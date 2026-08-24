"""CLI entrypoint durable INDEXER consumer."""

from __future__ import annotations

import asyncio
import logging

from pydantic import ValidationError

from tender_lens.ai import FakeAIProvider, OllamaAIProvider
from tender_lens.config import get_settings
from tender_lens.db import create_engine, create_session_factory
from tender_lens.indexer.service import IndexerService
from tender_lens.logging import configure_logging
from tender_lens.nats import NatsBroker
from tender_lens.schemas import TenderChangedV1

logger = logging.getLogger(__name__)


async def run() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    broker = NatsBroker(settings)
    await broker.connect()
    ai = (
        FakeAIProvider(settings.embedding_dimensions)
        if settings.ai_mode == "fake"
        else OllamaAIProvider(
            base_url=settings.ollama_url,
            embedding_model=settings.embedding_model,
            generation_model=settings.generation_model,
            dimensions=settings.embedding_dimensions,
        )
    )
    service = IndexerService(settings=settings, session_factory=sessions, ai=ai)

    try:
        async for message in broker.iter_messages():
            try:
                event = TenderChangedV1.model_validate_json(message.data)
            except ValidationError:
                logger.error("Некорректный NATS event удалён из очереди", exc_info=True)
                await message.ack()
                continue
            try:
                result = await service.process(event)
                logger.info(
                    "Индексация завершена: %s (%s chunks)",
                    result.status,
                    result.chunks,
                    extra={"event_id": str(event.event_id), "tender_id": str(event.tender_id)},
                )
                await message.ack()
            except Exception:
                logger.error(
                    "Индексация завершилась ошибкой; событие будет доставлено повторно",
                    extra={"event_id": str(event.event_id), "tender_id": str(event.tender_id)},
                    exc_info=True,
                )
                await message.nak(delay=10)
    finally:
        if isinstance(ai, OllamaAIProvider):
            await ai.aclose()
        await broker.close()
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()

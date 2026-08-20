"""Идемпотентная обработка tender.changed.v1 и атомарная замена чанков."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from tender_lens.ai import AIProvider
from tender_lens.config import Settings
from tender_lens.db import SessionFactory
from tender_lens.errors import ExtractionError
from tender_lens.hashing import build_chunk_key, chunk_content_hash
from tender_lens.indexer.chunk import chunk_units
from tender_lens.indexer.extract import extract_attachment, metadata_text
from tender_lens.models import Chunk, Tender
from tender_lens.schemas import TenderChangedV1

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class IndexResult:
    tender_id: UUID
    status: str
    chunks: int
    warnings: list[str]


class IndexerService:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: SessionFactory,
        ai: AIProvider,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._ai = ai

    async def _load_tender(self, tender_id: UUID) -> Tender | None:
        async with self._session_factory() as session:
            return await session.scalar(
                select(Tender)
                .where(Tender.id == tender_id)
                .options(selectinload(Tender.attachments))
            )

    async def _mark_failed(self, tender_id: UUID, message: str) -> None:
        async with self._session_factory() as session:
            tender = await session.get(Tender, tender_id, with_for_update=True)
            if tender is not None:
                tender.index_status = "failed"
                tender.last_error = message[:4000]
                await session.commit()

    async def process(self, event: TenderChangedV1) -> IndexResult:
        tender = await self._load_tender(event.tender_id)
        if tender is None:
            return IndexResult(event.tender_id, "missing", 0, [])
        if tender.content_hash != event.content_hash:
            return IndexResult(tender.id, "stale", 0, [])
        if tender.indexed_hash == event.content_hash and tender.index_status == "ready":
            return IndexResult(tender.id, "unchanged", 0, [])

        async with self._session_factory() as session:
            locked = await session.get(Tender, tender.id, with_for_update=True)
            if locked is None or locked.content_hash != event.content_hash:
                await session.rollback()
                return IndexResult(tender.id, "stale", 0, [])
            locked.index_status = "processing"
            locked.last_error = None
            await session.commit()

        warnings: list[str] = []
        try:
            units = [metadata_text(tender)]
            for attachment in tender.attachments:
                try:
                    units.extend(
                        extract_attachment(attachment, self._settings.max_attachment_bytes)
                    )
                except ExtractionError as exc:
                    warnings.append(str(exc))
                    logger.warning(
                        "Вложение пропущено при извлечении: %s",
                        exc,
                        extra={"tender_id": str(tender.id)},
                    )

            drafts = chunk_units(units, max_chars=1500, overlap_chars=150)
            if not drafts:
                raise RuntimeError("После извлечения не создано ни одного чанка")
            embeddings = await self._ai.embed([item.content for item in drafts])
            if len(embeddings) != len(drafts):
                raise RuntimeError("AI provider вернул неверное число embeddings")
            for vector in embeddings:
                if len(vector) != self._settings.embedding_dimensions:
                    raise RuntimeError("Embedding имеет неверную размерность")

            new_chunks: list[Chunk] = []
            for draft, vector in zip(drafts, embeddings, strict=True):
                content_hash = chunk_content_hash(draft.content)
                new_chunks.append(
                    Chunk(
                        tender_id=tender.id,
                        attachment_id=draft.attachment_id,
                        chunk_key=build_chunk_key(
                            tender.id,
                            draft.attachment_id,
                            draft.position,
                            content_hash,
                            self._settings.embedding_model,
                        ),
                        position=draft.position,
                        section=draft.section,
                        content=draft.content,
                        content_hash=content_hash,
                        embedding=vector,
                        embedding_model=self._settings.embedding_model,
                    )
                )

            async with self._session_factory() as session:
                locked = await session.get(Tender, tender.id, with_for_update=True)
                if locked is None or locked.content_hash != event.content_hash:
                    await session.rollback()
                    return IndexResult(tender.id, "stale", 0, warnings)
                await session.execute(delete(Chunk).where(Chunk.tender_id == tender.id))
                session.add_all(new_chunks)
                locked.indexed_hash = event.content_hash
                locked.index_status = "ready"
                locked.last_error = "\n".join(warnings)[:4000] if warnings else None
                await session.commit()
            return IndexResult(tender.id, "ready", len(new_chunks), warnings)
        except Exception as exc:
            await self._mark_failed(tender.id, str(exc))
            raise

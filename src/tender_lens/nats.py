"""Узкая интеграция NATS JetStream для одного события индексации."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from tender_lens.config import Settings
from tender_lens.errors import DependencyUnavailableError
from tender_lens.schemas import TenderChangedV1


class NatsMessage:
    """Минимальная обёртка, чтобы indexer не зависел от типов nats-py."""

    def __init__(self, raw_message: Any) -> None:
        self._raw = raw_message
        self.data: bytes = raw_message.data

    async def ack(self) -> None:
        await self._raw.ack()

    async def nak(self, delay: float | None = None) -> None:
        if delay is None:
            await self._raw.nak()
        else:
            await self._raw.nak(delay=delay)

    async def term(self) -> None:
        await self._raw.term()


class NatsBroker:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._nc: Any | None = None
        self._js: Any | None = None

    async def connect(self) -> None:
        try:
            import nats

            self._nc = await nats.connect(
                servers=[self._settings.nats_url],
                name="tender-lens",
                connect_timeout=5,
                max_reconnect_attempts=-1,
            )
            self._js = self._nc.jetstream()
            await self.ensure_stream()
        except Exception as exc:
            raise DependencyUnavailableError("Не удалось подключиться к NATS JetStream.") from exc

    async def ensure_stream(self) -> None:
        if self._js is None:
            raise RuntimeError("NATS connection не инициализирован")
        try:
            from nats.js.api import StorageType, StreamConfig
            from nats.js.errors import NotFoundError

            try:
                info = await self._js.stream_info(self._settings.nats_stream_name)
                subjects = set(info.config.subjects or [])
                if self._settings.nats_subject not in subjects:
                    raise DependencyUnavailableError(
                        "Существующий NATS stream имеет несовместимый subject."
                    )
            except NotFoundError:
                await self._js.add_stream(
                    config=StreamConfig(
                        name=self._settings.nats_stream_name,
                        subjects=[self._settings.nats_subject],
                        storage=StorageType.FILE,
                    )
                )
        except DependencyUnavailableError:
            raise
        except Exception as exc:
            raise DependencyUnavailableError("Не удалось настроить NATS stream.") from exc

    async def publish_tender_changed(self, event: TenderChangedV1) -> str:
        if self._js is None:
            raise RuntimeError("NATS connection не инициализирован")
        try:
            ack = await self._js.publish(
                self._settings.nats_subject,
                event.model_dump_json().encode("utf-8"),
                headers={"Nats-Msg-Id": str(event.event_id)},
            )
            return str(ack.seq)
        except Exception as exc:
            raise DependencyUnavailableError("Не удалось опубликовать NATS event.") from exc

    async def iter_messages(
        self,
        *,
        batch: int = 1,
        timeout: float = 1.0,
    ) -> AsyncIterator[NatsMessage]:
        if self._js is None:
            raise RuntimeError("NATS connection не инициализирован")
        try:
            from nats.js.api import AckPolicy, ConsumerConfig

            consumer_config = ConsumerConfig(
                durable_name=self._settings.nats_consumer_name,
                ack_policy=AckPolicy.EXPLICIT,
                ack_wait=self._settings.nats_ack_wait_seconds,
                max_deliver=self._settings.nats_max_deliver,
                filter_subject=self._settings.nats_subject,
            )
            # add_consumer идемпотентно создаёт или обновляет изменяемую
            # конфигурацию уже существующего durable consumer.
            await self._js.add_consumer(
                self._settings.nats_stream_name,
                config=consumer_config,
            )
            subscription = await self._js.pull_subscribe(
                self._settings.nats_subject,
                durable=self._settings.nats_consumer_name,
                stream=self._settings.nats_stream_name,
                config=consumer_config,
            )
        except Exception as exc:
            raise DependencyUnavailableError("Не удалось создать NATS consumer.") from exc

        while True:
            try:
                messages = await subscription.fetch(batch=batch, timeout=timeout)
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                if exc.__class__.__name__ == "TimeoutError":
                    continue
                raise DependencyUnavailableError("Ошибка получения NATS event.") from exc
            for message in messages:
                yield NatsMessage(message)

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.drain()
            await self._nc.close()
        self._nc = None
        self._js = None


class InMemoryBroker:
    """Детерминированный broker для unit/e2e без внешнего NATS."""

    def __init__(self) -> None:
        self.events: list[TenderChangedV1] = []

    async def connect(self) -> None:
        return None

    async def publish_tender_changed(self, event: TenderChangedV1) -> str:
        self.events.append(event)
        return str(len(self.events))

    async def close(self) -> None:
        return None

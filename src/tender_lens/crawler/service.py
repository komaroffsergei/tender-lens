"""Оркестрация crawl: upsert, вложения, cursor и NATS event."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tender_lens.config import Settings
from tender_lens.db import SessionFactory
from tender_lens.errors import AppError
from tender_lens.hashing import tender_content_hash
from tender_lens.models import Attachment, Source, Tender
from tender_lens.schemas import TenderChangedV1, TenderRecordV1
from tender_lens.storage import download_attachment

from .base import ResilientHttpClient, SourceAdapter

logger = logging.getLogger(__name__)


class EventPublisher(Protocol):
    async def publish_tender_changed(self, event: TenderChangedV1) -> str:
        ...


@dataclass(frozen=True, slots=True)
class PersistedTender:
    tender_id: UUID
    content_hash: str
    changed: bool
    attachment_ids: list[UUID]


@dataclass(frozen=True, slots=True)
class CrawlSummary:
    source: str
    received: int
    created_or_changed: int
    events_published: int
    attachments_ready: int
    next_cursor: str | None


class CrawlerService:
    def __init__(
        self,
        *,
        settings: Settings,
        session_factory: SessionFactory,
        attachment_client: ResilientHttpClient,
        publisher: EventPublisher,
    ) -> None:
        self._settings = settings
        self._session_factory = session_factory
        self._attachment_client = attachment_client
        self._publisher = publisher

    async def _source(self, session: AsyncSession, code: str) -> Source:
        source = await session.scalar(select(Source).where(Source.code == code))
        if source is None:
            source = Source(code=code)
            session.add(source)
            await session.flush()
        return source

    async def get_cursor(self, code: str) -> str | None:
        async with self._session_factory() as session:
            source = await self._source(session, code)
            await session.commit()
            return source.cursor

    async def persist_record(self, record: TenderRecordV1) -> PersistedTender:
        content_hash = tender_content_hash(record)
        async with self._session_factory() as session:
            source = await self._source(session, record.source)
            tender = await session.scalar(
                select(Tender).where(
                    Tender.source_id == source.id,
                    Tender.external_id == record.external_id,
                )
            )
            changed = tender is None or tender.content_hash != content_hash
            if tender is None:
                tender = Tender(
                    source_id=source.id,
                    external_id=record.external_id,
                    title=record.title,
                    description=record.description,
                    buyer_name=record.buyer_name,
                    amount=record.amount,
                    currency=record.currency,
                    published_at=record.published_at,
                    deadline=record.deadline,
                    source_url=str(record.source_url),
                    content_hash=content_hash,
                    index_status="pending",
                    raw_payload=record.raw_payload,
                )
                session.add(tender)
                await session.flush()
            else:
                tender.title = record.title
                tender.description = record.description
                tender.buyer_name = record.buyer_name
                tender.amount = record.amount
                tender.currency = record.currency
                tender.published_at = record.published_at
                tender.deadline = record.deadline
                tender.source_url = str(record.source_url)
                tender.raw_payload = record.raw_payload
                if changed:
                    tender.content_hash = content_hash
                    tender.index_status = "pending"
                    tender.last_error = None

            existing = {
                item.source_url: item
                for item in (
                    await session.scalars(
                        select(Attachment).where(Attachment.tender_id == tender.id)
                    )
                ).all()
            }
            current_urls = {str(item.source_url) for item in record.attachments}
            for old_url, attachment in existing.items():
                if old_url not in current_urls:
                    attachment.download_status = "skipped"

            attachment_ids: list[UUID] = []
            for item in record.attachments:
                url = str(item.source_url)
                attachment = existing.get(url)
                if attachment is None:
                    attachment = Attachment(
                        tender_id=tender.id,
                        external_id=item.external_id,
                        title=item.title,
                        filename=item.filename,
                        source_url=url,
                        content_type=item.content_type,
                        download_status="pending",
                    )
                    session.add(attachment)
                    await session.flush()
                else:
                    attachment.external_id = item.external_id
                    attachment.title = item.title
                    attachment.filename = item.filename
                    attachment.content_type = item.content_type or attachment.content_type
                    if attachment.download_status == "skipped":
                        attachment.download_status = "pending"
                attachment_ids.append(attachment.id)

            await session.commit()
            return PersistedTender(tender.id, content_hash, changed, attachment_ids)

    async def _download_one(self, tender_id: UUID, attachment_id: UUID) -> bool:
        async with self._session_factory() as session:
            attachment = await session.get(Attachment, attachment_id)
            if attachment is None or attachment.tender_id != tender_id:
                return False
            if attachment.download_status == "ready" and attachment.local_path:
                return False
            url = attachment.source_url
            filename = attachment.filename

        try:
            result = await download_attachment(
                client=self._attachment_client,
                url=url,
                root=self._settings.attachments_dir,
                tender_id=tender_id,
                attachment_id=attachment_id,
                filename=filename,
                max_bytes=self._settings.max_attachment_bytes,
            )
            async with self._session_factory() as session:
                attachment = await session.get(Attachment, attachment_id, with_for_update=True)
                if attachment is None:
                    return False
                attachment.local_path = result.local_path
                attachment.sha256 = result.sha256
                attachment.size_bytes = result.size_bytes
                attachment.content_type = attachment.content_type or result.content_type
                attachment.download_status = "ready"
                attachment.error_message = None
                tender = await session.get(Tender, tender_id, with_for_update=True)
                if tender is not None and tender.index_status == "ready":
                    tender.index_status = "pending"
                await session.commit()
            return True
        except Exception as exc:
            async with self._session_factory() as session:
                attachment = await session.get(Attachment, attachment_id, with_for_update=True)
                if attachment is not None:
                    attachment.download_status = "failed"
                    attachment.error_message = str(exc)[:2000]
                    await session.commit()
            logger.warning(
                "Не удалось скачать вложение",
                extra={"tender_id": str(tender_id), "event_id": str(attachment_id)},
                exc_info=True,
            )
            return False

    async def download_record_attachments(self, persisted: PersistedTender) -> int:
        if not persisted.attachment_ids:
            return 0
        outcomes = await asyncio.gather(
            *(self._download_one(persisted.tender_id, item) for item in persisted.attachment_ids)
        )
        return sum(outcomes)

    async def publish(self, tender_id: UUID, content_hash: str) -> bool:
        event = TenderChangedV1(tender_id=tender_id, content_hash=content_hash)
        try:
            await self._publisher.publish_tender_changed(event)
            return True
        except AppError:
            logger.error(
                "NATS publish не выполнен; pending будет переопубликован следующим циклом",
                extra={"tender_id": str(tender_id), "event_id": str(event.event_id)},
                exc_info=True,
            )
            return False

    async def republish_pending(self, limit: int = 100) -> int:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(Tender.id, Tender.content_hash)
                    .where(Tender.index_status == "pending")
                    .order_by(Tender.updated_at)
                    .limit(limit)
                )
            ).all()
        count = 0
        for tender_id, content_hash in rows:
            count += int(await self.publish(tender_id, content_hash))
        return count

    async def update_cursor(self, source_code: str, cursor: str | None) -> None:
        async with self._session_factory() as session:
            source = await self._source(session, source_code)
            source.cursor = cursor
            source.last_sync_at = datetime.now(UTC)
            await session.commit()

    async def run_source(self, adapter: SourceAdapter, max_items: int) -> CrawlSummary:
        cursor = await self.get_cursor(adapter.source_code)
        received = 0
        changed_count = 0
        published = 0
        attachments_ready = 0
        seen_cursors: set[str | None] = set()

        while received < max_items:
            if cursor in seen_cursors and cursor is not None:
                raise RuntimeError("Источник вернул повторяющийся cursor")
            seen_cursors.add(cursor)
            page = await adapter.fetch_page(cursor, max_items - received)
            if not page.records:
                await self.update_cursor(adapter.source_code, page.next_cursor)
                cursor = page.next_cursor
                break

            for record in page.records:
                persisted = await self.persist_record(record)
                received += 1
                downloaded = await self.download_record_attachments(persisted)
                attachments_ready += downloaded
                requires_index = persisted.changed or downloaded > 0
                if requires_index:
                    changed_count += 1
                    published += int(
                        await self.publish(persisted.tender_id, persisted.content_hash)
                    )
                if received >= max_items:
                    break

            # Cursor фиксируется только после успешной обработки всей принятой части.
            cursor = page.next_cursor
            await self.update_cursor(adapter.source_code, cursor)
            if cursor is None:
                break

        return CrawlSummary(
            source=adapter.source_code,
            received=received,
            created_or_changed=changed_count,
            events_published=published,
            attachments_ready=attachments_ready,
            next_cursor=cursor,
        )

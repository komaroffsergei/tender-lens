from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select, text

from tender_lens.ai import FakeAIProvider
from tender_lens.api.rate_limit import consume_rate_limit
from tender_lens.crawler.base import SourcePage
from tender_lens.crawler.service import CrawlerService
from tender_lens.indexer.service import IndexerService
from tender_lens.models import ApiKey, Chunk, Source, Tender
from tender_lens.nats import InMemoryBroker
from tender_lens.schemas import TenderChangedV1, TenderRecordV1
from tender_lens.search import SearchService

pytestmark = pytest.mark.integration


class UnusedAttachmentClient:
    """Заглушка: тесты этого файла не скачивают вложения."""


class SinglePageAdapter:
    source_code = "ted"

    def __init__(self, item: TenderRecordV1) -> None:
        self._item = item
        self.cursors: list[str | None] = []

    async def fetch_page(self, cursor: str | None, limit: int) -> SourcePage:
        del limit
        self.cursors.append(cursor)
        return SourcePage(records=[self._item], next_cursor="cursor-2")


class FailOncePublisher:
    def __init__(self) -> None:
        self.calls = 0

    async def publish_tender_changed(self, event: TenderChangedV1) -> str:
        del event
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary NATS failure")
        return str(self.calls)


class ChangeTenderThenFailAI:
    def __init__(self, callback) -> None:
        self._callback = callback

    async def embed(self, texts):
        del texts
        await self._callback()
        raise RuntimeError("old embedding failed")

    async def generate(self, *, system, prompt):
        del system, prompt
        raise AssertionError("generate must not be called")

    async def health(self):
        return True


def record(title: str = "Server equipment and storage") -> TenderRecordV1:
    return TenderRecordV1(
        source="ted",
        external_id="T-1",
        title=title,
        description="Rack servers, storage system and warranty for 36 months",
        buyer_name="Example authority",
        amount=Decimal("1000.00"),
        currency="EUR",
        published_at=datetime(2026, 8, 20, tzinfo=UTC),
        source_url="https://example.test/tender/T-1",
        attachments=[],
        raw_payload={"id": "T-1", "title": title},
    )


@pytest.mark.asyncio
async def test_migration_created_exact_tables_and_vector_extension(session_factory):
    async with session_factory() as session:
        tables = {
            row[0]
            for row in (
                await session.execute(
                    text(
                        "SELECT tablename FROM pg_tables "
                        "WHERE schemaname='public' AND tablename IN "
                        "('sources','tenders','attachments','chunks','api_keys')"
                    )
                )
            ).all()
        }
        extension = await session.scalar(
            text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")
        )
    assert tables == {"sources", "tenders", "attachments", "chunks", "api_keys"}
    assert extension is True


@pytest.mark.asyncio
async def test_new_unchanged_changed_upsert(session_factory, integration_settings):
    broker = InMemoryBroker()
    service = CrawlerService(
        settings=integration_settings,
        session_factory=session_factory,
        attachment_client=UnusedAttachmentClient(),  # type: ignore[arg-type]
        publisher=broker,
    )
    first = await service.persist_record(record())
    same = await service.persist_record(record())
    changed = await service.persist_record(record("Updated server equipment"))
    assert first.changed is True
    assert same.changed is False
    assert changed.changed is True
    assert first.tender_id == same.tender_id == changed.tender_id
    async with session_factory() as session:
        assert await session.scalar(select(func.count(Tender.id))) == 1
        row = await session.get(Tender, first.tender_id)
        assert row is not None
        assert row.title == "Updated server equipment"
        assert row.index_status == "pending"


@pytest.mark.asyncio
async def test_same_external_id_is_independent_between_sources(
    session_factory,
    integration_settings,
):
    service = CrawlerService(
        settings=integration_settings,
        session_factory=session_factory,
        attachment_client=UnusedAttachmentClient(),  # type: ignore[arg-type]
        publisher=InMemoryBroker(),
    )
    ted = record()
    cf = ted.model_copy(
        update={
            "source": "contracts_finder",
            "source_url": "https://example.test/cf/T-1",
        }
    )
    await service.persist_record(ted)
    await service.persist_record(cf)
    async with session_factory() as session:
        assert await session.scalar(select(func.count(Tender.id))) == 2
        assert await session.scalar(select(func.count(Source.id))) == 2


@pytest.mark.asyncio
async def test_cursor_advances_only_after_processed_page(session_factory, integration_settings):
    broker = InMemoryBroker()
    service = CrawlerService(
        settings=integration_settings,
        session_factory=session_factory,
        attachment_client=UnusedAttachmentClient(),  # type: ignore[arg-type]
        publisher=broker,
    )
    adapter = SinglePageAdapter(record())

    summary = await service.run_source(adapter, max_items=1)

    assert summary.next_cursor == "cursor-2"
    assert len(broker.events) == 1
    async with session_factory() as session:
        source = await session.scalar(select(Source).where(Source.code == "ted"))
        assert source is not None
        assert source.cursor == "cursor-2"


@pytest.mark.asyncio
async def test_cursor_is_not_advanced_after_record_failure(
    session_factory, integration_settings, monkeypatch
):
    service = CrawlerService(
        settings=integration_settings,
        session_factory=session_factory,
        attachment_client=UnusedAttachmentClient(),  # type: ignore[arg-type]
        publisher=InMemoryBroker(),
    )

    async def fail(_record):
        raise RuntimeError("database failure")

    monkeypatch.setattr(service, "persist_record", fail)
    with pytest.raises(RuntimeError, match="database failure"):
        await service.run_source(SinglePageAdapter(record()), max_items=1)

    async with session_factory() as session:
        source = await session.scalar(select(Source).where(Source.code == "ted"))
        assert source is not None
        assert source.cursor is None


@pytest.mark.asyncio
async def test_pending_event_is_republished_after_publish_failure(
    session_factory, integration_settings
):
    publisher = FailOncePublisher()
    service = CrawlerService(
        settings=integration_settings,
        session_factory=session_factory,
        attachment_client=UnusedAttachmentClient(),  # type: ignore[arg-type]
        publisher=publisher,
    )

    summary = await service.run_source(SinglePageAdapter(record()), max_items=1)
    republished = await service.republish_pending()

    assert summary.events_published == 0
    assert republished == 1
    assert publisher.calls == 2


@pytest.mark.asyncio
async def test_indexer_idempotency_and_exact_search(session_factory, integration_settings):
    crawler = CrawlerService(
        settings=integration_settings,
        session_factory=session_factory,
        attachment_client=UnusedAttachmentClient(),  # type: ignore[arg-type]
        publisher=InMemoryBroker(),
    )
    persisted = await crawler.persist_record(record())
    event = TenderChangedV1(
        tender_id=persisted.tender_id,
        content_hash=persisted.content_hash,
    )
    ai = FakeAIProvider(1024)
    indexer = IndexerService(
        settings=integration_settings,
        session_factory=session_factory,
        ai=ai,
    )
    first = await indexer.process(event)
    second = await indexer.process(event)
    assert first.status == "ready"
    assert first.chunks > 0
    assert second.status == "unchanged"

    async with session_factory() as session:
        count = await session.scalar(
            select(func.count(Chunk.id)).where(Chunk.tender_id == persisted.tender_id)
        )
        result = await SearchService(ai).search(session, "server storage warranty", 5)
    assert count == first.chunks
    assert result.items
    assert result.items[0].tender_id == persisted.tender_id


@pytest.mark.asyncio
async def test_stale_event_does_not_overwrite_new_version(session_factory, integration_settings):
    crawler = CrawlerService(
        settings=integration_settings,
        session_factory=session_factory,
        attachment_client=UnusedAttachmentClient(),  # type: ignore[arg-type]
        publisher=InMemoryBroker(),
    )
    old = await crawler.persist_record(record())
    await crawler.persist_record(record("New version"))
    result = await IndexerService(
        settings=integration_settings,
        session_factory=session_factory,
        ai=FakeAIProvider(1024),
    ).process(TenderChangedV1(tender_id=old.tender_id, content_hash=old.content_hash))
    assert result.status == "stale"
    async with session_factory() as session:
        row = await session.get(Tender, old.tender_id)
        assert row is not None
        assert row.title == "New version"
        assert row.indexed_hash is None


@pytest.mark.asyncio
async def test_old_failed_event_does_not_mark_new_version_failed(
    session_factory, integration_settings
):
    crawler = CrawlerService(
        settings=integration_settings,
        session_factory=session_factory,
        attachment_client=UnusedAttachmentClient(),  # type: ignore[arg-type]
        publisher=InMemoryBroker(),
    )
    old = await crawler.persist_record(record())

    async def change_tender():
        await crawler.persist_record(record("New version during embedding"))

    indexer = IndexerService(
        settings=integration_settings,
        session_factory=session_factory,
        ai=ChangeTenderThenFailAI(change_tender),
    )
    with pytest.raises(RuntimeError, match="old embedding failed"):
        await indexer.process(
            TenderChangedV1(tender_id=old.tender_id, content_hash=old.content_hash)
        )

    async with session_factory() as session:
        row = await session.get(Tender, old.tender_id)
        assert row is not None
        assert row.title == "New version during embedding"
        assert row.index_status == "pending"
        assert row.last_error is None


@pytest.mark.asyncio
async def test_irrelevant_question_skips_generation(session_factory, integration_settings):
    crawler = CrawlerService(
        settings=integration_settings,
        session_factory=session_factory,
        attachment_client=UnusedAttachmentClient(),  # type: ignore[arg-type]
        publisher=InMemoryBroker(),
    )
    persisted = await crawler.persist_record(record())
    ai = FakeAIProvider(1024)
    await IndexerService(
        settings=integration_settings,
        session_factory=session_factory,
        ai=ai,
    ).process(
        TenderChangedV1(
            tender_id=persisted.tender_id,
            content_hash=persisted.content_hash,
        )
    )

    async with session_factory() as session:
        response = await SearchService(ai, min_relevance_score=0.15).ask(
            session,
            "xylophone nebula pineapple archaeology",
            5,
        )

    assert response.sources == []
    assert response.answer == "Недостаточно данных в базе знаний."
    assert ai.generate_calls == 0


@pytest.mark.asyncio
async def test_rate_limiter_is_atomic_under_concurrency(session_factory):
    async with session_factory() as session:
        key = ApiKey(
            name="concurrent",
            key_hash="a" * 64,
            enabled=True,
            limit_per_minute=5,
        )
        session.add(key)
        await session.commit()
        await session.refresh(key)
        key_id = key.id

    now = datetime(2026, 8, 20, 10, 11, tzinfo=UTC)

    async def consume() -> bool:
        async with session_factory() as session:
            try:
                await consume_rate_limit(session, key_id, now=now)
                return True
            except Exception:
                return False

    outcomes = await asyncio.gather(*(consume() for _ in range(10)))
    assert sum(outcomes) == 5
    async with session_factory() as session:
        row = await session.get(ApiKey, key_id)
        assert row is not None
        assert row.request_count == 5

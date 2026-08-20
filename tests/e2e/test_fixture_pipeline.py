from __future__ import annotations

import os

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text

from tender_lens.ai import FakeAIProvider
from tender_lens.config import Settings
from tender_lens.crawler.base import ResilientHttpClient
from tender_lens.crawler.fixture import FixtureAdapter
from tender_lens.crawler.service import CrawlerService
from tender_lens.db import create_engine, create_session_factory
from tender_lens.indexer.service import IndexerService
from tender_lens.nats import InMemoryBroker
from tender_lens.search import SearchService

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def e2e_settings(tmp_path_factory) -> Settings:
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("e2e disabled; set RUN_INTEGRATION=1")
    return Settings(
        app_env="test",
        database_url=os.getenv(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://tender_lens:tender_lens@localhost:55432/tender_lens_test",
        ),
        nats_url=os.getenv("TEST_NATS_URL", "nats://localhost:54222"),
        ai_mode="fake",
        embedding_dimensions=1024,
        attachments_dir=tmp_path_factory.mktemp("attachments"),
        http_base_delay_seconds=0,
        http_jitter_seconds=0,
        max_attachment_bytes=2_000_000,
    )


@pytest_asyncio.fixture
async def e2e_sessions(e2e_settings):
    engine = create_engine(e2e_settings)
    sessions = create_session_factory(engine)
    async with sessions() as session:
        await session.execute(
            text("TRUNCATE TABLE chunks, attachments, tenders, sources, api_keys CASCADE")
        )
        await session.commit()
    yield sessions
    await engine.dispose()


def fixture_transport(pdf: bytes, xml: bytes):
    async def handler(request):
        if request.url.path.endswith(".pdf"):
            return httpx.Response(200, content=pdf, headers={"Content-Type": "application/pdf"})
        if request.url.path.endswith(".xml"):
            return httpx.Response(200, content=xml, headers={"Content-Type": "application/xml"})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source,fixture_name,query",
    [
        ("ted", "ted_search_response.json", "server equipment storage warranty"),
        ("contracts_finder", "contracts_finder_ocds.json", "rack servers network storage"),
    ],
)
async def test_fixture_to_database_index_search_and_ask(
    source,
    fixture_name,
    query,
    e2e_settings,
    e2e_sessions,
    fixture_dir,
):
    pdf = (fixture_dir / "sample_tender.pdf").read_bytes()
    xml = (fixture_dir / "sample_notice.xml").read_bytes()
    allowed_hosts = {
        "ted.europa.eu",
        "www.contractsfinder.service.gov.uk",
    }
    async with httpx.AsyncClient(transport=fixture_transport(pdf, xml)) as raw:
        client = ResilientHttpClient(
            max_concurrency=2,
            timeout_seconds=2,
            max_attempts=1,
            base_delay_seconds=0,
            jitter_seconds=0,
            user_agent="e2e",
            allowed_hosts=allowed_hosts,
            client=raw,
        )
        broker = InMemoryBroker()
        crawler = CrawlerService(
            settings=e2e_settings,
            session_factory=e2e_sessions,
            attachment_client=client,
            publisher=broker,
        )
        summary = await crawler.run_source(
            FixtureAdapter(source, fixture_dir / fixture_name),
            max_items=5,
        )
    assert summary.received == 1
    assert len(broker.events) == 1

    ai = FakeAIProvider(1024)
    indexer = IndexerService(
        settings=e2e_settings,
        session_factory=e2e_sessions,
        ai=ai,
    )
    indexed = await indexer.process(broker.events[0])
    assert indexed.status == "ready"

    async with e2e_sessions() as session:
        search = await SearchService(ai).search(session, query, 5)
        answer = await SearchService(ai).ask(session, query, 5)
    assert search.items
    assert answer.sources
    assert answer.answer.startswith("По найденным документам")


@pytest.mark.asyncio
async def test_repeat_fixture_crawl_does_not_create_duplicate_event(
    e2e_settings,
    e2e_sessions,
    fixture_dir,
):
    pdf = (fixture_dir / "sample_tender.pdf").read_bytes()
    xml = (fixture_dir / "sample_notice.xml").read_bytes()
    async with httpx.AsyncClient(transport=fixture_transport(pdf, xml)) as raw:
        client = ResilientHttpClient(
            max_concurrency=2,
            timeout_seconds=2,
            max_attempts=1,
            base_delay_seconds=0,
            jitter_seconds=0,
            user_agent="e2e",
            allowed_hosts={"ted.europa.eu"},
            client=raw,
        )
        broker = InMemoryBroker()
        service = CrawlerService(
            settings=e2e_settings,
            session_factory=e2e_sessions,
            attachment_client=client,
            publisher=broker,
        )
        await service.run_source(
            FixtureAdapter("ted", fixture_dir / "ted_search_response.json"), 5
        )
        first_count = len(broker.events)
        await service.run_source(
            FixtureAdapter("ted", fixture_dir / "ted_search_response.json"), 5
        )
    assert first_count == 1
    assert len(broker.events) == 1

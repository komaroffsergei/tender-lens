from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from tender_lens.config import Settings
from tender_lens.db import create_engine, create_session_factory

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def integration_settings() -> Settings:
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("integration tests disabled; set RUN_INTEGRATION=1")
    return Settings(
        app_env="test",
        database_url=os.getenv(
            "TEST_DATABASE_URL",
            "postgresql+asyncpg://tender_lens:tender_lens@localhost:55432/tender_lens_test",
        ),
        nats_url=os.getenv("TEST_NATS_URL", "nats://localhost:54222"),
        ai_mode="fake",
        embedding_dimensions=1024,
        attachments_dir=os.getenv("TEST_ATTACHMENTS_DIR", "/tmp/tender-lens-test-attachments"),
        http_base_delay_seconds=0,
        http_jitter_seconds=0,
        nats_stream_name="TENDERS_TEST",
        nats_consumer_name="INDEXER_TEST",
    )


@pytest_asyncio.fixture
async def engine(integration_settings: Settings) -> AsyncEngine:
    value = create_engine(integration_settings)
    yield value
    await value.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest_asyncio.fixture(autouse=True)
async def clean_database(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await session.execute(
            text("TRUNCATE TABLE chunks, attachments, tenders, sources, api_keys CASCADE")
        )
        await session.commit()
    yield

"""CLI entrypoint роли crawler."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from tender_lens.config import Settings, get_settings
from tender_lens.crawler.base import ResilientHttpClient
from tender_lens.crawler.contracts_finder import ContractsFinderAdapter
from tender_lens.crawler.fixture import FixtureAdapter
from tender_lens.crawler.service import CrawlerService
from tender_lens.crawler.ted import TedAdapter
from tender_lens.db import create_engine, create_session_factory
from tender_lens.logging import configure_logging
from tender_lens.nats import NatsBroker

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Асинхронный сбор закупок TenderLens")
    parser.add_argument("--once", action="store_true", help="Завершиться после одного цикла")
    parser.add_argument(
        "--source",
        choices=["ted", "contracts_finder", "all"],
        default="all",
    )
    parser.add_argument("--max-items", type=int, default=None)
    parser.add_argument(
        "--fixture",
        type=Path,
        help="JSON fixture соответствующего источника; live HTTP не вызывается",
    )
    return parser


def _source_hosts(source: str) -> set[str]:
    if source == "ted":
        return {"api.ted.europa.eu", "ted.europa.eu"}
    return {
        "www.contractsfinder.service.gov.uk",
        "contractsfinder.service.gov.uk",
        "assets.publishing.service.gov.uk",
    }


def _adapter(
    source: str,
    settings: Settings,
    source_client: ResilientHttpClient,
    fixture: Path | None,
):
    if fixture is not None:
        return FixtureAdapter(source, fixture)
    if source == "ted":
        return TedAdapter(
            source_client,
            base_url=settings.ted_base_url,
            query=settings.ted_query,
        )
    return ContractsFinderAdapter(
        source_client,
        base_url=settings.contracts_finder_base_url,
    )


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    broker = NatsBroker(settings)
    await broker.connect()

    sources = ["ted", "contracts_finder"] if args.source == "all" else [args.source]
    max_items = args.max_items or settings.source_max_items

    try:
        while True:
            for source in sources:
                allowed = _source_hosts(source)
                async with ResilientHttpClient(
                    max_concurrency=settings.crawl_max_concurrency,
                    timeout_seconds=settings.http_timeout_seconds,
                    max_attempts=settings.http_max_attempts,
                    base_delay_seconds=settings.http_base_delay_seconds,
                    jitter_seconds=settings.http_jitter_seconds,
                    user_agent=settings.user_agent,
                    allowed_hosts=allowed,
                ) as source_client, ResilientHttpClient(
                    max_concurrency=settings.attachment_max_concurrency,
                    timeout_seconds=settings.http_timeout_seconds,
                    max_attempts=settings.http_max_attempts,
                    base_delay_seconds=settings.http_base_delay_seconds,
                    jitter_seconds=settings.http_jitter_seconds,
                    user_agent=settings.user_agent,
                    allowed_hosts=allowed,
                ) as attachment_client:
                    service = CrawlerService(
                        settings=settings,
                        session_factory=sessions,
                        attachment_client=attachment_client,
                        publisher=broker,
                    )
                    await service.republish_pending()
                    summary = await service.run_source(
                        _adapter(source, settings, source_client, args.fixture),
                        max_items=max_items,
                    )
                    logger.info("Crawl завершён: %s", json.dumps(summary.__dict__, default=str))
            if args.once or args.fixture:
                return
            await asyncio.sleep(settings.crawl_interval_seconds)
    finally:
        await broker.close()
        await engine.dispose()


def main() -> None:
    asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()

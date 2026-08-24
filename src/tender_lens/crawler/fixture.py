"""Одноразовый fixture-адаптер для локального demo и e2e."""

from __future__ import annotations

import json
from pathlib import Path

from tender_lens.crawler.base import SourcePage
from tender_lens.crawler.contracts_finder import ContractsFinderAdapter
from tender_lens.crawler.ted import TedAdapter


class FixtureAdapter:
    def __init__(self, source_code: str, fixture_path: Path) -> None:
        if source_code not in {"ted", "contracts_finder"}:
            raise ValueError("fixture поддерживает только ted/contracts_finder")
        self.source_code = source_code
        self._fixture_path = fixture_path
        self._used = False

    async def fetch_page(self, cursor: str | None, limit: int) -> SourcePage:
        del cursor
        if self._used:
            return SourcePage(records=[], next_cursor=None)
        payload = json.loads(self._fixture_path.read_text(encoding="utf-8"))
        if self.source_code == "ted":
            items = payload.get("notices", [])
            records = [TedAdapter.map_notice(item) for item in items[:limit]]
        else:
            items = payload.get("releases", [])
            records = [ContractsFinderAdapter.map_release(item) for item in items[:limit]]
        self._used = True
        return SourcePage(records=records, next_cursor=None)

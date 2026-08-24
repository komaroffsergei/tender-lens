"""Адаптер UK Contracts Finder OCDS Search."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, urlparse

from tender_lens.crawler.base import ResilientHttpClient, SourcePage
from tender_lens.schemas import AttachmentRecordV1, TenderRecordV1

logger = logging.getLogger(__name__)


def _object(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _array(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _money(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _next_cursor(data: dict[str, Any]) -> str | None:
    links = _object(data.get("links"))
    next_url = links.get("next")
    if not isinstance(next_url, str):
        return None
    return parse_qs(urlparse(next_url).query).get("cursor", [None])[0]


class ContractsFinderAdapter:
    source_code = "contracts_finder"

    def __init__(self, client: ResilientHttpClient, *, base_url: str) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def fetch_page(self, cursor: str | None, limit: int) -> SourcePage:
        params: dict[str, Any] = {"stages": "tender", "limit": min(limit, 100)}
        if cursor:
            params["cursor"] = cursor
        data = await self._client.get_json(
            f"{self._base_url}/Published/Notices/OCDS/Search", params=params
        )
        releases = data.get("releases") or []
        records: list[TenderRecordV1] = []
        for index, item in enumerate(releases if isinstance(releases, list) else []):
            if not isinstance(item, dict):
                logger.warning(
                    "Contracts Finder release пропущен: ожидается JSON object",
                    extra={"item_index": index},
                )
                continue
            try:
                records.append(self.map_release(item))
            except (TypeError, ValueError) as exc:
                # Некорректная release изолируется, остальные элементы страницы сохраняются.
                logger.warning(
                    "Contracts Finder release пропущен: %s",
                    exc,
                    extra={"item_index": index},
                )
        return SourcePage(records=records, next_cursor=_next_cursor(data))

    @staticmethod
    def map_release(release: dict[str, Any]) -> TenderRecordV1:
        tender = _object(release.get("tender"))
        buyer = _object(release.get("buyer"))
        value = _object(tender.get("value"))
        period = _object(tender.get("tenderPeriod"))
        links = _object(release.get("links"))

        external_id = str(
            tender.get("id") or release.get("ocid") or release.get("id") or ""
        ).strip()
        title = str(tender.get("title") or release.get("title") or "").strip()
        if not external_id or not title:
            raise ValueError("Contracts Finder release не содержит id/title")

        attachments: list[AttachmentRecordV1] = []
        documents = _array(tender.get("documents"))
        for document in documents:
            if not isinstance(document, dict) or not document.get("url"):
                continue
            url = str(document["url"])
            filename = Path(urlparse(url).path).name or f"{document.get('id', 'document')}.bin"
            attachments.append(
                AttachmentRecordV1(
                    external_id=str(document.get("id")) if document.get("id") else None,
                    title=str(document.get("title")) if document.get("title") else None,
                    filename=filename,
                    source_url=url,
                    content_type=str(document.get("format")) if document.get("format") else None,
                )
            )

        source_url = links.get("self") or release.get("url")
        if not source_url:
            source_url = f"https://www.contractsfinder.service.gov.uk/Notice/{external_id}"

        return TenderRecordV1(
            source="contracts_finder",
            external_id=external_id,
            title=title,
            description=(
                str(tender.get("description")).strip() if tender.get("description") else None
            ),
            buyer_name=str(buyer.get("name")).strip() if buyer.get("name") else None,
            amount=_money(value.get("amount")),
            currency=str(value.get("currency")).upper() if value.get("currency") else None,
            published_at=_dt(release.get("date") or period.get("startDate")),
            deadline=_dt(period.get("endDate")),
            source_url=str(source_url),
            attachments=attachments,
            raw_payload=release,
        )

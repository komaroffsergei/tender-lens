"""Адаптер официального TED Search API v3."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from tender_lens.crawler.base import ResilientHttpClient, SourcePage
from tender_lens.schemas import AttachmentRecordV1, TenderRecordV1

logger = logging.getLogger(__name__)


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return _first(value[0]) if value else None
    if isinstance(value, dict):
        for key in ("value", "text", "eng", "en"):
            if key in value:
                return _first(value[key])
        for item in value.values():
            candidate = _first(item)
            if candidate not in (None, ""):
                return candidate
        return None
    return value


def _string(value: Any) -> str | None:
    candidate = _first(value)
    if candidate is None:
        return None
    text = str(candidate).strip()
    return text or None


def _datetime(value: Any) -> datetime | None:
    text = _string(value)
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=UTC)
    return result.astimezone(UTC)


def _decimal(value: Any) -> Decimal | None:
    candidate = _first(value)
    if candidate in (None, ""):
        return None
    try:
        return Decimal(str(candidate).replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None


class TedAdapter:
    source_code = "ted"

    def __init__(
        self,
        client: ResilientHttpClient,
        *,
        base_url: str,
        query: str,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._query = query

    async def fetch_page(self, cursor: str | None, limit: int) -> SourcePage:
        fields = [
            "publication-number",
            "notice-title",
            "buyer-name",
            "publication-date",
            "deadline",
            "deadline-receipt-request",
            "deadline-receipt-tender-date-lot",
            "estimated-value-proc",
            "estimated-value-cur-proc",
            "total-value",
            "total-value-cur",
            "description-proc",
            "links",
        ]
        payload: dict[str, Any] = {
            "query": self._query,
            "fields": fields,
            "limit": min(limit, 250),
            "scope": "ACTIVE",
            "checkQuerySyntax": False,
            "paginationMode": "ITERATION",
        }
        if cursor:
            payload["iterationNextToken"] = cursor
        data = await self._client.post_json(f"{self._base_url}/v3/notices/search", payload)
        notices = data.get("notices") or []
        records: list[TenderRecordV1] = []
        for index, item in enumerate(notices if isinstance(notices, list) else []):
            if not isinstance(item, dict):
                logger.warning(
                    "TED notice пропущен: ожидается JSON object",
                    extra={"item_index": index},
                )
                continue
            try:
                records.append(self.map_notice(item))
            except (TypeError, ValueError) as exc:
                # Одна испорченная запись не должна обрывать обработку всей страницы.
                logger.warning(
                    "TED notice пропущен: %s",
                    exc,
                    extra={"item_index": index},
                )
        next_cursor = _string(data.get("iterationNextToken"))
        return SourcePage(records=records, next_cursor=next_cursor)

    @staticmethod
    def map_notice(notice: dict[str, Any]) -> TenderRecordV1:
        external_id = _string(notice.get("publication-number") or notice.get("publicationNumber"))
        title = _string(notice.get("notice-title") or notice.get("title"))
        if not external_id or not title:
            raise ValueError("TED notice не содержит publication-number/title")

        raw_links = notice.get("links")
        links = cast(dict[str, Any], raw_links) if isinstance(raw_links, dict) else {}
        html_url = _string(links.get("html")) or (
            f"https://ted.europa.eu/en/notice/-/detail/{external_id}"
        )
        attachments: list[AttachmentRecordV1] = []
        for kind, content_type, suffix, caption in (
            ("pdf", "application/pdf", ".pdf", "Published notice PDF"),
            ("xml", "application/xml", ".xml", "Published notice XML"),
        ):
            url = _string(links.get(kind))
            if url:
                attachments.append(
                    AttachmentRecordV1(
                        external_id=kind,
                        title=caption,
                        filename=f"{Path(external_id).name}{suffix}",
                        source_url=url,
                        content_type=content_type,
                    )
                )

        return TenderRecordV1(
            source="ted",
            external_id=external_id,
            title=title,
            description=_string(
                notice.get("description-proc")
                or notice.get("description-procurement")
                or notice.get("description")
            ),
            buyer_name=_string(notice.get("buyer-name") or notice.get("buyer")),
            amount=_decimal(
                notice.get("estimated-value-proc")
                or notice.get("total-value")
                or notice.get("estimated-value")
                or notice.get("estimatedValue")
            ),
            currency=_string(
                notice.get("estimated-value-cur-proc")
                or notice.get("total-value-cur")
                or notice.get("estimated-value-currency")
                or notice.get("currency")
            ),
            published_at=_datetime(
                notice.get("publication-date") or notice.get("notice-publication-date")
            ),
            deadline=_datetime(
                notice.get("deadline")
                or notice.get("deadline-receipt-request")
                or notice.get("deadline-receipt-tender-date-lot")
                or notice.get("deadline-receipt-tender-date")
            ),
            source_url=html_url,
            attachments=attachments,
            raw_payload=notice,
        )

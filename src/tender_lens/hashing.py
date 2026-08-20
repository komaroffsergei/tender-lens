"""Детерминированные hash-функции для закупок, файлов и чанков."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from tender_lens.schemas import TenderRecordV1


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def _datetime_to_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    normalized = value.quantize(Decimal("0.01"))
    return format(normalized, "f")


def canonical_tender_payload(record: TenderRecordV1) -> dict[str, Any]:
    attachments = sorted(record.attachments, key=lambda item: str(item.source_url))
    return {
        "source": record.source,
        "external_id": record.external_id,
        "title": record.title,
        "description": record.description,
        "buyer_name": record.buyer_name,
        "amount": _decimal_to_string(record.amount),
        "currency": record.currency,
        "published_at": _datetime_to_utc_iso(record.published_at),
        "deadline": _datetime_to_utc_iso(record.deadline),
        "source_url": str(record.source_url),
        "attachments": [
            {
                "external_id": item.external_id,
                "title": item.title,
                "filename": item.filename,
                "source_url": str(item.source_url),
                "content_type": item.content_type,
            }
            for item in attachments
        ],
    }


def tender_content_hash(record: TenderRecordV1) -> str:
    serialized = json.dumps(
        canonical_tender_payload(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256_text(serialized)


def chunk_content_hash(content: str) -> str:
    return sha256_text(content)


def build_chunk_key(
    tender_id: UUID,
    attachment_id: UUID | None,
    position: int,
    content_hash: str,
    embedding_model: str,
) -> str:
    attachment_part = str(attachment_id) if attachment_id else "metadata"
    raw = f"{tender_id}:{attachment_part}:{position}:{content_hash}:{embedding_model}"
    return sha256_text(raw)

from __future__ import annotations

import json
from datetime import UTC
from decimal import Decimal
from uuid import UUID

import jsonschema
import pytest
from pydantic import ValidationError

from tender_lens.hashing import build_chunk_key, tender_content_hash
from tender_lens.schemas import AttachmentRecordV1, TenderChangedV1, TenderRecordV1


def load_record(fixture_dir):
    return TenderRecordV1.model_validate_json(
        (fixture_dir / "normalized_tender.json").read_text(encoding="utf-8")
    )


def test_normalized_fixture_is_valid(fixture_dir):
    record = load_record(fixture_dir)
    assert record.source == "ted"
    assert record.amount == Decimal("1250000.0")
    assert record.published_at.tzinfo is not None
    assert record.published_at.utcoffset() == UTC.utcoffset(record.published_at)


@pytest.mark.parametrize("field", ["external_id", "title"])
def test_required_strings_reject_blank(fixture_dir, field):
    payload = json.loads((fixture_dir / "normalized_tender.json").read_text())
    payload[field] = "   "
    with pytest.raises(ValidationError):
        TenderRecordV1.model_validate(payload)


@pytest.mark.parametrize("currency", ["EU", "EURO", "12A", "€€€"])
def test_currency_validation(fixture_dir, currency):
    payload = json.loads((fixture_dir / "normalized_tender.json").read_text())
    payload["currency"] = currency
    with pytest.raises(ValidationError):
        TenderRecordV1.model_validate(payload)


def test_negative_amount_is_rejected(fixture_dir):
    payload = json.loads((fixture_dir / "normalized_tender.json").read_text())
    payload["amount"] = -1
    with pytest.raises(ValidationError):
        TenderRecordV1.model_validate(payload)


def test_extra_internal_field_is_rejected(fixture_dir):
    payload = json.loads((fixture_dir / "normalized_tender.json").read_text())
    payload["only_ted_knows_this"] = True
    with pytest.raises(ValidationError):
        TenderRecordV1.model_validate(payload)


def test_attachment_normalizes_optional_empty_strings():
    item = AttachmentRecordV1(
        external_id=" ",
        title="",
        filename=" spec.pdf ",
        source_url="https://example.test/spec.pdf",
    )
    assert item.external_id is None
    assert item.title is None
    assert item.filename == "spec.pdf"


def test_hash_does_not_depend_on_raw_json_key_order(fixture_dir):
    record = load_record(fixture_dir)
    payload = record.model_dump(mode="python")
    raw = payload["raw_payload"]
    payload["raw_payload"] = dict(reversed(list(raw.items())))
    reordered = TenderRecordV1.model_validate(payload)
    assert tender_content_hash(record) == tender_content_hash(reordered)


def test_hash_does_not_depend_on_attachment_order(fixture_dir):
    record = load_record(fixture_dir)
    payload = record.model_dump(mode="python")
    payload["attachments"] = [
        AttachmentRecordV1(
            filename="z.xml",
            source_url="https://example.test/z.xml",
            content_type="application/xml",
        ),
        *payload["attachments"],
    ]
    first = TenderRecordV1.model_validate(payload)
    payload["attachments"].reverse()
    second = TenderRecordV1.model_validate(payload)
    assert tender_content_hash(first) == tender_content_hash(second)


def test_hash_changes_when_meaningful_field_changes(fixture_dir):
    record = load_record(fixture_dir)
    payload = record.model_dump(mode="python")
    payload["title"] = record.title + " updated"
    changed = TenderRecordV1.model_validate(payload)
    assert tender_content_hash(record) != tender_content_hash(changed)


def test_event_rejects_bad_hash_and_extra_field():
    base = {
        "schema_version": 1,
        "event_id": "00000000-0000-0000-0000-000000000001",
        "occurred_at": "2026-08-20T10:00:00Z",
        "tender_id": "00000000-0000-0000-0000-000000000002",
        "content_hash": "a" * 64,
    }
    assert TenderChangedV1.model_validate(base).schema_version == 1
    with pytest.raises(ValidationError):
        TenderChangedV1.model_validate({**base, "content_hash": "BAD"})
    with pytest.raises(ValidationError):
        TenderChangedV1.model_validate({**base, "secret": "oops"})


def test_chunk_key_is_deterministic():
    args = (UUID(int=1), None, 0, "a" * 64, "model")
    assert build_chunk_key(*args) == build_chunk_key(*args)
    assert build_chunk_key(UUID(int=1), None, 1, "a" * 64, "model") != build_chunk_key(*args)


def test_json_schemas_accept_examples(project_root, fixture_dir):
    record_schema = json.loads((project_root / "schemas/tender-record-v1.schema.json").read_text())
    event_schema = json.loads((project_root / "schemas/tender-changed-v1.schema.json").read_text())
    record = json.loads((fixture_dir / "normalized_tender.json").read_text())
    event = json.loads((fixture_dir / "tender_changed_event.json").read_text())
    jsonschema.Draft202012Validator(record_schema).validate(record)
    jsonschema.Draft202012Validator(event_schema).validate(event)

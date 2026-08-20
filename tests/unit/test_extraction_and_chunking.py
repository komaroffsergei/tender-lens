from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

import pytest

from tender_lens.errors import ExtractionError
from tender_lens.indexer.chunk import chunk_units
from tender_lens.indexer.extract import (
    TextUnit,
    extract_attachment,
    extract_html,
    extract_json,
    extract_pdf,
    extract_txt,
    extract_xml,
    metadata_text,
)
from tender_lens.models import Attachment, Tender


def attachment(path: Path, content_type: str) -> Attachment:
    return Attachment(
        id=UUID(int=2),
        tender_id=UUID(int=1),
        filename=path.name,
        source_url="https://example.test/file",
        local_path=str(path),
        content_type=content_type,
        download_status="ready",
    )


def test_metadata_has_labels():
    tender = Tender(
        id=UUID(int=1),
        source_id=UUID(int=3),
        external_id="x",
        title="Поставка серверов",
        buyer_name="Администрация",
        source_url="https://example.test/tender",
        content_hash="a" * 64,
        raw_payload={},
    )
    text = metadata_text(tender).text
    assert "Название: Поставка серверов" in text
    assert "Заказчик: Администрация" in text


def test_text_pdf_is_extracted(fixture_dir):
    units = extract_pdf(fixture_dir / "sample_tender.pdf", UUID(int=2))
    assert units
    text = " ".join(item.text for item in units).lower()
    assert "server" in text or "сервер" in text


def test_malformed_pdf_raises_typed_error(tmp_path):
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises(ExtractionError):
        extract_pdf(path, UUID(int=2))


def test_xml_does_not_resolve_external_entity():
    payload = b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>'
    with pytest.raises(ExtractionError):
        extract_xml(payload, UUID(int=2))


def test_html_removes_script_and_style():
    units = extract_html(
        b"<h1>Useful</h1><script>steal()</script><style>.x{}</style><p>Text</p>",
        UUID(int=2),
    )
    assert units[0].text == "Useful\nText"


def test_json_and_text_extraction():
    json_units = extract_json(json.dumps({"b": 2, "a": 1}).encode(), UUID(int=2))
    txt_units = extract_txt("Привет".encode(), UUID(int=2))
    assert '"a": 1' in json_units[0].text
    assert txt_units[0].text == "Привет"


def test_unsupported_binary_is_skipped(fixture_dir):
    item = attachment(fixture_dir / "unsupported.bin", "application/octet-stream")
    assert extract_attachment(item, 1024) == []


def test_missing_file_is_typed_error(tmp_path):
    item = attachment(tmp_path / "missing.txt", "text/plain")
    with pytest.raises(ExtractionError):
        extract_attachment(item, 1024)


def test_short_text_creates_one_chunk():
    chunks = chunk_units([TextUnit(None, "s", "Короткий абзац")])
    assert len(chunks) == 1
    assert chunks[0].content == "Короткий абзац"


def test_long_text_respects_limit_and_overlap():
    text = "\n\n".join(f"Абзац {i} " + "данные " * 30 for i in range(20))
    chunks = chunk_units([TextUnit(None, "s", text)], max_chars=300, overlap_chars=40)
    assert len(chunks) > 2
    assert all(len(item.content) <= 300 for item in chunks)
    assert any(
        chunks[index].content[-20:] in chunks[index + 1].content
        for index in range(len(chunks) - 1)
    )


def test_chunking_is_deterministic_and_keeps_unicode():
    units = [TextUnit(None, "Русский", "Серверы и хранилища.\n\nГарантия 36 месяцев.")]
    first = chunk_units(units, max_chars=100, overlap_chars=10)
    second = chunk_units(units, max_chars=100, overlap_chars=10)
    assert first == second
    assert "Гарантия" in " ".join(item.content for item in first)


@pytest.mark.parametrize("max_chars,overlap", [(50, 0), (100, 100), (100, -1)])
def test_invalid_chunk_settings(max_chars, overlap):
    with pytest.raises(ValueError):
        chunk_units([TextUnit(None, "x", "text")], max_chars=max_chars, overlap_chars=overlap)

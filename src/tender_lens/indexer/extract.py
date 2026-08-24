"""Безопасное извлечение текста из ограниченного набора форматов."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from uuid import UUID

from defusedxml import ElementTree
from pypdf import PdfReader

from tender_lens.errors import ExtractionError
from tender_lens.models import Attachment, Tender


@dataclass(frozen=True, slots=True)
class TextUnit:
    attachment_id: UUID | None
    section: str
    text: str


class _SafeHTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag.lower() in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag.lower() in {"p", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)


def metadata_text(tender: Tender) -> TextUnit:
    fields = [
        ("Название", tender.title),
        ("Описание", tender.description),
        ("Заказчик", tender.buyer_name),
        (
            "Сумма",
            f"{tender.amount} {tender.currency or ''}" if tender.amount is not None else None,
        ),
        ("Опубликовано", tender.published_at.isoformat() if tender.published_at else None),
        ("Срок подачи", tender.deadline.isoformat() if tender.deadline else None),
        ("Источник", tender.source_url),
    ]
    text = "\n\n".join(f"{label}: {value}" for label, value in fields if value)
    return TextUnit(attachment_id=None, section="Метаданные закупки", text=text)


def _read_bytes(path: Path, max_bytes: int) -> bytes:
    size = path.stat().st_size
    if size > max_bytes:
        raise ExtractionError(f"Файл больше допустимого лимита извлечения: {size} байт")
    return path.read_bytes()


def extract_pdf(path: Path, attachment_id: UUID) -> list[TextUnit]:
    try:
        reader = PdfReader(str(path))
        units: list[TextUnit] = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                units.append(
                    TextUnit(
                        attachment_id=attachment_id,
                        section=f"PDF, страница {page_number}",
                        text=text,
                    )
                )
        return units
    except Exception as exc:
        raise ExtractionError(f"Не удалось извлечь PDF: {path.name}") from exc


def extract_xml(data: bytes, attachment_id: UUID) -> list[TextUnit]:
    try:
        root = ElementTree.fromstring(data)
    except Exception as exc:
        raise ExtractionError("Некорректный или небезопасный XML.") from exc
    text = "\n".join(part.strip() for part in root.itertext() if part.strip())
    return [TextUnit(attachment_id, "XML document", text)] if text else []


def extract_html(data: bytes, attachment_id: UUID) -> list[TextUnit]:
    parser = _SafeHTMLTextParser()
    parser.feed(data.decode("utf-8", errors="replace"))
    text = parser.text()
    return [TextUnit(attachment_id, "HTML document", text)] if text else []


def extract_json(data: bytes, attachment_id: UUID) -> list[TextUnit]:
    try:
        payload: Any = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtractionError("Некорректный JSON.") from exc
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return [TextUnit(attachment_id, "JSON document", text)]


def extract_txt(data: bytes, attachment_id: UUID) -> list[TextUnit]:
    text = data.decode("utf-8", errors="replace").strip()
    return [TextUnit(attachment_id, "Text document", text)] if text else []


def extract_attachment(attachment: Attachment, max_bytes: int) -> list[TextUnit]:
    if attachment.download_status != "ready" or not attachment.local_path:
        return []
    path = Path(attachment.local_path)
    if not path.exists():
        raise ExtractionError(f"Файл вложения не найден: {path.name}")

    content_type = (attachment.content_type or "").split(";", 1)[0].lower()
    suffix = path.suffix.lower()
    if content_type == "application/pdf" or suffix == ".pdf":
        return extract_pdf(path, attachment.id)

    data = _read_bytes(path, max_bytes)
    if content_type in {"application/xml", "text/xml"} or suffix == ".xml":
        return extract_xml(data, attachment.id)
    if content_type == "text/html" or suffix in {".html", ".htm"}:
        return extract_html(data, attachment.id)
    if content_type == "application/json" or suffix == ".json":
        return extract_json(data, attachment.id)
    if content_type.startswith("text/") or suffix == ".txt":
        return extract_txt(data, attachment.id)
    return []

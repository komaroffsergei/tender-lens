"""Детерминированный paragraph-first chunking без отдельного фреймворка."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from tender_lens.indexer.extract import TextUnit


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    attachment_id: UUID | None
    position: int
    section: str
    content: str


def _paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"\n\s*\n|(?<=\.)\s*\n", normalized)
    return [" ".join(part.split()) for part in parts if part.strip()]


def _split_long(value: str, max_chars: int) -> list[str]:
    if len(value) <= max_chars:
        return [value]
    result: list[str] = []
    start = 0
    while start < len(value):
        end = min(len(value), start + max_chars)
        if end < len(value):
            space = value.rfind(" ", start, end)
            if space > start + max_chars // 2:
                end = space
        result.append(value[start:end].strip())
        start = end
    return [item for item in result if item]


def chunk_units(
    units: list[TextUnit],
    *,
    max_chars: int = 1500,
    overlap_chars: int = 150,
) -> list[ChunkDraft]:
    if max_chars < 100:
        raise ValueError("max_chars слишком мал")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars должен быть меньше max_chars")

    drafts: list[ChunkDraft] = []
    position = 0
    for unit in units:
        paragraphs: list[str] = []
        for paragraph in _paragraphs(unit.text):
            paragraphs.extend(_split_long(paragraph, max_chars))

        current = ""
        for paragraph in paragraphs:
            candidate = paragraph if not current else f"{current}\n\n{paragraph}"
            if len(candidate) <= max_chars:
                current = candidate
                continue

            if current:
                drafts.append(ChunkDraft(unit.attachment_id, position, unit.section, current))
                position += 1
                overlap = current[-overlap_chars:].lstrip() if overlap_chars else ""
                current = f"{overlap}\n\n{paragraph}".strip() if overlap else paragraph
                if len(current) > max_chars:
                    current = current[-max_chars:]
            else:
                drafts.append(ChunkDraft(unit.attachment_id, position, unit.section, paragraph))
                position += 1

        if current:
            drafts.append(ChunkDraft(unit.attachment_id, position, unit.section, current))
            position += 1
    return drafts

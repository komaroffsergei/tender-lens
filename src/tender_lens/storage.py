"""Безопасная потоковая загрузка вложений в локальный volume."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from tender_lens.crawler.base import ResilientHttpClient
from tender_lens.errors import AttachmentError

_SAFE_CHARS = re.compile(r"[^A-Za-zА-Яа-я0-9._ -]+")


@dataclass(frozen=True, slots=True)
class DownloadResult:
    local_path: str
    sha256: str
    size_bytes: int
    content_type: str | None


def safe_filename(value: str) -> str:
    """Удаляет traversal, null byte и опасные символы из внешнего имени."""

    cleaned = value.replace("\x00", "").replace("\\", "/")
    basename = Path(cleaned).name.strip().strip(".")
    basename = _SAFE_CHARS.sub("_", basename)
    basename = re.sub(r"\s+", " ", basename).strip()
    if not basename:
        basename = "attachment.bin"
    stem = Path(basename).stem[:120] or "attachment"
    suffix = Path(basename).suffix[:20]
    return f"{stem}{suffix}"


def attachment_path(root: Path, tender_id: UUID, attachment_id: UUID, filename: str) -> Path:
    directory = root / str(tender_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{attachment_id}_{safe_filename(filename)}"


async def download_attachment(
    *,
    client: ResilientHttpClient,
    url: str,
    root: Path,
    tender_id: UUID,
    attachment_id: UUID,
    filename: str,
    max_bytes: int,
) -> DownloadResult:
    target = attachment_path(root, tender_id, attachment_id, filename)
    temp = target.with_name(f".{target.name}.{uuid4().hex}.part")
    digest = hashlib.sha256()
    size = 0

    try:
        async with client.stream(url) as response:
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = 0
                if declared_size > max_bytes:
                    raise AttachmentError(
                        "attachment_too_large",
                        f"Размер вложения превышает лимит {max_bytes} байт.",
                    )

            with temp.open("wb") as output:
                async for chunk in response.aiter_bytes():
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise AttachmentError(
                            "attachment_too_large",
                            f"Размер вложения превышает лимит {max_bytes} байт.",
                        )
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())

            os.replace(temp, target)
            return DownloadResult(
                local_path=str(target),
                sha256=digest.hexdigest(),
                size_bytes=size,
                content_type=response.headers.get("Content-Type"),
            )
    except Exception:
        temp.unlink(missing_ok=True)
        raise

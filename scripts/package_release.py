#!/usr/bin/env python3
"""Собирает воспроизводимый source ZIP только из отслеживаемых Git файлов."""

from __future__ import annotations

import argparse
import hashlib
import os
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERSION = "0.1.0"
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "data",
    "dist",
}
EXCLUDED_NAMES = {".env", "codex-run.jsonl", "codex-final-report.json"}


def is_allowed_path(relative: str) -> bool:
    """Не допускает runtime, secrets, VCS metadata и путь вне корня архива."""

    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        return False
    if EXCLUDED_PARTS.intersection(path.parts):
        return False
    return path.name not in EXCLUDED_NAMES


def tracked_files(root: Path = ROOT) -> list[Path]:
    """Возвращает детерминированный список файлов, уже включённых в Git."""

    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    relative_paths = [item for item in result.stdout.decode("utf-8").split("\0") if item]
    return [root / item for item in sorted(relative_paths) if is_allowed_path(item)]


def _zip_info(archive_path: str, source: Path | None = None) -> zipfile.ZipInfo:
    """Создаёт стабильную metadata запись; timestamp ZIP намеренно фиксирован."""

    info = zipfile.ZipInfo(archive_path, date_time=(2026, 8, 20, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o644
    if source is not None and os.access(source, os.X_OK):
        mode = 0o755
    info.external_attr = (stat.S_IFREG | mode) << 16
    return info


def build_archive(output: Path, *, version: str = DEFAULT_VERSION) -> Path:
    """Создаёт ZIP и внутренний SHA-256 manifest всех исходных файлов."""

    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = f"tender-lens-{version}"
    manifest: list[str] = []

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in tracked_files():
            relative = source.relative_to(ROOT).as_posix()
            data = source.read_bytes()
            manifest.append(f"{hashlib.sha256(data).hexdigest()}  {relative}")
            archive.writestr(_zip_info(f"{prefix}/{relative}", source), data)

        manifest_data = ("\n".join(manifest) + "\n").encode("utf-8")
        archive.writestr(
            _zip_info(f"{prefix}/RELEASE_MANIFEST.sha256"),
            manifest_data,
        )

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / f"tender-lens-v{DEFAULT_VERSION}.zip",
    )
    args = parser.parse_args()
    archive = build_archive(args.output.resolve(), version=args.version)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    print(f"{archive}\nsha256={digest}")


if __name__ == "__main__":
    main()

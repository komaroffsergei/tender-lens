"""Validate generated docs, exact GitHub line links, and built search content."""

from __future__ import annotations

import json
import re
import struct
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LINK = re.compile(
    r"https://github\.com/komaroffsergei/tender-lens/blob/main/([^\s)#>\"']+)"
    r"(?:#L(\d+)(?:-L(\d+))?)?"
)


def validate_reference() -> list[str]:
    result = subprocess.run(
        [sys.executable, "scripts/generate_code_reference.py", "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        return [result.stdout.strip() or result.stderr.strip()]
    return []


def validate_source_links() -> list[str]:
    errors: list[str] = []
    documents = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    for document in documents:
        content = document.read_text(encoding="utf-8")
        for match in SOURCE_LINK.finditer(content):
            relative = Path(unquote(match.group(1)))
            target = ROOT / relative
            label = f"{document.relative_to(ROOT)}: {match.group(0)}"
            if not target.is_file():
                errors.append(f"Missing source target: {label}")
                continue
            if match.group(2):
                line_count = len(target.read_text(encoding="utf-8").splitlines())
                start = int(match.group(2))
                end = int(match.group(3) or start)
                if start < 1 or end < start or end > line_count:
                    errors.append(f"Invalid line range (file has {line_count}): {label}")
    return errors


def validate_search_index() -> list[str]:
    index_path = ROOT / "site/search/search_index.json"
    if not index_path.exists():
        return ["site/search/search_index.json is missing; run mkdocs build first"]
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    text = json.dumps(payload, ensure_ascii=False).lower()
    required = (
        "crawlerservice",
        "tender.changed.v1",
        "идемпотентность",
        "retry-after",
        "contracts finder",
        "indexerservice.process",
    )
    return [f"Search index misses required term: {term}" for term in required if term not in text]


def validate_dark_theme_tokens() -> list[str]:
    css = (ROOT / "docs/stylesheets/extra.css").read_text(encoding="utf-8")
    match = re.search(r'\[data-md-color-scheme="slate"\]\s*\{([^}]+)\}', css, re.DOTALL)
    if not match:
        return ["Dark documentation palette is missing"]
    required = (
        "--tl-line",
        "--tl-soft",
        "--tl-muted",
        "--tl-ink",
        "--tl-primary",
        "--tl-primary-soft",
        "--tl-green",
    )
    body = match.group(1)
    return [
        f"Dark documentation palette misses token: {token}"
        for token in required
        if token not in body
    ]


def validate_ui_screenshots() -> list[str]:
    """Ensure the published gallery contains real PNG captures at expected viewports."""

    expected_widths = {
        "01-home-desktop.png": 1440,
        "02-loading-desktop.png": 1440,
        "03-search-results-desktop.png": 1440,
        "04-ask-answer-desktop.png": 1440,
        "05-validation-error-desktop.png": 1440,
        "06-search-results-mobile.png": 390,
        "07-ask-answer-mobile.png": 390,
        "08-home-mobile.png": 390,
    }
    root = ROOT / "docs/ui/screenshots"
    errors: list[str] = []
    for name, expected_width in expected_widths.items():
        path = root / name
        if not path.is_file():
            errors.append(f"UI screenshot is missing: {path.relative_to(ROOT)}")
            continue
        data = path.read_bytes()
        if len(data) < 50_000:
            errors.append(f"UI screenshot is unexpectedly small: {path.relative_to(ROOT)}")
            continue
        if data[:8] != b"\x89PNG\r\n\x1a\n" or len(data) < 24:
            errors.append(f"UI screenshot is not a valid PNG: {path.relative_to(ROOT)}")
            continue
        width, height = struct.unpack(">II", data[16:24])
        if width != expected_width or height < 800:
            errors.append(
                f"Unexpected UI screenshot dimensions for {name}: "
                f"{width}x{height}, expected {expected_width}px wide and at least 800px high"
            )
    return errors


def main() -> None:
    errors = (
        validate_reference()
        + validate_source_links()
        + validate_search_index()
        + validate_dark_theme_tokens()
        + validate_ui_screenshots()
    )
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        raise SystemExit(1)
    print("Documentation reference, source links, search index, and UI captures are valid.")


if __name__ == "__main__":
    main()

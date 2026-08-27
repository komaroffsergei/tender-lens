"""Validate generated docs, exact GitHub line links, and built search content."""

from __future__ import annotations

import json
import re
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


def main() -> None:
    errors = (
        validate_reference()
        + validate_source_links()
        + validate_search_index()
        + validate_dark_theme_tokens()
    )
    if errors:
        print("\n".join(f"ERROR: {item}" for item in errors))
        raise SystemExit(1)
    print("Documentation reference, source links, and search index are valid.")


if __name__ == "__main__":
    main()

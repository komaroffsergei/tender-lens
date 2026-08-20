#!/usr/bin/env python3
"""Экспортирует JSON Schema из Pydantic-контрактов без ручного дублирования."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypeAlias

from pydantic import BaseModel

from tender_lens.schemas import TenderChangedV1, TenderRecordV1

ModelType: TypeAlias = type[BaseModel]
ROOT = Path(__file__).resolve().parents[1]
SCHEMAS: dict[str, tuple[ModelType, str]] = {
    "tender-record-v1.schema.json": (
        TenderRecordV1,
        "https://example.local/schemas/tender-record-v1.schema.json",
    ),
    "tender-changed-v1.schema.json": (
        TenderChangedV1,
        "https://example.local/schemas/tender-changed-v1.schema.json",
    ),
}


def build_schema(model: ModelType, schema_id: str) -> dict:
    """Возвращает детерминированную Draft 2020-12 схему для validation contract."""

    generated = model.model_json_schema(mode="validation")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": schema_id,
        **generated,
    }


def export(*, check: bool = False) -> int:
    target_dir = ROOT / "schemas"
    drift: list[str] = []
    for filename, (model, schema_id) in SCHEMAS.items():
        path = target_dir / filename
        expected = build_schema(model, schema_id)
        if check:
            actual = json.loads(path.read_text(encoding="utf-8"))
            if actual != expected:
                drift.append(filename)
            continue
        path.write_text(
            json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if drift:
        print("JSON Schema drift: " + ", ".join(drift))
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="не менять файлы, проверить drift")
    raise SystemExit(export(check=parser.parse_args().check))


if __name__ == "__main__":
    main()

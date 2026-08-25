from __future__ import annotations

import importlib
import json
import logging

import jsonschema
import pytest
from pydantic import ValidationError

from tender_lens.config import Settings
from tender_lens.logging import JsonFormatter, mask_mapping


@pytest.mark.parametrize(
    "module",
    [
        "tender_lens",
        "tender_lens.crawler.__main__",
        "tender_lens.indexer.__main__",
        "tender_lens.api.main",
        "tender_lens.cli",
    ],
)
def test_entrypoints_import_without_external_connections(module):
    assert importlib.import_module(module) is not None


def test_default_settings_are_valid(tmp_path):
    settings = Settings(_env_file=None, attachments_dir=tmp_path)
    assert settings.embedding_dimensions == 1024
    assert settings.embedding_batch_size == 8
    assert settings.ollama_timeout_seconds == 300
    assert settings.min_relevance_score == 0.20
    assert settings.nats_max_deliver == 5
    assert settings.crawl_max_concurrency >= 1
    assert settings.default_rate_limit_per_minute == 5


def test_example_environment_file_is_valid(project_root):
    settings = Settings(_env_file=project_root / ".env.example")
    assert settings.embedding_dimensions == 1024
    assert settings.database_url.endswith("@postgres:5432/tender_lens")


@pytest.mark.parametrize(
    "field,value",
    [
        ("crawl_max_concurrency", 0),
        ("attachment_max_concurrency", 0),
        ("max_attachment_bytes", 10),
        ("default_rate_limit_per_minute", 0),
        ("api_port", 70000),
        ("embedding_dimensions", 768),
        ("embedding_batch_size", 0),
        ("ollama_timeout_seconds", 0),
        ("min_relevance_score", 2),
    ],
)
def test_invalid_settings_are_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_json_formatter_has_required_fields_and_masks_secrets():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="message",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-1"
    payload = json.loads(formatter.format(record))
    assert {"timestamp", "level", "logger", "message", "request_id"} <= payload.keys()
    assert mask_mapping({"api_key": "secret", "nested": {"password": "secret"}}) == {
        "api_key": "***",
        "nested": {"password": "***"},
    }


def test_checked_in_json_schemas_are_current(project_root):
    from scripts.export_schemas import SCHEMAS, build_schema

    for filename, (model, schema_id) in SCHEMAS.items():
        path = project_root / "schemas" / filename
        actual = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(actual)
        assert actual == build_schema(model, schema_id)


def test_required_delivery_files_exist_and_are_nonempty(project_root):
    paths = [
        "README.md",
        "LICENSE",
        "Dockerfile",
        "docker-compose.yml",
        ".github/workflows/ci.yml",
        "docs/architecture.md",
        "docs/algorithm.md",
        "docs/testing.md",
        "docs/operations.md",
        "docs/code-map.md",
        "docs/traceability.md",
        "docs/tradeoffs.md",
    ]
    for relative in paths:
        path = project_root / relative
        assert path.is_file(), relative
        assert path.stat().st_size > 0, relative


def test_static_ui_has_no_remote_dependencies_or_unsafe_rendering(project_root):
    web_dir = project_root / "src" / "tender_lens" / "web"
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(web_dir.iterdir())
        if path.suffix in {".html", ".css", ".js"}
    )
    lowered = combined.lower()
    assert "cdn." not in lowered
    assert "unpkg.com" not in lowered
    assert "jsdelivr" not in lowered
    assert "innerhtml" not in lowered
    assert "hardcoded-api-key" not in lowered
    assert "sessionstorage" in lowered


def test_shell_scripts_have_valid_shebang(project_root):
    for path in (project_root / "scripts").glob("*.sh"):
        assert path.read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")


def test_default_ted_query_uses_current_search_field(tmp_path):
    settings = Settings(_env_file=None, attachments_dir=tmp_path)
    assert "notice-type = cn-standard" in settings.ted_query
    assert "publication-date" in settings.ted_query
    assert "competition-status" not in settings.ted_query

"""Минимальное структурированное логирование без секретов."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any


SENSITIVE_KEYS = {"x-api-key", "api_key", "authorization", "key_hash", "password"}


def mask_mapping(value: dict[str, Any]) -> dict[str, Any]:
    """Рекурсивно маскирует известные секретные поля перед логированием."""

    result: dict[str, Any] = {}
    for key, item in value.items():
        if key.lower() in SENSITIVE_KEYS:
            result[key] = "***"
        elif isinstance(item, dict):
            result[key] = mask_mapping(item)
        else:
            result[key] = item
    return result


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for name in ("request_id", "event_id", "tender_id", "source"):
            if hasattr(record, name):
                payload[name] = getattr(record, name)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(mask_mapping(payload), ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

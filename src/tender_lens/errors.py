"""Типизированные ошибки, переводимые в стабильные HTTP-ответы и логи."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AppError(Exception):
    """Базовая прикладная ошибка без утечки технических деталей наружу."""

    code: str
    message: str
    status_code: int = 500
    details: Any | None = None

    def __str__(self) -> str:
        return self.message


class DependencyUnavailableError(AppError):
    def __init__(self, message: str = "Внешняя зависимость недоступна.") -> None:
        super().__init__("dependency_unavailable", message, 503)


class SourceRequestError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("source_request_failed", message, 502)


class AttachmentError(AppError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 422)


class ExtractionError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("extraction_failed", message, 422)


class InvalidAIResponseError(DependencyUnavailableError):
    def __init__(self, message: str = "AI-сервис вернул некорректный ответ.") -> None:
        super().__init__(message)

"""Типизированная конфигурация приложения без побочных эффектов."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Единый набор настроек для ролей crawler, indexer и API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["local", "test", "production"] = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://tender_lens:tender_lens@localhost:5432/tender_lens"
    nats_url: str = "nats://localhost:4222"
    ollama_url: str = "http://localhost:11434"

    ai_mode: Literal["live", "fake"] = "fake"
    embedding_model: str = "qwen3-embedding:0.6b"
    # Размерность зафиксирована схемой PostgreSQL VECTOR(1024). Тип int нужен,
    # чтобы pydantic-settings мог корректно разобрать строковое значение из .env.
    embedding_dimensions: int = Field(default=1024)
    generation_model: str = "qwen3:1.7b"

    attachments_dir: Path = Path("./data/attachments")
    max_attachment_bytes: int = Field(default=20 * 1024 * 1024, ge=1024)

    crawl_interval_seconds: float = Field(default=3600.0, gt=0)
    crawl_max_concurrency: int = Field(default=3, ge=1, le=32)
    attachment_max_concurrency: int = Field(default=2, ge=1, le=16)
    source_max_items: int = Field(default=20, ge=1, le=1000)

    http_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    http_max_attempts: int = Field(default=3, ge=1, le=10)
    http_base_delay_seconds: float = Field(default=0.5, ge=0, le=60)
    http_jitter_seconds: float = Field(default=0.5, ge=0, le=60)
    user_agent: str = "TenderLens/0.1 (+educational candidate project)"

    default_rate_limit_per_minute: int = Field(default=5, ge=1, le=1000)
    api_host: str = "0.0.0.0"
    api_port: int = Field(default=8000, ge=1, le=65535)

    ted_base_url: str = "https://api.ted.europa.eu"
    ted_query: str = "notice-type = cn-standard SORT BY publication-date DESC"
    ted_page_size: int = Field(default=20, ge=1, le=250)

    contracts_finder_base_url: str = "https://www.contractsfinder.service.gov.uk"
    contracts_finder_page_size: int = Field(default=20, ge=1, le=100)
    contracts_finder_cooldown_seconds: float = Field(default=300.0, ge=0)

    nats_stream_name: str = "TENDERS"
    nats_subject: str = "tender.changed.v1"
    nats_consumer_name: str = "INDEXER"

    @field_validator("ollama_url", "ted_base_url", "contracts_finder_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("embedding_dimensions")
    @classmethod
    def validate_embedding_dimensions(cls, value: int) -> int:
        if value != 1024:
            raise ValueError("embedding_dimensions должна быть равна 1024")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает кэшированный immutable-by-convention объект настроек."""

    return Settings()

"""Pydantic-контракты источников, NATS и HTTP API."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
)


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class AttachmentRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str | None = None
    title: str | None = None
    filename: str = Field(min_length=1, max_length=1024)
    source_url: AnyHttpUrl
    content_type: str | None = None

    @field_validator("external_id", "title", "content_type", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> Any:
        return _empty_to_none(value) if isinstance(value, str) or value is None else value

    @field_validator("filename", mode="before")
    @classmethod
    def normalize_filename(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("filename не может быть пустым")
        return value.strip()


class TenderRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["ted", "contracts_finder"]
    external_id: str = Field(min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=10000)
    description: str | None = None
    buyer_name: str | None = Field(default=None, max_length=5000)
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    published_at: datetime | None = None
    deadline: datetime | None = None
    source_url: AnyHttpUrl
    attachments: list[AttachmentRecordV1] = Field(default_factory=list)
    raw_payload: dict[str, Any]

    @field_validator("external_id", "title", mode="before")
    @classmethod
    def normalize_required_strings(cls, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("обязательная строка не может быть пустой")
        return value.strip()

    @field_validator("description", "buyer_name", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> Any:
        return _empty_to_none(value) if isinstance(value, str) or value is None else value

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency(cls, value: Any) -> str | None:
        normalized = _empty_to_none(value) if isinstance(value, str) or value is None else value
        if normalized is None:
            return None
        normalized = str(normalized).upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency должна содержать три буквы")
        return normalized

    @field_validator("published_at", "deadline")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal | None) -> str | None:
        return None if value is None else format(value, "f")


class TenderChangedV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tender_id: UUID
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("occurred_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=1000)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("query должен содержать не менее трёх символов")
        return stripped


class AttachmentBrief(BaseModel):
    id: UUID
    filename: str


class SearchResult(BaseModel):
    tender_id: UUID
    title: str
    source: str
    source_url: AnyHttpUrl
    snippet: str
    score: float = Field(ge=-1.0, le=1.0)
    attachment: AttachmentBrief | None = None


class SearchResponse(BaseModel):
    query: str
    items: list[SearchResult]


class AskResponse(BaseModel):
    answer: str
    sources: list[SearchResult]


class AttachmentDetails(BaseModel):
    id: UUID
    filename: str
    title: str | None
    content_type: str | None
    size_bytes: int | None
    download_status: str


class TenderDetails(BaseModel):
    id: UUID
    source: str
    external_id: str
    title: str
    description: str | None
    buyer_name: str | None
    amount: Decimal | None
    currency: str | None
    published_at: datetime | None
    deadline: datetime | None
    source_url: AnyHttpUrl
    index_status: str
    attachments: list[AttachmentDetails]

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal | None) -> str | None:
        return None if value is None else format(value, ".2f")


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: Any | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody

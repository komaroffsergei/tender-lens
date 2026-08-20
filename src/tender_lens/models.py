"""Пять SQLAlchemy-моделей, утверждённых спецификацией MVP."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType

try:
    from pgvector.sqlalchemy import VECTOR
except ImportError:  # pragma: no cover - нужен только в урезанной среде локального анализа

    class VECTOR(UserDefinedType):  # type: ignore[no-redef]
        cache_ok = True

        def __init__(self, dimensions: int) -> None:
            self.dimensions = dimensions

        def get_col_spec(self, **_: Any) -> str:
            return f"VECTOR({self.dimensions})"


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Общая declarative base без runtime-побочных эффектов."""


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    cursor: Mapped[str | None] = mapped_column(sa.Text)
    last_sync_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now, server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=sa.func.now(),
        nullable=False,
    )

    tenders: Mapped[list["Tender"]] = relationship(back_populates="source")


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (
        sa.UniqueConstraint("source_id", "external_id", name="uq_tenders_source_external"),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_tenders_amount_nonnegative"),
        sa.CheckConstraint(
            "index_status IN ('pending','processing','ready','failed')",
            name="ck_tenders_index_status",
        ),
        sa.Index("ix_tenders_published_at", sa.desc("published_at")),
        sa.Index("ix_tenders_deadline", "deadline"),
        sa.Index("ix_tenders_index_status", "index_status"),
        sa.Index("ix_tenders_content_hash", "content_hash"),
    )

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text)
    buyer_name: Mapped[str | None] = mapped_column(sa.Text)
    amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(20, 2))
    currency: Mapped[str | None] = mapped_column(sa.String(3))
    published_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    deadline: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    source_url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    indexed_hash: Mapped[str | None] = mapped_column(sa.CHAR(64))
    index_status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default="pending", server_default="pending"
    )
    last_error: Mapped[str | None] = mapped_column(sa.Text)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now, server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=sa.func.now(),
        nullable=False,
    )

    source: Mapped[Source] = relationship(back_populates="tenders")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan"
    )


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (
        sa.UniqueConstraint("tender_id", "source_url", name="uq_attachments_tender_url"),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_attachment_size"),
        sa.CheckConstraint(
            "download_status IN ('pending','ready','failed','skipped')",
            name="ck_attachments_download_status",
        ),
        sa.Index("ix_attachments_tender_id", "tender_id"),
        sa.Index("ix_attachments_sha256", "sha256"),
    )

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tender_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(sa.Text)
    title: Mapped[str | None] = mapped_column(sa.Text)
    filename: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    local_path: Mapped[str | None] = mapped_column(sa.Text)
    content_type: Mapped[str | None] = mapped_column(sa.Text)
    sha256: Mapped[str | None] = mapped_column(sa.CHAR(64))
    size_bytes: Mapped[int | None] = mapped_column(sa.BigInteger)
    download_status: Mapped[str] = mapped_column(
        sa.String(16), nullable=False, default="pending", server_default="pending"
    )
    error_message: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now, server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=sa.func.now(),
        nullable=False,
    )

    tender: Mapped[Tender] = relationship(back_populates="attachments")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="attachment")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        sa.CheckConstraint("position >= 0", name="ck_chunks_position"),
        sa.CheckConstraint("length(content) > 0", name="ck_chunks_content"),
        sa.Index("ix_chunks_tender_id", "tender_id"),
        sa.Index("ix_chunks_attachment_id", "attachment_id"),
    )

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    tender_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False
    )
    attachment_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("attachments.id", ondelete="CASCADE")
    )
    chunk_key: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False, unique=True)
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(sa.Text)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(1024), nullable=False)
    embedding_model: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now, server_default=sa.func.now(), nullable=False
    )

    tender: Mapped[Tender] = relationship(back_populates="chunks")
    attachment: Mapped[Attachment | None] = relationship(back_populates="chunks")


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        sa.CheckConstraint(
            "limit_per_minute BETWEEN 1 AND 1000", name="ck_api_keys_limit_range"
        ),
        sa.CheckConstraint("request_count >= 0", name="ck_api_keys_request_count"),
    )

    id: Mapped[UUID] = mapped_column(sa.Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    key_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=True, server_default=sa.true()
    )
    limit_per_minute: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=5, server_default="5"
    )
    window_started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0, server_default="0"
    )
    last_used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=utc_now, server_default=sa.func.now(), nullable=False
    )

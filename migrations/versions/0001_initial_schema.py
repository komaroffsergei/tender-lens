"""Создание минимальной схемы TenderLens.

Revision ID: 0001
Revises: None
Create Date: 2026-08-20
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("key_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("limit_per_minute", sa.Integer(), server_default="5", nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "limit_per_minute BETWEEN 1 AND 1000", name="ck_api_keys_limit_range"
        ),
        sa.CheckConstraint("request_count >= 0", name="ck_api_keys_request_count"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )

    op.create_table(
        "tenders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("buyer_name", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("indexed_hash", sa.CHAR(length=64), nullable=True),
        sa.Column("index_status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_tenders_amount_nonnegative"),
        sa.CheckConstraint(
            "index_status IN ('pending','processing','ready','failed')",
            name="ck_tenders_index_status",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_id", name="uq_tenders_source_external"),
    )
    op.create_index("ix_tenders_published_at", "tenders", [sa.text("published_at DESC")])
    op.create_index("ix_tenders_deadline", "tenders", ["deadline"])
    op.create_index("ix_tenders_index_status", "tenders", ["index_status"])
    op.create_index("ix_tenders_content_hash", "tenders", ["content_hash"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "download_status",
            sa.String(length=16),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="ck_attachment_size"),
        sa.CheckConstraint(
            "download_status IN ('pending','ready','failed','skipped')",
            name="ck_attachments_download_status",
        ),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tender_id", "source_url", name="uq_attachments_tender_url"),
    )
    op.create_index("ix_attachments_tender_id", "attachments", ["tender_id"])
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("attachment_id", sa.Uuid(), nullable=True),
        sa.Column("chunk_key", sa.CHAR(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("embedding", VECTOR(dim=1024), nullable=False),
        sa.Column("embedding_model", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("position >= 0", name="ck_chunks_position"),
        sa.CheckConstraint("length(content) > 0", name="ck_chunks_content"),
        sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_key"),
    )
    op.create_index("ix_chunks_tender_id", "chunks", ["tender_id"])
    op.create_index("ix_chunks_attachment_id", "chunks", ["attachment_id"])


def downgrade() -> None:
    op.drop_index("ix_chunks_attachment_id", table_name="chunks")
    op.drop_index("ix_chunks_tender_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_attachments_sha256", table_name="attachments")
    op.drop_index("ix_attachments_tender_id", table_name="attachments")
    op.drop_table("attachments")
    op.drop_index("ix_tenders_content_hash", table_name="tenders")
    op.drop_index("ix_tenders_index_status", table_name="tenders")
    op.drop_index("ix_tenders_deadline", table_name="tenders")
    op.drop_index("ix_tenders_published_at", table_name="tenders")
    op.drop_table("tenders")
    op.drop_table("api_keys")
    op.drop_table("sources")

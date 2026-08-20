"""Служебные команды: API-ключи, demo seed и проверка зависимостей."""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from tender_lens.api.auth import generate_api_key
from tender_lens.config import get_settings
from tender_lens.db import create_engine, create_session_factory
from tender_lens.hashing import tender_content_hash
from tender_lens.models import ApiKey, Attachment, Source, Tender
from tender_lens.nats import NatsBroker
from tender_lens.schemas import TenderChangedV1, TenderRecordV1
from tender_lens.storage import attachment_path


async def create_key(name: str, limit: int) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    generated = generate_api_key()
    async with sessions() as session:
        row = ApiKey(
            name=name,
            key_hash=generated.key_hash,
            limit_per_minute=limit,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    await engine.dispose()
    print(
        json.dumps(
            {
                "id": str(row.id),
                "name": row.name,
                "api_key": generated.secret,
                "limit_per_minute": row.limit_per_minute,
                "warning": "Открытый ключ показан один раз и не хранится в базе.",
            },
            ensure_ascii=False,
        )
    )


async def disable_key(identifier: str) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    async with sessions() as session:
        row: ApiKey | None
        try:
            row = await session.get(ApiKey, UUID(identifier))
        except ValueError:
            row = await session.scalar(select(ApiKey).where(ApiKey.name == identifier))
        if row is None:
            raise SystemExit("API-ключ не найден")
        row.enabled = False
        await session.commit()
        print(json.dumps({"id": str(row.id), "name": row.name, "enabled": False}))
    await engine.dispose()


async def list_keys() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    async with sessions() as session:
        rows = (await session.scalars(select(ApiKey).order_by(ApiKey.created_at))).all()
        payload = [
            {
                "id": str(row.id),
                "name": row.name,
                "enabled": row.enabled,
                "limit_per_minute": row.limit_per_minute,
                "request_count": row.request_count,
                "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
            }
            for row in rows
        ]
    await engine.dispose()
    print(json.dumps(payload, ensure_ascii=False))


async def _upsert_demo_record(
    record: TenderRecordV1,
    fixture_file: Path,
    sessions,
) -> tuple[UUID, str]:
    content_hash = tender_content_hash(record)
    async with sessions() as session:
        source = await session.scalar(select(Source).where(Source.code == record.source))
        if source is None:
            source = Source(code=record.source)
            session.add(source)
            await session.flush()
        tender = await session.scalar(
            select(Tender).where(
                Tender.source_id == source.id,
                Tender.external_id == record.external_id,
            )
        )
        if tender is None:
            tender = Tender(
                source_id=source.id,
                external_id=record.external_id,
                title=record.title,
                description=record.description,
                buyer_name=record.buyer_name,
                amount=record.amount,
                currency=record.currency,
                published_at=record.published_at,
                deadline=record.deadline,
                source_url=str(record.source_url),
                content_hash=content_hash,
                raw_payload=record.raw_payload,
                index_status="pending",
            )
            session.add(tender)
            await session.flush()
        else:
            tender.title = record.title
            tender.description = record.description
            tender.buyer_name = record.buyer_name
            tender.amount = record.amount
            tender.currency = record.currency
            tender.published_at = record.published_at
            tender.deadline = record.deadline
            tender.source_url = str(record.source_url)
            tender.raw_payload = record.raw_payload
            tender.content_hash = content_hash
            tender.index_status = "pending"
            tender.last_error = None

        attachment_record = record.attachments[0]
        attachment = await session.scalar(
            select(Attachment).where(
                Attachment.tender_id == tender.id,
                Attachment.source_url == str(attachment_record.source_url),
            )
        )
        if attachment is None:
            attachment = Attachment(
                tender_id=tender.id,
                external_id=attachment_record.external_id,
                title=attachment_record.title,
                filename=attachment_record.filename,
                source_url=str(attachment_record.source_url),
                content_type=attachment_record.content_type,
                download_status="pending",
            )
            session.add(attachment)
            await session.flush()

        target = attachment_path(
            get_settings().attachments_dir,
            tender.id,
            attachment.id,
            attachment.filename,
        )
        shutil.copyfile(fixture_file, target)
        data = target.read_bytes()
        import hashlib

        attachment.local_path = str(target)
        attachment.sha256 = hashlib.sha256(data).hexdigest()
        attachment.size_bytes = len(data)
        attachment.download_status = "ready"
        attachment.error_message = None
        await session.commit()
        return tender.id, content_hash


def _demo_records(fixture_dir: Path) -> list[tuple[TenderRecordV1, Path]]:
    ted = TenderRecordV1.model_validate_json(
        (fixture_dir / "normalized_tender.json").read_text(encoding="utf-8")
    )
    cf_payload = json.loads((fixture_dir / "contracts_finder_ocds.json").read_text())
    from tender_lens.crawler.contracts_finder import ContractsFinderAdapter

    cf = ContractsFinderAdapter.map_release(cf_payload["releases"][0])
    return [
        (ted, fixture_dir / "sample_tender.pdf"),
        (cf, fixture_dir / "sample_tender.pdf"),
    ]


async def seed_demo(fixture_dir: Path) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    broker = NatsBroker(settings)
    await broker.connect()
    inserted: list[str] = []
    try:
        for record, fixture_file in _demo_records(fixture_dir):
            tender_id, content_hash = await _upsert_demo_record(record, fixture_file, sessions)
            event = TenderChangedV1(tender_id=tender_id, content_hash=content_hash)
            await broker.publish_tender_changed(event)
            inserted.append(str(tender_id))
    finally:
        await broker.close()
        await engine.dispose()
    print(json.dumps({"seeded_tenders": inserted}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TenderLens maintenance CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-api-key")
    create.add_argument("--name", required=True)
    create.add_argument("--limit", type=int, default=5, choices=range(1, 1001), metavar="1..1000")

    disable = sub.add_parser("disable-api-key")
    disable.add_argument("identifier", help="UUID или name")

    sub.add_parser("list-api-keys")

    seed = sub.add_parser("seed-demo")
    seed.add_argument("--fixture-dir", type=Path, default=Path("examples/fixtures"))
    return parser


async def async_main(args: argparse.Namespace) -> None:
    if args.command == "create-api-key":
        await create_key(args.name, args.limit)
    elif args.command == "disable-api-key":
        await disable_key(args.identifier)
    elif args.command == "list-api-keys":
        await list_keys()
    elif args.command == "seed-demo":
        await seed_demo(args.fixture_dir)


def main() -> None:
    asyncio.run(async_main(build_parser().parse_args()))


if __name__ == "__main__":
    main()

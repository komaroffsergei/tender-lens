"""Public demo boundary: synthetic corpus, signed expiring sessions, bounded queue replay."""

from __future__ import annotations

import asyncio
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import time
from typing import Callable
from uuid import uuid4

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from tender_lens.api.auth import hash_api_key
from tender_lens.api.rate_limit import rate_limited_key
from tender_lens.models import ApiKey, Chunk, Tender
from tender_lens.nats import NatsBroker
from tender_lens.schemas import AttachmentRecordV1, TenderChangedV1, TenderRecordV1


class PortfolioRateGate:
    """Process-wide fixed-window cap protecting paid public AI endpoints."""

    def __init__(self, limit: int, clock: Callable[[], float] = time) -> None:
        self._limit = limit
        self._clock = clock
        self._window = int(clock() // 60)
        self._requests = 0
        self._lock = asyncio.Lock()

    async def consume(self) -> int | None:
        now = self._clock()
        minute = int(now // 60)
        async with self._lock:
            if minute != self._window:
                self._window = minute
                self._requests = 0
            if self._requests >= self._limit:
                return max(1, 60 - int(now % 60))
            self._requests += 1
            return None


async def cleanup(sessions):
    async with sessions() as session:
        await session.execute(
            delete(ApiKey).where(
                ApiKey.name == "portfolio-demo",
                ApiKey.created_at < datetime.now(UTC) - timedelta(hours=1),
            )
        )
        await session.commit()


async def cleanup_loop(sessions):
    while True:
        await cleanup(sessions)
        await asyncio.sleep(300)


def install_demo(application, settings):
    if not settings.portfolio_demo:
        return
    if settings.ai_mode not in {"fake", "mws"} or len(settings.portfolio_secret) < 32:
        raise RuntimeError("Public demo requires fake or MWS AI and a session signing secret")
    global_rate_gate = PortfolioRateGate(settings.portfolio_global_rate_limit_per_minute)

    @application.middleware("http")
    async def session_context(request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        if request.url.path in {"/api/v1/search", "/api/v1/ask"}:
            retry_after = await global_rate_gate.consume()
            if retry_after is not None:
                return JSONResponse(
                    {
                        "error": {
                            "code": "portfolio_rate_limited",
                            "message": "Общий лимит демо исчерпан. Повторите позже.",
                        }
                    },
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
        token = request.cookies.get("portfolio_tenders", "")
        parts = token.split(".")
        valid = (
            len(parts) == 3
            and len(parts[0]) == 48
            and parts[1].isdigit()
            and int(parts[1]) > time()
            and hmac.compare_digest(
                hmac.new(
                    settings.portfolio_secret.encode(), ".".join(parts[:2]).encode(), "sha256"
                ).hexdigest(),
                parts[2],
            )
        )
        if not valid:
            raw = secrets.token_hex(24) + "." + str(int(time()) + 3600)
            token = (
                raw
                + "."
                + hmac.new(settings.portfolio_secret.encode(), raw.encode(), "sha256").hexdigest()
            )
        key_hash = hash_api_key(token)
        async with request.app.state.session_factory() as session:
            exists = await session.scalar(select(ApiKey.id).where(ApiKey.key_hash == key_hash))
            if not exists:
                if (await session.scalar(select(func.count()).select_from(ApiKey))) >= 1000:
                    return JSONResponse(
                        {"error": {"message": "Демо занято. Повторите позже."}}, 429
                    )
                await session.execute(
                    insert(ApiKey)
                    .values(
                        id=uuid4(),
                        name="portfolio-demo",
                        key_hash=key_hash,
                        limit_per_minute=settings.default_rate_limit_per_minute,
                    )
                    .on_conflict_do_nothing(index_elements=["key_hash"])
                )
                await session.commit()
        request.state.portfolio_key = token
        response = await call_next(request)
        if not valid:
            response.set_cookie(
                "portfolio_tenders", token, max_age=3600, secure=True, httponly=True, samesite="lax"
            )
        return response

    @application.get("/api/demo/status")
    async def status(request: Request):
        async with request.app.state.session_factory() as session:
            rows = (await session.scalars(select(Tender).order_by(Tender.external_id))).all()
            chunks = await session.scalar(select(func.count()).select_from(Chunk))
            if settings.ai_mode == "mws":
                ai = {
                    "mode": "mws",
                    "provider": "MWS Model Hub",
                    "embeddings": settings.mws_embedding_model,
                    "generation": settings.mws_generation_model,
                }
                mock = []
                real = [
                    "MWS embeddings",
                    "MWS grounded generation",
                    "NATS JetStream",
                    "extraction",
                    "chunking",
                    "PostgreSQL pgvector",
                    "cosine search",
                ]
            else:
                ai = {
                    "mode": "fake",
                    "provider": "deterministic local test provider",
                    "embeddings": "hashing trick",
                    "generation": "template response",
                }
                mock = ["hash embeddings", "template LLM"]
                real = [
                    "NATS JetStream",
                    "extraction",
                    "chunking",
                    "PostgreSQL pgvector",
                    "cosine search",
                ]
            return {
                "at": datetime.now(UTC).isoformat(),
                "source": "PostgreSQL: tenders + chunks",
                "chunks": chunks,
                "documents": [
                    {
                        "title": x.title,
                        "status": x.index_status,
                        "url": x.source_url,
                        "updated_at": x.updated_at.isoformat(),
                    }
                    for x in rows
                ],
                "ai": ai,
                "synthetic": ["four public demo documents"],
                "mock": mock,
                "real": real,
            }

    @application.post("/api/demo/replay", dependencies=[Depends(rate_limited_key)])
    async def replay(request: Request):
        async with request.app.state.session_factory() as session:
            rows = (await session.scalars(select(Tender))).all()
        broker = NatsBroker(settings)
        await broker.connect()
        try:
            for row in rows:
                await broker.publish_tender_changed(
                    TenderChangedV1(tender_id=row.id, content_hash=row.content_hash)
                )
        finally:
            await broker.close()
        return {
            "queued": len(rows),
            "at": datetime.now(UTC).isoformat(),
            "message": (
                "События доставлены в настоящую NATS-очередь. Worker проверяет хеш "
                "и пропускает уже готовый неизменённый документ."
            ),
        }


CORPUS = [
    (
        "servers",
        "Серверы и гарантия 36 месяцев",
        (
            "Синтетическая закупка: серверы для учебного центра. Требуются серверы, "
            "256 ГБ оперативной памяти, SSD 4 ТБ, два блока питания. Гарантия 36 месяцев. "
            "Поставка в течение 45 дней. Приёмка включает тест памяти и проверку RAID. "
            "Документ создан для демонстрации; реального заказчика нет."
        ),
    ),
    (
        "backup",
        "Резервное копирование и восстановление",
        (
            "Синтетическая закупка: резервное копирование учебной инфраструктуры. "
            "Ежедневные копии, хранение 30 дней, шифрование и проверка восстановления "
            "раз в месяц. RPO 24 часа и RTO 4 часа — условия вымышленного примера. "
            "Исполнитель передаёт инструкции и журнал учебного восстановления."
        ),
    ),
    (
        "portal",
        "Разработка Angular-портала",
        (
            "Синтетическая закупка: Angular TypeScript портал заявок. Формы с валидацией, "
            "таблицы с фильтрами, роли администратора и оператора, REST API. Нужны "
            "адаптивный интерфейс, unit и e2e проверки, документация API. "
            "Срок демонстрационного проекта 60 дней. Реальная закупка не проводится."
        ),
    ),
    (
        "network",
        "Мониторинг сети и оборудования",
        (
            "Синтетическая закупка: мониторинг сети учебного стенда. SNMP метрики "
            "оборудования, графики CPU и памяти, уведомления при недоступности узла. "
            "Хранение агрегатов 90 дней. Предусмотрены контроль доступа, журнал изменений "
            "и инструкция по эксплуатации."
        ),
    ),
]


async def seed():
    from tender_lens.cli import _upsert_demo_record
    from tender_lens.config import get_settings
    from tender_lens.db import create_engine, create_session_factory

    settings = get_settings()
    engine = create_engine(settings)
    sessions = create_session_factory(engine)
    broker = NatsBroker(settings)
    await broker.connect()
    try:
        for index, (slug, title, body) in enumerate(CORPUS):
            url = "https://tenders.komaroff-dev.ru/static/demo/" + slug + ".html"
            file = Path(__file__).parent / "web/demo" / f"{slug}.html"
            record = TenderRecordV1(
                source="ted" if index % 2 == 0 else "contracts_finder",
                external_id="DEMO-" + slug,
                title=title,
                description=body,
                buyer_name="Учебный центр (синтетический)",
                amount=100000 + index * 25000,
                currency="RUB",
                published_at="2026-09-01T00:00:00Z",
                source_url=url,
                attachments=[
                    AttachmentRecordV1(
                        filename=slug + ".html", source_url=url, content_type="text/html"
                    )
                ],
                raw_payload={"synthetic": True},
            )
            tender_id, content_hash = await _upsert_demo_record(record, file, sessions)
            await broker.publish_tender_changed(
                TenderChangedV1(tender_id=tender_id, content_hash=content_hash)
            )
    finally:
        await broker.close()
        await engine.dispose()
    print("Four synthetic documents queued for real indexing")


if __name__ == "__main__":
    asyncio.run(seed())

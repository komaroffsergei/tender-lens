"""Тонкие HTTP routes: валидация, зависимости и вызов сервисов."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from tender_lens.api.auth import authenticate_api_key, get_session
from tender_lens.api.rate_limit import rate_limited_key
from tender_lens.errors import AppError
from tender_lens.models import Tender
from tender_lens.schemas import (
    AskResponse,
    AttachmentDetails,
    SearchRequest,
    SearchResponse,
    TenderDetails,
)

router = APIRouter()


@router.get("/health/live", tags=["health"])
async def live_health() -> dict[str, str]:
    return {"status": "ok", "service": "api"}


@router.get("/health/ready", tags=["health"])
async def ready_health(request: Request) -> JSONResponse:
    dependencies = {"postgres": False, "ai": False}
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
            dependencies["postgres"] = True
    except Exception:
        dependencies["postgres"] = False
    try:
        dependencies["ai"] = await request.app.state.ai.health()
    except Exception:
        dependencies["ai"] = False

    ready = all(dependencies.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ready" if ready else "unavailable", "dependencies": dependencies},
    )


@router.get(
    "/api/v1/tenders/{tender_id}",
    response_model=TenderDetails,
    dependencies=[Depends(authenticate_api_key)],
    tags=["tenders"],
)
async def tender_details(tender_id: UUID, session=Depends(get_session)) -> TenderDetails:
    tender = await session.scalar(
        select(Tender)
        .where(Tender.id == tender_id)
        .options(selectinload(Tender.source), selectinload(Tender.attachments))
    )
    if tender is None:
        raise AppError("not_found", "Закупка не найдена.", 404)
    return TenderDetails(
        id=tender.id,
        source=tender.source.code,
        external_id=tender.external_id,
        title=tender.title,
        description=tender.description,
        buyer_name=tender.buyer_name,
        amount=tender.amount,
        currency=tender.currency,
        published_at=tender.published_at,
        deadline=tender.deadline,
        source_url=tender.source_url,
        index_status=tender.index_status,
        attachments=[
            AttachmentDetails(
                id=item.id,
                filename=item.filename,
                title=item.title,
                content_type=item.content_type,
                size_bytes=item.size_bytes,
                download_status=item.download_status,
            )
            for item in tender.attachments
        ],
    )


@router.post(
    "/api/v1/search",
    response_model=SearchResponse,
    dependencies=[Depends(rate_limited_key)],
    tags=["search"],
)
async def search(request: Request, payload: SearchRequest, session=Depends(get_session)):
    response = await request.app.state.search_service.search(session, payload.query, payload.limit)
    headers = request.state.rate_limit.headers
    return JSONResponse(content=response.model_dump(mode="json"), headers=headers)


@router.post(
    "/api/v1/ask",
    response_model=AskResponse,
    dependencies=[Depends(rate_limited_key)],
    tags=["search"],
)
async def ask(request: Request, payload: SearchRequest, session=Depends(get_session)):
    response = await request.app.state.search_service.ask(session, payload.query, payload.limit)
    headers = request.state.rate_limit.headers
    return JSONResponse(content=response.model_dump(mode="json"), headers=headers)

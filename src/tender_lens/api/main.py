"""App factory, lifecycle, middleware, errors и статический интерфейс."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from tender_lens.ai import AIProvider, FakeAIProvider, OllamaAIProvider
from tender_lens.api.routes import router
from tender_lens.config import Settings, get_settings
from tender_lens.db import SessionFactory, create_engine, create_session_factory
from tender_lens.errors import AppError
from tender_lens.logging import configure_logging
from tender_lens.schemas import ErrorBody, ErrorResponse
from tender_lens.search import SearchService

logger = logging.getLogger(__name__)
WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def _error_response(request: Request, error: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    details = error.details
    headers: dict[str, str] = {}
    if isinstance(details, dict) and isinstance(details.get("headers"), dict):
        headers = {str(key): str(value) for key, value in details["headers"].items()}
        details = None
    body = ErrorResponse(
        error=ErrorBody(
            code=error.code,
            message=error.message,
            request_id=request_id,
            details=details,
        )
    )
    return JSONResponse(
        status_code=error.status_code,
        content=body.model_dump(mode="json"),
        headers=headers,
    )


def create_app(
    *,
    settings: Settings | None = None,
    session_factory: SessionFactory | Any | None = None,
    ai: AIProvider | None = None,
    search_service: Any | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    owns_engine = session_factory is None
    owns_ai = ai is None

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = None
        actual_sessions = session_factory
        actual_ai = ai
        if actual_sessions is None:
            engine = create_engine(settings)
            actual_sessions = create_session_factory(engine)
        if actual_ai is None:
            actual_ai = (
                FakeAIProvider(settings.embedding_dimensions)
                if settings.ai_mode == "fake"
                else OllamaAIProvider(
                    base_url=settings.ollama_url,
                    embedding_model=settings.embedding_model,
                    generation_model=settings.generation_model,
                    dimensions=settings.embedding_dimensions,
                )
            )
        application.state.settings = settings
        application.state.session_factory = actual_sessions
        application.state.ai = actual_ai
        application.state.search_service = search_service or SearchService(
            actual_ai, settings.min_relevance_score
        )
        yield
        if owns_ai and isinstance(actual_ai, OllamaAIProvider):
            await actual_ai.aclose()
        if owns_engine and engine is not None:
            await engine.dispose()

    application = FastAPI(
        title="TenderLens API",
        version="0.2.0",
        description="Поиск и grounded RAG по открытым закупкам.",
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, error: AppError) -> JSONResponse:
        return _error_response(request, error)

    @application.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, error: RequestValidationError) -> JSONResponse:
        app_error = AppError(
            "validation_error",
            "Запрос не прошёл валидацию.",
            422,
            details=[
                {key: value for key, value in item.items() if key not in {"ctx", "url"}}
                for item in error.errors()
            ],
        )
        return _error_response(request, app_error)

    @application.exception_handler(Exception)
    async def internal_handler(request: Request, error: Exception) -> JSONResponse:
        logger.exception(
            "Необработанная ошибка API",
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        return _error_response(
            request,
            AppError("internal_error", "Внутренняя ошибка сервиса.", 500),
        )

    application.include_router(router)
    application.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @application.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    return application


app = create_app()

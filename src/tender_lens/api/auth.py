"""Проверка X-API-Key без сохранения открытого секрета."""

from __future__ import annotations

import hashlib
import secrets
from typing import cast
from dataclasses import dataclass, field

from fastapi import Header, Request
from sqlalchemy import select

from tender_lens.errors import AppError
from tender_lens.models import ApiKey


@dataclass(frozen=True, slots=True)
class GeneratedApiKey:
    secret: str = field(repr=False)
    key_hash: str


def hash_api_key(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_api_key() -> GeneratedApiKey:
    secret = f"tl_{secrets.token_urlsafe(32)}"
    return GeneratedApiKey(secret=secret, key_hash=hash_api_key(secret))


async def get_session(request: Request):
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session


async def authenticate_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> ApiKey:
    if not x_api_key:
        raise AppError("api_key_required", "Требуется заголовок X-API-Key.", 401)
    key_hash = hash_api_key(x_api_key)
    factory = request.app.state.session_factory
    async with factory() as session:
        api_key = cast(
            ApiKey | None,
            await session.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash)),
        )
        if api_key is None:
            raise AppError("api_key_invalid", "API-ключ не найден.", 401)
        if api_key.enabled is False:
            raise AppError("api_key_disabled", "API-ключ отключён.", 403)
        # Сравнение сохраняет одинаковую ветвь выполнения после поиска по hash.
        if not secrets.compare_digest(api_key.key_hash, key_hash):
            raise AppError("api_key_invalid", "API-ключ не найден.", 401)
        session.expunge(api_key)
        return api_key

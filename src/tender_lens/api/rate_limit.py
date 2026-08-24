"""Fixed UTC-minute limiter в одной атомарной PostgreSQL-транзакции."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tender_lens.api.auth import authenticate_api_key
from tender_lens.errors import AppError
from tender_lens.models import ApiKey


@dataclass(frozen=True, slots=True)
class RateLimitState:
    limit: int
    remaining: int
    reset_at: datetime

    @property
    def headers(self) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(int(self.reset_at.timestamp())),
        }

    def exceeded_headers(self, now: datetime) -> dict[str, str]:
        retry_after = max(1, ceil((self.reset_at - now).total_seconds()))
        return {**self.headers, "Retry-After": str(retry_after)}


def minute_start(now: datetime) -> datetime:
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return now.astimezone(UTC).replace(second=0, microsecond=0)


async def consume_rate_limit(
    session: AsyncSession,
    api_key_id: UUID,
    *,
    now: datetime | None = None,
) -> RateLimitState:
    current = now or datetime.now(UTC)
    window = minute_start(current)
    reset_at = window + timedelta(minutes=1)
    api_key = await session.get(ApiKey, api_key_id, with_for_update=True)
    if api_key is None or api_key.enabled is False:
        raise AppError("api_key_invalid", "API-ключ не найден.", 401)

    if api_key.window_started_at is None or minute_start(api_key.window_started_at) != window:
        api_key.window_started_at = window
        api_key.request_count = 0

    if api_key.request_count >= api_key.limit_per_minute:
        limit = api_key.limit_per_minute
        await session.rollback()
        state = RateLimitState(limit, 0, reset_at)
        raise AppError(
            "rate_limit_exceeded",
            "Превышен лимит запросов.",
            429,
            details={"headers": state.exceeded_headers(current)},
        )

    api_key.request_count += 1
    api_key.last_used_at = current
    remaining = max(0, api_key.limit_per_minute - api_key.request_count)
    await session.commit()
    return RateLimitState(api_key.limit_per_minute, remaining, reset_at)


async def rate_limited_key(
    request: Request,
    api_key: ApiKey = Depends(authenticate_api_key),
):
    factory = request.app.state.session_factory
    async with factory() as session:
        state = await consume_rate_limit(session, api_key.id)
    request.state.rate_limit = state
    return api_key

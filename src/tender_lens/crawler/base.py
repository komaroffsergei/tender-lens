"""Общий контракт источника и безопасная HTTP-политика crawler."""

from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from ipaddress import ip_address
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

import httpx

from tender_lens.errors import SourceRequestError
from tender_lens.schemas import TenderRecordV1


@dataclass(frozen=True, slots=True)
class SourcePage:
    """Одна подтверждаемая порция данных внешнего источника."""

    records: list[TenderRecordV1]
    next_cursor: str | None


class SourceAdapter(Protocol):
    source_code: str

    async def fetch_page(self, cursor: str | None, limit: int) -> SourcePage:
        """Получить и нормализовать одну страницу/итерацию источника."""

        ...


class ResilientHttpClient:
    """HTTP-клиент с bounded concurrency, retry и проверкой redirect host."""

    def __init__(
        self,
        *,
        max_concurrency: int,
        timeout_seconds: float,
        max_attempts: int,
        base_delay_seconds: float,
        jitter_seconds: float,
        user_agent: str,
        allowed_hosts: set[str],
        forbidden_cooldown_seconds: float | None = None,
        client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_value: Callable[[], float] = random.random,
    ) -> None:
        self._semaphore = asyncio.BoundedSemaphore(max_concurrency)
        self._timeout = timeout_seconds
        self._max_attempts = max_attempts
        self._base_delay = base_delay_seconds
        self._jitter = jitter_seconds
        self._allowed_hosts = {host.lower() for host in allowed_hosts}
        self._forbidden_cooldown = forbidden_cooldown_seconds
        self._sleep = sleep
        self._random = random_value
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"User-Agent": user_agent, "Accept": "application/json, */*"},
            follow_redirects=False,
        )

    async def __aenter__(self) -> "ResilientHttpClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _validate_host(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise SourceRequestError(f"Недопустимый URL: {url}")
        hostname = parsed.hostname.lower()
        if hostname == "localhost" or hostname.endswith((".localhost", ".local")):
            raise SourceRequestError(f"Локальный host запрещён политикой crawler: {hostname}")
        try:
            address = ip_address(hostname)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise SourceRequestError(f"Локальный IP запрещён политикой crawler: {hostname}")
        if hostname not in self._allowed_hosts:
            raise SourceRequestError(f"Host не разрешён политикой crawler: {parsed.hostname}")

    def _is_retryable_status(self, status_code: int) -> bool:
        statuses = {429, 500, 502, 503, 504}
        return status_code in statuses or (
            status_code == 403 and self._forbidden_cooldown is not None
        )

    def _retry_delay(self, response: httpx.Response | None, attempt: int) -> float:
        if (
            response is not None
            and response.status_code == 403
            and self._forbidden_cooldown is not None
        ):
            return self._forbidden_cooldown
        if response is not None:
            raw = response.headers.get("Retry-After")
            if raw:
                try:
                    return max(0.0, float(raw))
                except ValueError:
                    try:
                        retry_at = parsedate_to_datetime(raw)
                    except (TypeError, ValueError, OverflowError):
                        retry_at = None
                    if retry_at is not None:
                        if retry_at.tzinfo is None:
                            retry_at = retry_at.replace(tzinfo=UTC)
                        return float(max(0.0, (retry_at - datetime.now(UTC)).total_seconds()))
        exponential = self._base_delay * (2 ** max(0, attempt - 1))
        return float(exponential + self._jitter * self._random())

    async def _polite_delay(self) -> None:
        delay = self._base_delay + self._jitter * self._random()
        if delay > 0:
            await self._sleep(delay)

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self._validate_host(url)
        current_url = url
        redirects = 0
        last_error: Exception | None = None
        attempt = 1

        while attempt <= self._max_attempts:
            await self._polite_delay()
            try:
                async with self._semaphore:
                    response = await self._client.request(
                        method,
                        current_url,
                        timeout=self._timeout,
                        follow_redirects=False,
                        **kwargs,
                    )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt == self._max_attempts:
                    break
                await self._sleep(self._retry_delay(None, attempt))
                attempt += 1
                continue

            if response.is_redirect:
                location = response.headers.get("Location")
                if not location:
                    raise SourceRequestError("Redirect без заголовка Location")
                redirects += 1
                if redirects > 5:
                    raise SourceRequestError("Превышено число redirect")
                current_url = urljoin(str(response.url), location)
                self._validate_host(current_url)
                # Redirect не является повторной попыткой после сбоя.
                continue

            if self._is_retryable_status(response.status_code):
                if attempt == self._max_attempts:
                    raise SourceRequestError(
                        f"Источник ответил HTTP {response.status_code} после {attempt} попыток"
                    )
                await self._sleep(self._retry_delay(response, attempt))
                attempt += 1
                continue

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise SourceRequestError(f"Источник ответил HTTP {response.status_code}") from exc
            return response

        raise SourceRequestError(
            f"Не удалось обратиться к источнику после {self._max_attempts} попыток"
        ) from last_error

    async def get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        response = await self.request("GET", url, **kwargs)
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceRequestError("Источник вернул некорректный JSON") from exc
        if not isinstance(payload, dict):
            raise SourceRequestError("Корень JSON источника должен быть объектом")
        return payload

    async def post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self.request("POST", url, json=payload)
        try:
            result = response.json()
        except ValueError as exc:
            raise SourceRequestError("Источник вернул некорректный JSON") from exc
        if not isinstance(result, dict):
            raise SourceRequestError("Корень JSON источника должен быть объектом")
        return result

    @asynccontextmanager
    async def stream(self, url: str) -> AsyncIterator[httpx.Response]:
        """Открыть поток и удерживать semaphore до завершения чтения."""

        self._validate_host(url)
        last_error: Exception | None = None
        current_url = url
        redirects = 0
        attempt = 1

        while attempt <= self._max_attempts:
            await self._polite_delay()
            await self._semaphore.acquire()
            response: httpx.Response | None = None
            retry_delay: float | None = None
            try:
                request = self._client.build_request("GET", current_url)
                response = await self._client.send(
                    request,
                    stream=True,
                    follow_redirects=False,
                )

                if response.is_redirect:
                    location = response.headers.get("Location")
                    if not location:
                        raise SourceRequestError("Redirect без заголовка Location")
                    redirects += 1
                    if redirects > 5:
                        raise SourceRequestError("Превышено число redirect")
                    current_url = urljoin(str(response.url), location)
                    self._validate_host(current_url)
                    # Redirect не расходует лимит retry; следующий URL всё равно
                    # проходит полную проверку схемы и host.
                    continue
                elif self._is_retryable_status(response.status_code):
                    if attempt == self._max_attempts:
                        raise SourceRequestError(
                            f"Загрузка файла завершилась HTTP {response.status_code}"
                        )
                    retry_delay = self._retry_delay(response, attempt)
                    attempt += 1
                else:
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        raise SourceRequestError(
                            f"Загрузка файла завершилась HTTP {exc.response.status_code}"
                        ) from exc
                    try:
                        yield response
                    finally:
                        await response.aclose()
                        response = None
                    return
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < self._max_attempts:
                    retry_delay = self._retry_delay(None, attempt)
                    attempt += 1
            finally:
                if response is not None:
                    await response.aclose()
                self._semaphore.release()

            if retry_delay is not None:
                await self._sleep(retry_delay)
                continue
            break

        raise SourceRequestError("Не удалось открыть поток вложения") from last_error

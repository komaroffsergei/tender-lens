from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from uuid import UUID

import httpx
import pytest

from tender_lens.crawler.base import ResilientHttpClient
from tender_lens.errors import AttachmentError, SourceRequestError
from tender_lens.storage import download_attachment, safe_filename


async def no_sleep(_: float):
    return None


def make_client(
    raw,
    max_concurrency=2,
    attempts=3,
    sleep=no_sleep,
    forbidden_cooldown_seconds=None,
):
    return ResilientHttpClient(
        max_concurrency=max_concurrency,
        timeout_seconds=1,
        max_attempts=attempts,
        base_delay_seconds=0,
        jitter_seconds=0,
        user_agent="test",
        allowed_hosts={"example.test"},
        forbidden_cooldown_seconds=forbidden_cooldown_seconds,
        client=raw,
        sleep=sleep,
    )


@pytest.mark.parametrize(
    "value,expected",
    [
        ("../../secret.pdf", "secret.pdf"),
        ("C:\\temp\\x.pdf", "x.pdf"),
        ("..", "attachment.bin"),
        ("a\x00b?.pdf", "ab_.pdf"),
    ],
)
def test_safe_filename(value, expected):
    assert safe_filename(value) == expected


@pytest.mark.asyncio
async def test_http_concurrency_is_bounded():
    active = 0
    maximum = 0
    lock = asyncio.Lock()

    async def handler(request):
        nonlocal active, maximum
        async with lock:
            active += 1
            maximum = max(maximum, active)
        await asyncio.sleep(0.02)
        async with lock:
            active -= 1
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        client = make_client(raw, max_concurrency=2, attempts=1)
        await asyncio.gather(
            *(client.get_json("https://example.test/data") for _ in range(8))
        )
    assert maximum <= 2


@pytest.mark.asyncio
async def test_retry_after_is_respected():
    attempts = 0
    sleeps = []

    async def fake_sleep(value):
        sleeps.append(value)

    async def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        result = await make_client(raw, sleep=fake_sleep).get_json("https://example.test/data")
    assert result == {"ok": True}
    assert 2.0 in sleeps


@pytest.mark.asyncio
async def test_optional_403_cooldown_is_respected():
    attempts = 0
    sleeps = []

    async def fake_sleep(value):
        sleeps.append(value)

    async def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(403)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        result = await make_client(
            raw,
            sleep=fake_sleep,
            forbidden_cooldown_seconds=17.0,
        ).get_json("https://example.test/data")

    assert result == {"ok": True}
    assert 17.0 in sleeps


@pytest.mark.asyncio
async def test_403_without_source_cooldown_is_not_retried():
    attempts = 0

    async def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        with pytest.raises(SourceRequestError):
            await make_client(raw).get_json("https://example.test/data")

    assert attempts == 1


@pytest.mark.asyncio
async def test_network_timeout_is_retried_then_fails():
    attempts = 0

    async def handler(request):
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timeout", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        with pytest.raises(SourceRequestError):
            await make_client(raw, attempts=2).get_json("https://example.test/data")
    assert attempts == 2


@pytest.mark.asyncio
async def test_redirect_to_unknown_host_is_rejected():
    async def handler(request):
        return httpx.Response(302, headers={"Location": "https://evil.test/file"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        with pytest.raises(SourceRequestError, match="Host"):
            await make_client(raw, attempts=1).get_json("https://example.test/data")


@pytest.mark.asyncio
async def test_invalid_json_is_typed_error():
    async def handler(request):
        return httpx.Response(200, text="not-json")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        with pytest.raises(SourceRequestError, match="JSON"):
            await make_client(raw, attempts=1).get_json("https://example.test/data")


@pytest.mark.asyncio
async def test_stream_download_success(tmp_path):
    data = b"hello tender"

    async def handler(request):
        return httpx.Response(
            200,
            content=data,
            headers={"Content-Type": "application/pdf", "Content-Length": str(len(data))},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        result = await download_attachment(
            client=make_client(raw, attempts=1),
            url="https://example.test/spec.pdf",
            root=tmp_path,
            tender_id=UUID(int=1),
            attachment_id=UUID(int=2),
            filename="../../spec.pdf",
            max_bytes=1024,
        )
    assert Path(result.local_path).read_bytes() == data
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert result.content_type == "application/pdf"


@pytest.mark.asyncio
async def test_declared_large_attachment_fails_before_write(tmp_path):
    async def handler(request):
        return httpx.Response(200, content=b"x", headers={"Content-Length": "9999"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        with pytest.raises(AttachmentError):
            await download_attachment(
                client=make_client(raw, attempts=1),
                url="https://example.test/file",
                root=tmp_path,
                tender_id=UUID(int=1),
                attachment_id=UUID(int=2),
                filename="x.bin",
                max_bytes=10,
            )
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.asyncio
async def test_stream_over_limit_removes_temp_file(tmp_path):
    async def handler(request):
        return httpx.Response(200, content=b"12345678901")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        with pytest.raises(AttachmentError):
            await download_attachment(
                client=make_client(raw, attempts=1),
                url="https://example.test/file",
                root=tmp_path,
                tender_id=UUID(int=1),
                attachment_id=UUID(int=2),
                filename="x.bin",
                max_bytes=10,
            )
    assert not list(tmp_path.rglob("*.part"))
    assert not list(tmp_path.rglob("*.bin"))


@pytest.mark.asyncio
async def test_redirect_to_allowed_host_is_followed():
    paths = []

    async def handler(request):
        paths.append(request.url.path)
        if request.url.path == "/start":
            return httpx.Response(302, headers={"Location": "/final"})
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        result = await make_client(raw, attempts=2).get_json(
            "https://example.test/start"
        )

    assert result == {"ok": True}
    assert paths == ["/start", "/final"]

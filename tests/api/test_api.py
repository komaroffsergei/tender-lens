from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import Request
from fastapi.testclient import TestClient

from tender_lens.ai import FakeAIProvider
from tender_lens.api.auth import authenticate_api_key, get_session, hash_api_key
from tender_lens.api.main import create_app
from tender_lens.api.rate_limit import RateLimitState, rate_limited_key
from tender_lens.config import Settings
from tender_lens.models import ApiKey, Attachment, Source, Tender
from tender_lens.schemas import SearchResult
from tender_lens.search import InMemorySearchService


class FakeSession:
    def __init__(self, api_key: ApiKey | None = None, execute_error: Exception | None = None):
        self.api_key = api_key
        self.execute_error = execute_error
        self.commits = 0
        self.rollbacks = 0

    async def scalar(self, statement):
        del statement
        return self.api_key

    async def get(self, model, identifier, with_for_update=False):
        del model, with_for_update
        if self.api_key is not None and self.api_key.id == identifier:
            return self.api_key
        return None

    async def execute(self, statement, params=None):
        del statement, params
        if self.execute_error:
            raise self.execute_error
        return object()

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    def expunge(self, value):
        del value


class FakeContext(AbstractAsyncContextManager):
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return FakeContext(self.session)


def item() -> SearchResult:
    return SearchResult(
        tender_id=UUID(int=10),
        title="Supply of server equipment",
        source="ted",
        source_url="https://example.test/tender",
        snippet="Rack servers, storage and warranty for 36 months.",
        score=0.91,
    )


def make_client(api_key: ApiKey | None, *, search_service=None, execute_error=None):
    session = FakeSession(api_key, execute_error=execute_error)
    app = create_app(
        settings=Settings(ai_mode="fake", embedding_dimensions=1024),
        session_factory=FakeFactory(session),
        ai=FakeAIProvider(64),
        search_service=search_service or InMemorySearchService([item()], "Grounded answer"),
    )
    return TestClient(app, raise_server_exceptions=False), app, session


def enabled_key(limit=5):
    return ApiKey(
        id=UUID(int=1),
        name="demo",
        key_hash=hash_api_key("tl_test"),
        enabled=True,
        limit_per_minute=limit,
        request_count=0,
    )


def test_live_health_does_not_require_dependencies():
    client, _, _ = make_client(None, execute_error=RuntimeError("db down"))
    with client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}
    assert response.headers["X-Request-ID"]


def test_ready_health_success():
    client, _, _ = make_client(enabled_key())
    with client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["dependencies"] == {"postgres": True, "ai": True}


def test_ready_health_db_failure_is_503():
    client, _, _ = make_client(enabled_key(), execute_error=RuntimeError("db down"))
    with client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["dependencies"]["postgres"] is False


def test_missing_api_key_is_401():
    client, _, _ = make_client(enabled_key())
    with client:
        response = client.post("/api/v1/search", json={"query": "server"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "api_key_required"


def test_unknown_api_key_is_401():
    client, _, _ = make_client(None)
    with client:
        response = client.post(
            "/api/v1/search",
            headers={"X-API-Key": "tl_unknown"},
            json={"query": "server"},
        )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "api_key_invalid"


def test_disabled_api_key_is_403():
    key = enabled_key()
    key.enabled = False
    client, _, _ = make_client(key)
    with client:
        response = client.post(
            "/api/v1/search",
            headers={"X-API-Key": "tl_test"},
            json={"query": "server"},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "api_key_disabled"


def test_search_contract_and_rate_headers():
    client, _, _ = make_client(enabled_key())
    with client:
        response = client.post(
            "/api/v1/search",
            headers={"X-API-Key": "tl_test"},
            json={"query": "server equipment", "limit": 5},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "server equipment"
    assert body["items"][0]["source"] == "ted"
    assert "raw_payload" not in body["items"][0]
    assert response.headers["X-RateLimit-Limit"] == "5"
    assert response.headers["X-RateLimit-Remaining"] == "4"


def test_search_and_ask_share_counter_and_sixth_is_429():
    client, _, session = make_client(enabled_key(limit=5))
    headers = {"X-API-Key": "tl_test"}
    with client:
        statuses = []
        for index in range(6):
            endpoint = "/api/v1/search" if index % 2 == 0 else "/api/v1/ask"
            statuses.append(
                client.post(endpoint, headers=headers, json={"query": "server"}).status_code
            )
    assert statuses == [200, 200, 200, 200, 200, 429]
    assert session.api_key.request_count == 5


def test_validation_error_is_stable():
    client, _, _ = make_client(enabled_key())
    with client:
        response = client.post(
            "/api/v1/search",
            headers={"X-API-Key": "tl_test"},
            json={"query": "  "},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_static_ui_and_assets_are_local(project_root):
    client, _, _ = make_client(None)
    with client:
        page = client.get("/")
        css = client.get("/static/styles.css")
        js = client.get("/static/app.js")
    assert page.status_code == css.status_code == js.status_code == 200
    assert "<title>TenderLens</title>" in page.text
    assert 'src="http' not in page.text.lower()
    assert 'href="http' not in page.text.lower()
    assert "innerHTML" not in js.text
    assert "tl_demo" not in page.text + js.text


def test_openapi_contains_required_routes():
    client, _, _ = make_client(enabled_key())
    with client:
        document = client.get("/openapi.json").json()
    paths = document["paths"]
    assert "/api/v1/search" in paths
    assert "/api/v1/ask" in paths
    assert "/api/v1/tenders/{tender_id}" in paths


class TenderSession:
    def __init__(self, tender):
        self.tender = tender

    async def scalar(self, statement):
        del statement
        return self.tender


async def allow_auth():
    return enabled_key()


async def allow_rate(request: Request):
    request.state.rate_limit = RateLimitState(
        limit=5,
        remaining=4,
        reset_at=datetime(2099, 1, 1, tzinfo=UTC),
    )
    return enabled_key()


def test_tender_details_are_sanitized():
    source = Source(id=UUID(int=2), code="ted")
    tender = Tender(
        id=UUID(int=3),
        source_id=source.id,
        external_id="123",
        title="Tender",
        description="Description",
        buyer_name="Buyer",
        amount=Decimal("12.50"),
        currency="EUR",
        source_url="https://example.test/tender",
        content_hash="a" * 64,
        index_status="ready",
        raw_payload={"secret_external_noise": True},
    )
    tender.source = source
    tender.attachments = [
        Attachment(
            id=UUID(int=4),
            tender_id=tender.id,
            filename="spec.pdf",
            source_url="https://example.test/spec.pdf",
            local_path="/private/path/spec.pdf",
            download_status="ready",
        )
    ]

    client, app, _ = make_client(enabled_key())

    async def tender_session_override():
        yield TenderSession(tender)

    app.dependency_overrides[authenticate_api_key] = allow_auth
    app.dependency_overrides[get_session] = tender_session_override
    with client:
        response = client.get(f"/api/v1/tenders/{tender.id}", headers={"X-API-Key": "x"})
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] == "12.50"
    assert "raw_payload" not in body
    assert "local_path" not in body["attachments"][0]


def test_unknown_tender_is_404():
    client, app, _ = make_client(enabled_key())

    async def empty_session_override():
        yield TenderSession(None)

    app.dependency_overrides[authenticate_api_key] = allow_auth
    app.dependency_overrides[get_session] = empty_session_override
    with client:
        response = client.get(
            f"/api/v1/tenders/{UUID(int=99)}", headers={"X-API-Key": "x"}
        )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_internal_exception_is_hidden():
    class BrokenSearch:
        async def search(self, session: Any, query: str, limit: int):
            del session, query, limit
            raise RuntimeError("database password=secret")

        async def ask(self, session: Any, query: str, limit: int):
            del session, query, limit
            raise RuntimeError("secret")

    client, app, _ = make_client(enabled_key(), search_service=BrokenSearch())
    app.dependency_overrides[rate_limited_key] = allow_rate

    async def dummy_session():
        yield object()

    app.dependency_overrides[get_session] = dummy_session
    with client:
        response = client.post(
            "/api/v1/search",
            headers={"X-API-Key": "x"},
            json={"query": "server"},
        )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "password" not in response.text

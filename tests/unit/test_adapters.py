from __future__ import annotations

import json

import httpx
import pytest

from tender_lens.crawler.base import ResilientHttpClient
from tender_lens.crawler.contracts_finder import ContractsFinderAdapter
from tender_lens.crawler.ted import TedAdapter


def no_sleep(_: float):
    async def done():
        return None

    return done()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_ted_fixture_mapping(fixture_dir):
    notice = load(fixture_dir / "ted_search_response.json")["notices"][0]
    record = TedAdapter.map_notice(notice)
    assert record.source == "ted"
    assert record.external_id == "123456-2026"
    assert record.currency == "EUR"
    assert {item.content_type for item in record.attachments} == {
        "application/pdf",
        "application/xml",
    }


def test_contracts_finder_fixture_mapping(fixture_dir):
    release = load(fixture_dir / "contracts_finder_ocds.json")["releases"][0]
    record = ContractsFinderAdapter.map_release(release)
    assert record.source == "contracts_finder"
    assert record.external_id == "CF-EXAMPLE-001"
    assert record.buyer_name == "Example Borough Council"
    assert record.attachments[0].filename == "specification.pdf"


@pytest.mark.parametrize(
    "mapper,fixture_name,collection",
    [
        (TedAdapter.map_notice, "ted_search_response.json", "notices"),
        (ContractsFinderAdapter.map_release, "contracts_finder_ocds.json", "releases"),
    ],
)
def test_common_adapter_contract(mapper, fixture_name, collection, fixture_dir):
    record = mapper(load(fixture_dir / fixture_name)[collection][0])
    assert record.external_id
    assert record.title
    assert str(record.source_url).startswith("http")
    assert record.amount is None or record.amount >= 0
    assert record.published_at is None or record.published_at.tzinfo is not None
    assert all(str(item.source_url).startswith("http") for item in record.attachments)
    json.dumps(record.raw_payload)


def test_missing_optional_contracts_finder_fields_are_none(fixture_dir):
    release = load(fixture_dir / "contracts_finder_ocds.json")["releases"][0]
    release["buyer"] = None
    release["tender"].pop("value")
    release["tender"].pop("tenderPeriod")
    record = ContractsFinderAdapter.map_release(release)
    assert record.buyer_name is None
    assert record.amount is None
    assert record.deadline is None


@pytest.mark.asyncio
async def test_ted_request_uses_iteration_token_and_caps_limit(fixture_dir):
    fixture = load(fixture_dir / "ted_search_response.json")
    captured = {}

    async def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=fixture)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        client = ResilientHttpClient(
            max_concurrency=1,
            timeout_seconds=1,
            max_attempts=1,
            base_delay_seconds=0,
            jitter_seconds=0,
            user_agent="test",
            allowed_hosts={"api.ted.europa.eu"},
            client=raw,
            sleep=no_sleep,
        )
        page = await TedAdapter(
            client, base_url="https://api.ted.europa.eu", query="test"
        ).fetch_page("token", 999)
    assert captured["iterationNextToken"] == "token"
    assert captured["limit"] == 250
    assert page.records


@pytest.mark.asyncio
async def test_contracts_finder_uses_cursor_and_limit(fixture_dir):
    fixture = load(fixture_dir / "contracts_finder_ocds.json")
    captured = {}

    async def handler(request):
        captured.update(dict(request.url.params))
        return httpx.Response(200, json=fixture)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        client = ResilientHttpClient(
            max_concurrency=1,
            timeout_seconds=1,
            max_attempts=1,
            base_delay_seconds=0,
            jitter_seconds=0,
            user_agent="test",
            allowed_hosts={"www.contractsfinder.service.gov.uk"},
            client=raw,
            sleep=no_sleep,
        )
        page = await ContractsFinderAdapter(
            client, base_url="https://www.contractsfinder.service.gov.uk"
        ).fetch_page("cursor-1", 500)
    assert captured["cursor"] == "cursor-1"
    assert captured["limit"] == "100"
    assert page.next_cursor == "next-example"


@pytest.mark.asyncio
async def test_ted_invalid_notice_is_skipped_and_logged(fixture_dir, caplog):
    fixture = load(fixture_dir / "ted_search_response.json")
    fixture["notices"] = [
        {"publication-number": "broken-without-title"},
        fixture["notices"][0],
    ]

    async def handler(request):
        return httpx.Response(200, json=fixture)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        client = ResilientHttpClient(
            max_concurrency=1,
            timeout_seconds=1,
            max_attempts=1,
            base_delay_seconds=0,
            jitter_seconds=0,
            user_agent="test",
            allowed_hosts={"api.ted.europa.eu"},
            client=raw,
            sleep=no_sleep,
        )
        page = await TedAdapter(
            client,
            base_url="https://api.ted.europa.eu",
            query="test",
        ).fetch_page(None, 10)

    assert len(page.records) == 1
    assert page.records[0].external_id == "123456-2026"
    assert "TED notice пропущен" in caplog.text


@pytest.mark.asyncio
async def test_contracts_finder_invalid_release_is_skipped_and_logged(fixture_dir, caplog):
    fixture = load(fixture_dir / "contracts_finder_ocds.json")
    fixture["releases"] = [
        {"tender": {"id": "broken-without-title"}},
        fixture["releases"][0],
    ]

    async def handler(request):
        return httpx.Response(200, json=fixture)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        client = ResilientHttpClient(
            max_concurrency=1,
            timeout_seconds=1,
            max_attempts=1,
            base_delay_seconds=0,
            jitter_seconds=0,
            user_agent="test",
            allowed_hosts={"www.contractsfinder.service.gov.uk"},
            client=raw,
            sleep=no_sleep,
        )
        page = await ContractsFinderAdapter(
            client,
            base_url="https://www.contractsfinder.service.gov.uk",
        ).fetch_page(None, 10)

    assert len(page.records) == 1
    assert page.records[0].external_id == "CF-EXAMPLE-001"
    assert "Contracts Finder release пропущен" in caplog.text


@pytest.mark.asyncio
async def test_empty_source_pages_return_no_records():
    async def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"notices": []})
        return httpx.Response(200, json={"releases": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        ted_client = ResilientHttpClient(
            max_concurrency=1,
            timeout_seconds=1,
            max_attempts=1,
            base_delay_seconds=0,
            jitter_seconds=0,
            user_agent="test",
            allowed_hosts={"api.ted.europa.eu"},
            client=raw,
            sleep=no_sleep,
        )
        cf_client = ResilientHttpClient(
            max_concurrency=1,
            timeout_seconds=1,
            max_attempts=1,
            base_delay_seconds=0,
            jitter_seconds=0,
            user_agent="test",
            allowed_hosts={"www.contractsfinder.service.gov.uk"},
            client=raw,
            sleep=no_sleep,
        )
        ted_page = await TedAdapter(
            ted_client,
            base_url="https://api.ted.europa.eu",
            query="test",
        ).fetch_page(None, 10)
        cf_page = await ContractsFinderAdapter(
            cf_client,
            base_url="https://www.contractsfinder.service.gov.uk",
        ).fetch_page(None, 10)

    assert ted_page.records == []
    assert cf_page.records == []


def test_ted_maps_current_search_api_fields():
    record = TedAdapter.map_notice(
        {
            "publication-number": "765432-2026",
            "notice-title": {"eng": "Current API notice"},
            "buyer-name": {"eng": "Example authority"},
            "publication-date": "2026-08-20T08:00:00Z",
            "deadline-receipt-request": "2026-09-15T12:00:00Z",
            "estimated-value-proc": "123456.78",
            "estimated-value-cur-proc": "EUR",
            "description-proc": {"eng": "Supply of storage systems"},
            "links": {"html": "https://ted.europa.eu/example"},
        }
    )

    assert record.external_id == "765432-2026"
    assert record.title == "Current API notice"
    assert record.description == "Supply of storage systems"
    assert str(record.amount) == "123456.78"
    assert record.currency == "EUR"
    assert record.published_at is not None
    assert record.deadline is not None


@pytest.mark.asyncio
async def test_ted_requests_only_current_official_field_names():
    captured = {}

    async def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"notices": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as raw:
        client = ResilientHttpClient(
            max_concurrency=1,
            timeout_seconds=1,
            max_attempts=1,
            base_delay_seconds=0,
            jitter_seconds=0,
            user_agent="test",
            allowed_hosts={"api.ted.europa.eu"},
            client=raw,
            sleep=no_sleep,
        )
        await TedAdapter(
            client,
            base_url="https://api.ted.europa.eu",
            query="notice-type = cn-standard",
        ).fetch_page(None, 10)

    assert "publication-date" in captured["fields"]
    assert "description-proc" in captured["fields"]
    assert "estimated-value-proc" in captured["fields"]
    assert "notice-publication-date" not in captured["fields"]
    assert "description-procurement" not in captured["fields"]

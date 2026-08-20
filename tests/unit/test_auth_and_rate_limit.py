from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from tender_lens.api.auth import generate_api_key, hash_api_key
from tender_lens.api.rate_limit import consume_rate_limit, minute_start
from tender_lens.errors import AppError
from tender_lens.models import ApiKey


class FakeSession:
    def __init__(self, row):
        self.row = row
        self.commits = 0
        self.rollbacks = 0

    async def get(self, model, identifier, with_for_update=False):
        del model, with_for_update
        return self.row if self.row.id == identifier else None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def test_generated_key_has_prefix_entropy_and_matching_hash():
    first = generate_api_key()
    second = generate_api_key()
    assert first.secret.startswith("tl_")
    assert len(first.secret) > 35
    assert first.secret != second.secret
    assert first.key_hash == hash_api_key(first.secret)
    assert first.secret not in repr(first)


def test_minute_start_is_utc_and_truncated():
    result = minute_start(datetime(2026, 8, 20, 10, 11, 59, 999, tzinfo=UTC))
    assert result == datetime(2026, 8, 20, 10, 11, tzinfo=UTC)


@pytest.mark.asyncio
async def test_first_five_requests_pass_and_sixth_fails():
    row = ApiKey(id=UUID(int=1), name="demo", key_hash="a" * 64, limit_per_minute=5)
    session = FakeSession(row)
    now = datetime(2026, 8, 20, 10, 11, 1, tzinfo=UTC)
    for expected_remaining in [4, 3, 2, 1, 0]:
        state = await consume_rate_limit(session, row.id, now=now)
        assert state.remaining == expected_remaining
    with pytest.raises(AppError) as captured:
        await consume_rate_limit(session, row.id, now=now)
    assert captured.value.status_code == 429
    assert row.request_count == 5


@pytest.mark.asyncio
async def test_counter_resets_in_new_utc_minute():
    row = ApiKey(
        id=UUID(int=1),
        name="demo",
        key_hash="a" * 64,
        limit_per_minute=5,
        request_count=5,
        window_started_at=datetime(2026, 8, 20, 10, 11, tzinfo=UTC),
    )
    state = await consume_rate_limit(
        FakeSession(row), row.id, now=datetime(2026, 8, 20, 10, 12, 2, tzinfo=UTC)
    )
    assert state.remaining == 4
    assert row.request_count == 1


@pytest.mark.asyncio
async def test_two_keys_have_independent_state():
    now = datetime(2026, 8, 20, 10, 11, tzinfo=UTC)
    first = ApiKey(id=UUID(int=1), name="a", key_hash="a" * 64, limit_per_minute=2)
    second = ApiKey(id=UUID(int=2), name="b", key_hash="b" * 64, limit_per_minute=2)
    await consume_rate_limit(FakeSession(first), first.id, now=now)
    state = await consume_rate_limit(FakeSession(second), second.id, now=now)
    assert first.request_count == 1
    assert second.request_count == 1
    assert state.remaining == 1

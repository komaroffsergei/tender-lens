from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from tender_lens.nats import NatsBroker
from tender_lens.schemas import TenderChangedV1

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_jetstream_publish_consume_and_ack(integration_settings):
    broker = NatsBroker(integration_settings)
    await broker.connect()
    event = TenderChangedV1(tender_id=UUID(int=1), content_hash="a" * 64)
    await broker.publish_tender_changed(event)
    iterator = broker.iter_messages(timeout=0.2)
    message = await asyncio.wait_for(anext(iterator), timeout=5)
    parsed = TenderChangedV1.model_validate_json(message.data)
    assert parsed.event_id == event.event_id
    await message.ack()
    await iterator.aclose()
    await broker.close()


@pytest.mark.asyncio
async def test_stream_initialization_is_idempotent(integration_settings):
    first = NatsBroker(integration_settings)
    second = NatsBroker(integration_settings)
    await first.connect()
    await second.connect()
    await first.ensure_stream()
    await second.ensure_stream()
    await first.close()
    await second.close()

from __future__ import annotations

import pytest

from tender_lens.nats import NatsMessage


class RawMessage:
    data = b"payload"

    def __init__(self) -> None:
        self.actions: list[tuple[str, float | None]] = []

    async def ack(self) -> None:
        self.actions.append(("ack", None))

    async def nak(self, delay: float | None = None) -> None:
        self.actions.append(("nak", delay))

    async def term(self) -> None:
        self.actions.append(("term", None))


@pytest.mark.asyncio
async def test_message_supports_ack_retry_and_permanent_termination():
    raw = RawMessage()
    message = NatsMessage(raw)

    await message.ack()
    await message.nak(delay=10)
    await message.term()

    assert raw.actions == [("ack", None), ("nak", 10), ("term", None)]

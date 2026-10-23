from unittest.mock import AsyncMock

import pytest

from donats.handlers import DonatEventHandler
from tests.units.test_schemas import DONATIONS_ALERTS_PAYLOAD


class _HandlerError(Exception):
    pass


async def test_on_message_propagates_handler_error() -> None:
    handler = DonatEventHandler(sender=None, admin='admin')
    handler.handle_event = AsyncMock(side_effect=_HandlerError('boom'))

    with pytest.raises(_HandlerError):
        await handler.on_message(DONATIONS_ALERTS_PAYLOAD)


async def test_on_message_formats_donations_alerts_payload() -> None:
    sender = AsyncMock()
    handler = DonatEventHandler(sender=sender, admin='gunlinux')

    await handler.on_message(DONATIONS_ALERTS_PAYLOAD)

    sender.send_message.assert_awaited_once()
    text = sender.send_message.await_args.args[0]
    assert 'test555' in text
    assert '555' in text
    assert 'RUB' in text

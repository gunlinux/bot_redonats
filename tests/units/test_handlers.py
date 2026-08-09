from unittest.mock import AsyncMock, Mock

import pytest

from donats.handlers import DonatEventHandler


class _HandlerError(Exception):
    pass


async def test_on_message_propagates_handler_error() -> None:
    handler = DonatEventHandler(sender=None, admin='admin')
    handler.handle_event = AsyncMock(side_effect=_HandlerError('boom'))

    with pytest.raises(_HandlerError):
        await handler.on_message(Mock())

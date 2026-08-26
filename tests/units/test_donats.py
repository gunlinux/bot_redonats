import json
from unittest.mock import AsyncMock

import aiohttp
import pytest

from donats.donats import DonatApi

CENTRIFUGO_DONATION = {
    'id': 30530030,
    'name': 'donation',
    'username': 'Ivan',
    'message_type': 'text',
    'message': 'Hello!',
    'amount': 500,
    'currency': 'RUB',
    'is_shown': 1,
    'created_at': '2019-09-29 09:00:00',
    'shown_at': None,
}


class _Msg:
    type = aiohttp.WSMsgType.TEXT

    def __init__(self, data: str) -> None:
        self.data = data


class _FakeWs:
    def __init__(self, frames: list[str]) -> None:
        self.frames = frames
        self.sent: list[str] = []

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.frames:
            raise StopAsyncIteration
        return _Msg(self.frames.pop(0))

    async def send_str(self, data: str) -> None:
        self.sent.append(data)


class _ReplyWs:
    def __init__(self, frame: dict) -> None:
        self._frame = frame
        self.sent: list[str] = []

    async def receive(self):
        return _Msg(json.dumps(self._frame))

    async def send_str(self, data: str) -> None:
        self.sent.append(data)

    async def send_json(self, data: dict) -> None:
        self.sent.append(json.dumps(data))


async def test_connect_returns_client_id_from_reply() -> None:
    api = DonatApi(token='token', handler=AsyncMock())
    ws = _ReplyWs({'id': 1, 'result': {'client': 'abc-123', 'version': '2.2.1'}})

    client = await api._connect(ws, 'socket_token')

    assert client == 'abc-123'


async def test_connect_raises_without_client_id() -> None:
    api = DonatApi(token='token', handler=AsyncMock())
    ws = _ReplyWs({'id': 1, 'result': {'version': '2.2.1'}})

    with pytest.raises(ConnectionError, match='missing client id'):
        await api._connect(ws, 'socket_token')


async def test_read_loop_pongs_ping_and_parses_publication() -> None:
    handler = AsyncMock()
    api = DonatApi(token='token', handler=handler)
    frame = {
        'type': 1,
        'channel': '$alerts:donation_1',
        'data': {'data': CENTRIFUGO_DONATION},
    }
    ws = _FakeWs(['{}', json.dumps(frame)])

    await api._read_loop(ws)

    assert ws.sent == ['{}']
    handler.assert_awaited_once()
    event = handler.await_args.args[0]
    assert event.id == CENTRIFUGO_DONATION['id']
    assert event.amount == 500


async def test_read_loop_handles_protobuf_style_publication() -> None:
    handler = AsyncMock()
    api = DonatApi(token='token', handler=handler)
    frame = {'id': 0, 'pub': {'channel': '$alerts:donation_1', 'data': CENTRIFUGO_DONATION}}
    ws = _FakeWs([json.dumps(frame)])

    await api._read_loop(ws)

    handler.assert_awaited_once()


async def test_read_loop_raises_on_disconnect() -> None:
    api = DonatApi(token='token', handler=AsyncMock())
    ws = _FakeWs([json.dumps({'type': 32771, 'reason': 'expired'})])

    with pytest.raises(ConnectionError):
        await api._read_loop(ws)


async def test_handle_donation_drops_validation_errors() -> None:
    handler = AsyncMock()
    api = DonatApi(token='token', handler=handler)

    await api._handle_donation({'name': 'alien_invasion'})

    handler.assert_not_awaited()

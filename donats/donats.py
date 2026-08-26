import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from typing import Any, cast

import aiohttp
from marshmallow.exceptions import ValidationError

from donats.da_auth import get_access_token
from donats.models import AlertEvent
from donats.schemas import AlertEventSchema

logger = logging.getLogger(__name__)

CENTRIFUGO_URL = 'wss://centrifugo.donationalerts.com/connection/websocket'
API_BASE = 'https://www.donationalerts.com/api/v1'

_METHOD_SUBSCRIBE = 1
_PUSH_PUBLICATION = 1
_PUSH_PING = 7
_PUSH_DISCONNECT = 32771


class DonatApi:
    async def run(self) -> None:
        async with aiohttp.ClientSession() as session:
            self.token = await get_access_token(session) or self.token
            user = await self._fetch_user(session)
            channel = f'$alerts:donation_{user["id"]}'
            sub_token = await self._fetch_subscribe_token(session, channel)
            async with session.ws_connect(CENTRIFUGO_URL) as ws:
                await self._connect(ws, user['socket_connection_token'])
                await self._subscribe(ws, channel, sub_token)
                await self._read_loop(ws)

    def __init__(
        self, token: str, handler: Callable[[AlertEvent], Coroutine[Any, Any, None]]
    ) -> None:
        self.token: str = token
        self.handler: Callable[[AlertEvent], Coroutine[Any, Any, None]] = handler
        self._msg_id: int = 0

    async def _fetch_user(self, session: aiohttp.ClientSession) -> dict[str, Any]:
        headers = {'Authorization': f'Bearer {self.token}'}
        async with session.get(f'{API_BASE}/user/oauth', headers=headers) as resp:
            resp.raise_for_status()
            return (await resp.json())['data']

    async def _fetch_subscribe_token(
        self, session: aiohttp.ClientSession, channel: str
    ) -> str:
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }
        body = {'channels': [channel], 'client': str(uuid.uuid4())}
        async with session.post(
            f'{API_BASE}/centrifuge/subscribe', headers=headers, json=body
        ) as resp:
            resp.raise_for_status()
            return (await resp.json())['channels'][0]['token']

    async def _send(self, ws: aiohttp.ClientWebSocketResponse, command: dict) -> None:
        self._msg_id += 1
        await ws.send_json({'id': self._msg_id, **command})

    async def _connect(self, ws: aiohttp.ClientWebSocketResponse, socket_token: str) -> None:
        await self._send(ws, {'params': {'token': socket_token}})
        await self._expect_reply(ws)

    async def _subscribe(
        self, ws: aiohttp.ClientWebSocketResponse, channel: str, token: str
    ) -> None:
        await self._send(
            ws,
            {
                'method': _METHOD_SUBSCRIBE,
                'params': {'channel': channel, 'token': token},
            },
        )
        await self._expect_reply(ws)

    async def _expect_reply(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        while True:
            msg = await ws.receive()
            if msg.type != aiohttp.WSMsgType.TEXT:
                message = f'centrifugo closed during handshake: {msg.type}'
                raise ConnectionError(message)
            frame = json.loads(msg.data)
            if 'error' in frame:
                message = f'centrifugo error: {frame["error"]}'
                raise ConnectionError(message)
            if frame.get('id') is not None:
                return
            if not frame or frame.get('type') == _PUSH_PING:
                await ws.send_str('{}')

    async def _read_loop(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        async for msg in ws:
            if msg.type != aiohttp.WSMsgType.TEXT:
                continue
            text = msg.data.strip()
            if not text or text == '{}':
                await ws.send_str('{}')  # pong to server ping
                continue
            frame = json.loads(text)
            if frame.get('id'):  # reply to our own command
                continue
            if 'disconnect' in frame or frame.get('type') == _PUSH_DISCONNECT:
                message = f'centrifugo disconnect: {frame}'
                raise ConnectionError(message)
            if frame.get('pub'):  # protobuf-style publication
                payload = frame['pub'].get('data', frame['pub'])
                await self._handle_donation(payload)
            elif frame.get('type') == _PUSH_PUBLICATION:
                publication = frame.get('data') or {}
                payload = publication.get('data', publication)
                await self._handle_donation(payload)
            elif frame.get('type') == _PUSH_PING:
                await ws.send_str('{}')

    async def _handle_donation(self, payload: dict) -> None:
        logger.debug('new event %s', payload)
        try:
            event: AlertEvent = cast('AlertEvent', AlertEventSchema().load(payload))
        except ValidationError as e:
            logger.critical('validation error: %s', payload, exc_info=e)
            return None
        if self.handler is not None:
            return await self.handler(event)
        logger.critical('no handler wtf')
        return None

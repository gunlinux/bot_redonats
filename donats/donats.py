import json
import logging
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
_PUSH_DISCONNECT_JSON = 7
_PUSH_DISCONNECT = 32771


class DonatApi:
    async def run(self) -> None:
        async with aiohttp.ClientSession() as session:
            self.token = await get_access_token(session) or self.token
            user = await self._fetch_user(session)
            channel = f'$alerts:donation_{user["id"]}'
            async with session.ws_connect(CENTRIFUGO_URL) as ws:
                client_id = await self._connect(ws, user['socket_connection_token'])
                sub_token = await self._fetch_subscribe_token(session, channel, client_id)
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
        self, session: aiohttp.ClientSession, channel: str, client: str
    ) -> str:
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
        }
        body = {'channels': [channel], 'client': client}
        async with session.post(
            f'{API_BASE}/centrifuge/subscribe', headers=headers, json=body
        ) as resp:
            resp.raise_for_status()
            return (await resp.json())['channels'][0]['token']

    async def _send(self, ws: aiohttp.ClientWebSocketResponse, command: dict) -> None:
        self._msg_id += 1
        await ws.send_json({'id': self._msg_id, **command})

    async def _connect(
        self, ws: aiohttp.ClientWebSocketResponse, socket_token: str
    ) -> str:
        await self._send(ws, {'params': {'token': socket_token}})
        reply = await self._expect_reply(ws)
        client = (reply.get('result') or {}).get('client')
        if not client:
            message = f'centrifugo connect missing client id: {reply}'
            raise ConnectionError(message)
        return client

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

    async def _expect_reply(self, ws: aiohttp.ClientWebSocketResponse) -> dict:
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
                return frame
            if not frame:
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
            # DonationAlerts wraps every server push in a top-level "result"
            # field ({result: {channel, data}}), unlike the raw Centrifugo
            # format where type/pub sit at the top level.
            push = frame.get('result') or frame
            if 'disconnect' in push or push.get('type') in (
                _PUSH_DISCONNECT,
                _PUSH_DISCONNECT_JSON,
            ):
                message = f'centrifugo disconnect: {frame}'
                raise ConnectionError(message)
            if push.get('pub'):  # protobuf-style publication
                payload = push['pub'].get('data', push['pub'])
                await self._handle_donation(payload)
            elif push.get('type') == _PUSH_PUBLICATION or 'channel' in push:
                publication = push.get('data') or {}
                payload = publication.get('data')
                if isinstance(payload, dict):
                    await self._handle_donation(payload)

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

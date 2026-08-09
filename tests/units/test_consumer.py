import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from donats.consumer import RabbitConsumer


def make_consumer() -> tuple[RabbitConsumer, Mock]:
    broker = Mock()
    with patch('donats.consumer.FastStream') as faststream_cls:
        app = faststream_cls.return_value
        app.run = AsyncMock()
        app.stop = AsyncMock()
        consumer = RabbitConsumer(
            broker=broker,
            worker=AsyncMock(),
            queue_name='test_queue',
        )
    return consumer, app


async def test_consume_stops_app_on_normal_exit() -> None:
    consumer, app = make_consumer()

    await consumer.consume()

    app.run.assert_awaited_once()
    app.stop.assert_awaited_once()


async def test_consume_stops_app_on_cancellation() -> None:
    consumer, app = make_consumer()
    app.run.side_effect = asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await consumer.consume()

    app.stop.assert_awaited_once()

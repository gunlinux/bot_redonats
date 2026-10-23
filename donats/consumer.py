import asyncio
from collections.abc import Awaitable, Callable
import logging
import typing

from faststream import FastStream, AckPolicy
from faststream.rabbit import RabbitBroker, RabbitQueue
from faststream.rabbit.annotations import RabbitMessage


class RabbitConsumer:
    def __init__(
        self,
        queue_name: str,
        broker: RabbitBroker,
        worker: Callable[[dict[str, typing.Any]], Awaitable[None]],
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logging.getLogger() if logger is None else logger
        self.worker = worker
        self._app = FastStream(broker)
        # shortcut: no DLQ args so we can bind an already-declared external queue
        broker.subscriber(
            queue=RabbitQueue(
                queue_name,
                auto_delete=False,
                durable=True,
            ),
            ack_policy=AckPolicy.MANUAL,
        )(self.worker_wrapper)

    async def worker_wrapper(
        self, message: dict[str, typing.Any], msg: RabbitMessage
    ) -> None:
        try:
            await self.worker(message)
            await msg.ack()
        except Exception as e:  # noqa: BLE001
            self.logger.warning('worker function failed with error %s', e)
            await msg.reject()

    async def consume(self) -> None:
        try:
            await self._app.run()
        finally:
            await asyncio.shield(self._app.stop())

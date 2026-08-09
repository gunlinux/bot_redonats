import asyncio
from collections.abc import Awaitable, Callable
import logging

from faststream import FastStream, AckPolicy
from faststream.rabbit import RabbitBroker, RabbitQueue
from faststream.rabbit.annotations import RabbitMessage

from donats.queue_models import FQueueMessage


class RabbitConsumer:
    def __init__(
        self,
        queue_name: str,
        broker: RabbitBroker,
        worker: Callable[[FQueueMessage], Awaitable[None]],
        dlq_exchange: str = 'dlq',
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logging.getLogger() if logger is None else logger
        self.dlq_exchange = dlq_exchange
        self.worker = worker
        self._app = FastStream(broker)
        broker.subscriber(
            queue=RabbitQueue(
                queue_name,
                auto_delete=False,
                durable=True,
                arguments={
                    'x-dead-letter-exchange': dlq_exchange,
                    'x-dead-letter-routing-key': f'{queue_name}.dlq',
                },
            ),
            ack_policy=AckPolicy.MANUAL,
        )(self.worker_wrapper)

    async def worker_wrapper(self, message: FQueueMessage, msg: RabbitMessage) -> None:
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

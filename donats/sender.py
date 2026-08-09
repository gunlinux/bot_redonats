import logging
from typing import Protocol

from faststream.rabbit import RabbitBroker, RabbitExchange

from donats.publisher import Publisher
from donats.queue_models import FQueueEvent, FQueueMessage


logger = logging.getLogger(__name__)


class SenderProtocol(Protocol):
    async def send_message(
        self,
        message: str,
        source: str = '',
    ) -> None: ...


class Sender(SenderProtocol):
    def __init__(
        self,
        exchange_name: str,
        broker: RabbitBroker | None,
        source: str = '',
    ) -> None:
        self.publisher = (
            Publisher(broker=broker, exchange=RabbitExchange(exchange_name))
            if broker and exchange_name
            else None
        )
        self.source = source

    async def send_message(
        self,
        message: str,
        source: str = '',
    ) -> None:
        new_message = FQueueMessage(
            event='mssg',
            source=source or self.source,
            data=FQueueEvent(
                event_type='mssg',
                message=message,
            ),
        )
        if self.publisher:
            await self.publisher.publish(new_message)

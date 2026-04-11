import asyncio

from donats.handlers import DonatEventHandler
from donats import settings
from donats.utils import logger_setup
from requeue.sender.sender import Sender

from faststream.rabbit import RabbitBroker
from requeue.fstream.consumer import RabbitConsumer


logger = logger_setup(__name__)
logger.info('Donats worker service started')


async def main() -> None:
    broker = RabbitBroker(settings.rabbit_url, virtualhost=settings.rabbit_vhost)
    sender = Sender(broker=broker, exchange_name=settings.TWITCH_OUT)
    donat_handler: DonatEventHandler = DonatEventHandler(
        sender=sender,
        admin='gunlinux',
    )
    await RabbitConsumer(
        broker=broker,
        worker=donat_handler.on_message,
        queue_name=settings.DONATS_EVENTS,
    ).consume()


if __name__ == '__main__':
    asyncio.run(main())

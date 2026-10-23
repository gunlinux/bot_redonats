import asyncio

from donats.handlers import DonatEventHandler
from donats import settings
from donats.utils import logger_setup
from donats.sender import Sender

from faststream.rabbit import RabbitBroker
from donats.consumer import RabbitConsumer


logger = logger_setup(__name__)
logger.info('Donats worker service started')


async def main() -> None:
    out_broker = RabbitBroker(settings.rabbit_url, virtualhost=settings.rabbit_vhost)
    alerts_broker = RabbitBroker(settings.rabbit_alerts)
    sender = Sender(broker=out_broker, exchange_name=settings.TWITCH_OUT)
    donat_handler: DonatEventHandler = DonatEventHandler(
        sender=sender,
        admin='gunlinux',
    )
    await RabbitConsumer(
        broker=alerts_broker,
        worker=donat_handler.on_message,
        queue_name=settings.DONATIONS_ALERTS,
    ).consume()


if __name__ == '__main__':
    asyncio.run(main())

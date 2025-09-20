import asyncio

from donats.handlers import DonatEventHandler
from donats import settings
from donats.utils import logger_setup
from requeue.requeue import Queue
from requeue.rredis import RedisConnection
from requeue.sender.sender import Sender

logger = logger_setup(__name__)
logger.info('Donats worker service started')


async def main() -> None:
    redis_url: str = settings.donats_redis_url
    async with RedisConnection(redis_url) as redis_connection:
        queue = Queue(name=settings.DONATS_EVENTS, connection=redis_connection)
        sender = Sender(queue_name=settings.TWITCH_OUT, connection=redis_connection)
        donat_handler: DonatEventHandler = DonatEventHandler(
            sender=sender,
            admin='gunlinux',
        )
        await queue.consumer(donat_handler.on_message)


if __name__ == '__main__':
    asyncio.run(main())

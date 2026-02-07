import asyncio
from collections import deque
from collections.abc import Callable, Coroutine
import typing

from donats.donats import DonatApi
from donats.models import BillingSystem, AlertEvent
from donats import settings
from donats.utils import logger_setup, get_currencies

from requeue.requeue import Queue
from requeue.rredis import RedisConnection

if typing.TYPE_CHECKING:
    from requeue.models import QueueMessage

logger = logger_setup(__name__)
logger.info('Donats getter service started')


def recal_amount(event: AlertEvent, currencies: dict[str, float], default='RUB'):
    if event.currency == default:
        return event
    pair = f'{event.currency}{default}'
    if pair in currencies:
        event.amount = event.amount * currencies.get('pair', 1)
        event.currency = default
    return event


async def init_process(
    queue: Queue,
    redis_connection: RedisConnection,
    currencies: dict[str, float],
) -> Callable[[AlertEvent], Coroutine[typing.Any, typing.Any, None]]:
    work_queue: Queue = queue
    events_queue = Queue(name=settings.LOCAL_EVENTS, connection=redis_connection)
    beer_queue = Queue(name=settings.BEER_STAT, connection=redis_connection)
    processed = deque(maxlen=100)

    async def process_mssg(message: AlertEvent) -> None:
        nonlocal processed
        logger.debug('Received message for processing')
        logger.debug('Message content: %s', message)
        message = typing.cast('AlertEvent', message)
        logger.debug('Processing message ID: %s', message.id)
        if message.id in processed:
            logger.critical('Duplicate message detected: %s', message.id)
            return
        processed.append(message.id)

        if message.billing_system != BillingSystem.TWITCH:
            recal_amount(event=message, currencies=currencies)

        new_message: QueueMessage = message.map_to_queue_message(source='donats_getter')
        if new_message.data.billing_system == BillingSystem.TWITCH:
            # ignoring twitch events
            logger.debug('ignoring message from twitch: %s', message)
            return
        await events_queue.push(new_message)
        await work_queue.push(new_message)
        await beer_queue.push(new_message)
        logger.critical('saving new_message to a works queues')

    return process_mssg


async def main() -> None:
    logger.info('Initializing donats getter service')
    logger.info('Redis URL: %s', settings.donats_redis_url)
    currencies = get_currencies(settings.CURRENCIES)
    async with RedisConnection(settings.donats_redis_url) as redis_connection:
        queue = Queue(name=settings.DONATS_EVENTS, connection=redis_connection)

        handler = await init_process(
            queue,
            typing.cast('RedisConnection', redis_connection),
            currencies=currencies,
        )
        bot = DonatApi(token=settings.DA_ACCESS_TOKEN, handler=handler)
        while True:
            try:
                logger.info('start donats bot')
                await bot.run()
                logger.warning('bot.run() finished without an exception. Restarting...')
            except Exception as e:  # noqa: BLE001, PERF203
                logger.warning('Connection error we are reconnecting', exc_info=e)


if __name__ == '__main__':
    asyncio.run(main())

import asyncio
from collections import deque
from collections.abc import Callable, Coroutine
import typing
import sys

from donats.donats import DonatApi
from donats.models import BillingSystem, AlertEvent
from donats import settings
from donats.utils import logger_setup, get_currencies

from faststream.rabbit import RabbitBroker, RabbitExchange
from requeue.fstream.publisher import Publisher


if typing.TYPE_CHECKING:
    from requeue.fstream.models import FQueueMessage

logger = logger_setup(__name__)
logger.info('Donats getter service started')


def recal_amount(event: AlertEvent, currencies: dict[str, float], default='RUB'):
    if event.currency == default:
        return event
    pair = f'{event.currency}{default}'
    if pair in currencies:
        event.amount = event.amount * currencies.get(pair, 1)
        event.currency = default
    else:
        logger.warning('cant find currency pair %s', pair)
    return event


async def init_process(
    currencies: dict[str, float],
    publisher: Publisher,
) -> Callable[[AlertEvent], Coroutine[typing.Any, typing.Any, None]]:
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
            message = recal_amount(event=message, currencies=currencies)
            logger.critical('after recal %s', message)

        new_message: FQueueMessage = message.map_to_fastq_message(
            source='donats_getter'
        )
        if (
            new_message.data.billing_system == BillingSystem.TWITCH
            or new_message.data.billing_system is None
        ):
            # ignoring twitch events
            logger.debug('ignoring message from twitch: %s', message)
            return

        await publisher.publish(new_message)
        logger.critical('saving new_message to a works queues')

    return process_mssg


async def main() -> None:
    logger.info('Initializing donats getter service')
    currencies = get_currencies(settings.CURRENCIES)
    if not currencies:
        logger.critical('cant load currencies')
        sys.exit(1)

    broker = RabbitBroker(settings.rabbit_url, virtualhost=settings.rabbit_vhost)
    exch = RabbitExchange(settings.rabbit_exchange)
    publisher = Publisher(broker=broker, exchange=exch)

    handler = await init_process(
        publisher=publisher,
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

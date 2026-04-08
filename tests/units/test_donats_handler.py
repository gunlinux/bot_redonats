import logging


logger = logging.getLogger(name=__name__)

from donats.handlers import DonatEventHandler
from requeue.requeue import Queue


async def process(handler, data):
    _ = handler
    logger.debug('process start %s', data)


async def test_real_events(load_da_events: Queue):
    queue = load_da_events
    await queue.pop()

    donat_handler: DonatEventHandler = DonatEventHandler(
        sender=None,
        admin='gunlinux',
    )

    for _ in range(2):
        new_event = await queue.pop()
        if new_event:
            await process(handler=donat_handler, data=new_event)

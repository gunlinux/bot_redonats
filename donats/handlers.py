import logging
from enum import Enum

from requeue.models import QueueMessage, QueueEvent
from requeue.sender.sender import SenderAbc


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class DonationAlertTypes(Enum):
    DONATION = 1
    CUSTOM_REWARD = 19
    FOLLOW = 6
    SUBSCRIBE = 7


class DonatEventHandler:
    def __init__(self, sender: SenderAbc | None, admin: str | None) -> None:
        self.admin = admin
        self.sender = sender

    async def chat(self, mssg: str) -> None:
        if self.sender is not None:
            await self.sender.send_message(mssg)
        else:
            logger.error('Cannot send message: sender is not initialized')

    async def on_message(self, message: QueueMessage) -> QueueMessage | None:
        logger.debug('Processing new event from queue')

        try:
            await self.handle_event(message.data)
        except Exception as e:  # noqa: BLE001
            logger.critical('FAILED TO PROCESS MESSAGE %s %s ', message, e)
            return message

    async def handle_event(self, event: QueueEvent) -> None:
        if event.event_type == DonationAlertTypes.DONATION.name:
            await self._donation(event)
            return

        if event.event_type == DonationAlertTypes.FOLLOW.name:
            await self._follow(event)
            return

        if event.event_type == DonationAlertTypes.SUBSCRIBE.name:
            await self._subscribe(event)
            return

        logger.warning('handle_event not implemented yet %s', event)

    async def _donation(self, event: QueueEvent) -> None:
        logger.info('donat.event _donation')
        if event.user_name is None:
            event.user_name = 'anonym'
        mssg_text = f"""{self.admin} {event.user_name} пожертвовал
            {event.amount} {event.currency} | {event.message}"""
        await self.chat(mssg_text)

    async def _follow(self, event: QueueEvent) -> None:
        logger.info('donat.event _follow')
        mssg_text = f'@gunlinux @{event.user_name} started follow auf'
        await self.chat(mssg_text)

    async def _subscribe(self, event: QueueEvent) -> None:
        logger.info('donat.event _subscribe (youtube?)')
        mssg_text = f'@gunlinux @{event.user_name} _subscribed on youtube <3 auf'
        await self.chat(mssg_text)

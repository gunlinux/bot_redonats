from dataclasses import dataclass, asdict
from enum import Enum, StrEnum

import typing

from requeue.models import QueueMessage, QueueEvent


class BillingSystem(StrEnum):
    TWITCH = 'TWITCH'
    RETWITCH = 'RETWITCH'
    YOUTUBE = 'YOUTUBE'


class DonationAlertTypes(Enum):
    DONATION = 1
    CUSTOM_REWARD = 19
    FOLLOW = 6
    SUBSCRIBE = 7


@dataclass
class AlertEvent:
    id: int
    alert_type: int
    billing_system: str
    username: str | None
    amount: float
    amount_formatted: str
    currency: str
    message: str
    # valdate as date???
    date_created: str
    _is_test_alert: bool

    def serialize(self) -> dict[str, typing.Any]:
        return asdict(self)

    def get_event_type(self) -> str:
        return DonationAlertTypes(self.alert_type).name

    def map_to_queue_message(self, source='donats_getter') -> QueueMessage:
        event_type = self.get_event_type()
        return QueueMessage(
            event=event_type,
            source=source,
            data=QueueEvent(
                event_type=event_type,
                billing_system=self.billing_system,
                user_name=self.username,
                amount=self.amount,
                currency=self.currency,
                message=self.message,
                event=None,
            ),
        )

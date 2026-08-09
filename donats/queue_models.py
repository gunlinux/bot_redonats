import typing

from pydantic import BaseModel


class FQueueEvent(BaseModel):
    event_type: str
    billing_system: str | None = None
    user_name: str | None = None
    amount: float | None = None
    currency: str | None = None
    message: str | None = None
    event: dict[str, typing.Any] | None = None


class FQueueMessage(BaseModel):
    event: str
    data: FQueueEvent
    source: str = ''

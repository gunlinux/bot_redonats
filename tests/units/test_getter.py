from unittest.mock import AsyncMock

from donats.models import AlertEvent
from donats_getter import init_process


def _event(billing_system: str | None) -> AlertEvent:
    return AlertEvent(
        id=1,
        alert_type=1,
        billing_system=billing_system,
        username='Ivan',
        amount=500.0,
        amount_formatted='500 RUB',
        currency='RUB',
        message='Hello!',
        date_created='2019-09-29 09:00:00',
        _is_test_alert=False,
    )


async def test_native_donation_without_billing_system_is_published() -> None:
    publisher = AsyncMock()
    handler = await init_process(currencies={}, publisher=publisher)

    await handler(_event(billing_system=None))

    publisher.publish.assert_awaited_once()


async def test_twitch_event_is_dropped() -> None:
    publisher = AsyncMock()
    handler = await init_process(currencies={}, publisher=publisher)

    await handler(_event(billing_system='TWITCH'))

    publisher.publish.assert_not_awaited()

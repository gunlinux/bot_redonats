from typing import TYPE_CHECKING
import typing
from donats.schemas import AlertEventSchema

if TYPE_CHECKING:
    from donats.models import AlertEvent


async def test_twitch_follow():
    data = {
        'id': 247645962,
        'alert_type': 6,
        'is_shown': '0',
        'additional_data': '{"randomness":469,"event_data":{"user":{"display_name":"sent1ma"}}}',
        'billing_system': None,
        'billing_system_type': None,
        'username': 'sent1ma',
        'amount': '0.00',
        'amount_formatted': '0',
        'amount_main': 0,
        'currency': 'USD',
        'message': '',
        'header': '',
        'date_created': '2026-03-27 17:13:16',
        'emotes': None,
        'ap_id': None,
        'tts_url': None,
        '_is_test_alert': False,
        'referrer': None,
        'message_type': 'text',
    }
    event: AlertEvent = typing.cast('AlertEvent', AlertEventSchema().load(data))
    assert event is not None

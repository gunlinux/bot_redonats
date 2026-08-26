import pytest
from marshmallow.exceptions import ValidationError

from donats.schemas import AlertEventSchema

CENTRIFUGO_DONATION = {
    'id': 30530030,
    'name': 'donation',
    'username': 'Ivan',
    'message_type': 'text',
    'message': 'Hello!',
    'amount': 500,
    'currency': 'RUB',
    'is_shown': 1,
    'created_at': '2019-09-29 09:00:00',
    'shown_at': None,
}


def test_centrifugo_donation_maps_to_alert_event() -> None:
    event = AlertEventSchema().load(CENTRIFUGO_DONATION)
    assert event.id == 30530030
    assert event.alert_type == 1
    assert event.username == 'Ivan'
    assert event.amount == 500
    assert event.currency == 'RUB'
    assert event.message == 'Hello!'
    assert event.date_created == '2019-09-29 09:00:00'
    assert event.billing_system is None
    assert event._is_test_alert is False


def test_centrifugo_unknown_alert_name_rejected() -> None:
    payload = {**CENTRIFUGO_DONATION, 'name': 'alien_invasion'}
    with pytest.raises(ValidationError):
        AlertEventSchema().load(payload)


def test_legacy_socketio_payload_still_works() -> None:
    legacy = {
        'id': 95682041,
        'alert_type': '19',
        'billing_system': 'TWITCH',
        'username': 'mr_qmr',
        'amount': 420.0,
        'amount_formatted': '420',
        'currency': 'USD',
        'message': '#handsoff',
        'date_created': '2025-03-03 17:00:26',
        '_is_test_alert': False,
    }
    event = AlertEventSchema().load(legacy)
    assert event.alert_type == 19
    assert event.billing_system == 'TWITCH'

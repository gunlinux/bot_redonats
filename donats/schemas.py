import typing
from marshmallow import Schema, fields, post_load, EXCLUDE, pre_load
from donats.models import AlertEvent, DonationAlertTypes


class AlertEventSchema(Schema):
    id = fields.Int(required=True)
    alert_type = fields.Int(required=True)
    billing_system = fields.Str(allow_none=True)
    username = fields.Str(allow_none=True)
    amount = fields.Float()
    amount_formatted = fields.Str()
    currency = fields.Str()
    message = fields.Str(allow_none=True)
    # valdate as date???
    date_created = fields.Str()
    _is_test_alert = fields.Bool()

    class Meta:
        unknown = EXCLUDE

    @pre_load
    def preload(self, data: dict[str, typing.Any], **_) -> dict[str, typing.Any]:
        if 'alert_type' in data:
            data['alert_type'] = (
                int(data['alert_type'])
                if isinstance(data['alert_type'], str)
                else data['alert_type']
            )
            return data
        # Centrifugo donation payload: {id, name, username, message, amount,
        # currency, created_at, ...} — no alert_type/billing_system. The
        # $alerts:donation_<user_id> channel only carries donations, so the
        # event type is always DONATION. The "name" field is the donor's
        # display name, not an event type.
        amount = data.get('amount', 0)
        currency = data.get('currency', '')
        return {
            'id': data.get('id'),
            'alert_type': DonationAlertTypes.DONATION.value,
            'billing_system': None,
            'username': data.get('username') or data.get('name'),
            'amount': amount,
            'amount_formatted': f'{amount} {currency}'.strip(),
            'currency': currency,
            'message': data.get('message'),
            'date_created': data.get('created_at'),
            '_is_test_alert': data.get('is_test_alert', False),
        }

    @post_load
    def make(self, data: dict[str, typing.Any], **_) -> AlertEvent:
        return AlertEvent(**data)

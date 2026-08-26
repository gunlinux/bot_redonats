import typing
from marshmallow import Schema, fields, post_load, EXCLUDE, pre_load, ValidationError
from donats.models import AlertEvent, DonationAlertTypes

_ALERT_TYPES_BY_NAME = {
    'donation': DonationAlertTypes.DONATION,
    'custom_alert': DonationAlertTypes.CUSTOM_REWARD,
    'follow': DonationAlertTypes.FOLLOW,
    'subscribe': DonationAlertTypes.SUBSCRIBE,
}


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
        if 'name' in data:
            # Centrifugo payload: {id, name, username, message, amount, currency,
            # created_at, ...} — no alert_type/billing_system/date_created.
            try:
                alert_type = _ALERT_TYPES_BY_NAME[data['name']]
            except KeyError:
                message = f'unknown alert name: {data["name"]}'
                raise ValidationError(message) from None
            amount = data.get('amount', 0)
            currency = data.get('currency', '')
            return {
                'id': data['id'],
                'alert_type': alert_type.value,
                'billing_system': None,
                'username': data.get('username'),
                'amount': amount,
                'amount_formatted': f'{amount} {currency}'.strip(),
                'currency': currency,
                'message': data.get('message'),
                'date_created': data.get('created_at'),
                '_is_test_alert': data.get('is_test_alert', False),
            }
        if 'alert_type' not in data:
            return data
        data['alert_type'] = (
            int(data['alert_type'])
            if isinstance(data['alert_type'], str)
            else data['alert_type']
        )
        return data

    @post_load
    def make(self, data: dict[str, typing.Any], **_) -> AlertEvent:
        return AlertEvent(**data)

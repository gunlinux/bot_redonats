# donations-worker Specification

## Purpose

Consumes donation alerts from RabbitMQ and turns them into Twitch chat notifications, as the repository's only runtime service.

## Requirements

### Requirement: Worker-only runtime

The deployed runtime SHALL consist of the donations worker only and SHALL NOT require DonationAlerts OAuth credentials or a currency conversion file to start.

#### Scenario: Starting without DonationAlerts configuration

- **WHEN** the worker starts with only RabbitMQ and logging configuration available
- **THEN** it consumes alert messages and publishes chat output without reading DonationAlerts credentials or a currencies file

### Requirement: Consume alerts from the configured queue

The worker SHALL consume messages from the durable queue named by `DONATIONS_ALERTS` on the broker at `RABBIT_ALERTS`, acknowledging each message after successful handling.

#### Scenario: Successful handling is acknowledged

- **WHEN** a queued alert is handled without error
- **THEN** the message is acknowledged and removed from the queue

#### Scenario: Failed handling is rejected

- **WHEN** handling a queued alert raises an error
- **THEN** the message is rejected without acknowledgement and the worker keeps consuming

### Requirement: Accept raw and legacy alert payloads

The worker SHALL accept both payloads that carry `alert_type` and raw donation payloads that omit it, treating the latter as donations with the donor taken from `username`, falling back to `name`.

#### Scenario: Raw donation payload

- **WHEN** a queue message contains a donation payload without `alert_type`
- **THEN** it is handled as a donation event

#### Scenario: Donor fallback

- **WHEN** a raw donation payload has no `username` but has `name`
- **THEN** `name` is used as the donor name

#### Scenario: Missing identifier

- **WHEN** a payload has no `id`
- **THEN** handling fails and the message is rejected

### Requirement: Amounts are rendered as received

The worker SHALL report amounts and currencies exactly as they appear in the queue payload, without currency conversion or duplicate suppression.

#### Scenario: Non-default currency

- **WHEN** a donation arrives in a currency other than RUB
- **THEN** the chat message shows the original amount and currency

#### Scenario: Repeated identifier

- **WHEN** two queued messages carry the same alert identifier
- **THEN** both are handled, since deduplication is no longer performed in this repository

### Requirement: Format chat text per event type

The worker SHALL format a distinct chat message for donations, follows and subscriptions, mentioning the configured admin and substituting `anonym` when a donation has no donor name.

#### Scenario: Donation message

- **WHEN** a donation event is handled
- **THEN** the published text mentions the admin and contains the donor, amount, currency and donation message

#### Scenario: Anonymous donation

- **WHEN** a donation event has no donor name
- **THEN** the text uses `anonym` as the donor

#### Scenario: Follow and subscription messages

- **WHEN** a follow or subscription event is handled
- **THEN** the published text states that the user started following or subscribed

#### Scenario: Unsupported event type

- **WHEN** an event type has no formatter
- **THEN** the event is logged and no chat message is published

### Requirement: Publish chat output to the Twitch exchange

The worker SHALL publish each formatted chat message to the exchange named by `TWITCH_OUT` on the outbound broker.

#### Scenario: Formatted message is published

- **WHEN** a message has been formatted for an event
- **THEN** exactly one message publication carrying that text is sent to the `TWITCH_OUT` exchange

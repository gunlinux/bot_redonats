# Project: GunlinuxBot — Donation Alerts → Twitch Bridge

A Python async service that consumes donation alerts from RabbitMQ and forwards formatted notifications to Twitch chat. Alert ingestion from [DonationAlerts](https://www.donationalerts.com/) happens outside this repository, which contains only the worker.

## Architecture

```
External producer (outside this repo)
        │
        ▼
  RabbitMQ (RABBIT_ALERTS) ── queue "donations_alerts"
        │
        ▼
  donats_worker.py
        │
  RabbitConsumer → DonatEventHandler (format message)
        │
  Sender ──► RabbitMQ Exchange ("twitch_out")
                    │
                    ▼
              Twitch chat bot
```

The repository ships a single service:

| Service | Entry Point | Role |
|---|---|---|
| **donats-worker** | `donats_worker.py` | Consumes alerts from `donations_alerts`, formats messages per event type, publishes them to the Twitch chat output exchange |

The external producer is expected to publish both raw donation payloads (no `alert_type`) and legacy payloads carrying `alert_type`. This repository performs no ingestion, currency conversion or deduplication.

## Stack

- **Python** ≥ 3.10
- **Package manager:** [uv](https://docs.astral.sh/uv/)
- **Message broker:** RabbitMQ via [FastStream](https://faststream.airt.ai/) (`faststream[rabbit]`)
- **Validation:** Marshmallow (`marshmallow`, `marshmallow-enum`)
- **Data models:** Pydantic (queue messages), dataclasses (alert events)
- **Error tracking:** Sentry (`sentry-sdk`)
- **Type checking:** Pyright
- **Linting/formatting:** Ruff (single-quote style, all rules except E501, docs, and a few others)
- **Testing:** pytest + pytest-asyncio (asyncio mode: auto, function-scoped event loops)

## Directory Layout

```
.
├── donats_worker.py       # Entry point: RabbitMQ → Twitch chat
├── donats/                # Worker library
│   ├── consumer.py        # RabbitConsumer — FastStream-based queue consumer with manual ack
│   ├── publisher.py       # Publisher — lazy-connect RabbitMQ publisher
│   ├── sender.py          # Sender — publishes formatted Twitch chat messages
│   ├── handlers.py        # DonatEventHandler — dispatches events by type (donation/follow/sub)
│   ├── models.py          # AlertEvent dataclass + BillingSystem/DonationAlertTypes enums
│   ├── queue_models.py    # FQueueMessage/FQueueEvent — Pydantic models for RabbitMQ messages
│   ├── schemas.py         # Marshmallow schema for queue payloads → AlertEvent
│   ├── settings.py        # All config via env vars, loaded by python-dotenv
│   └── utils.py           # logger_setup (console + optional Sentry)
├── services/              # systemd unit files for production deployment
├── tests/
│   └── units/             # Unit tests (pytest + pytest-asyncio)
├── Dockerfile
├── pyproject.toml
├── Makefile
└── uv.lock
```

## Building & Running

### Development Setup

```bash
make dev          # uv sync --dev (install all deps including dev)
```

### Linting & Type Checking

```bash
make lint         # ruff check
make fix          # ruff check --fix + ruff format
make types        # pyright
make check        # lint + fix + types
```

### Testing

```bash
make test         # uv run pytest
make test-dev     # uv run pytest -vv -s
make cov          # uv run pytest (coverage)
```

### Running Locally

```bash
uv run python donats_worker.py
```

The entry point is an `asyncio.run(main())` script — no CLI argument parsing. It needs the RabbitMQ settings below; no DonationAlerts credentials or currencies file are required.

### Production Deployment

- The Docker image builds from this repo and runs `uv run --no-sync donats_worker.py` by default.
- `.github/workflows/deploy.yaml` builds and pushes the image tagged with the commit short SHA, then runs `.github/deploy.sh` on the **gunlinux.ru** VPS (`185.146.156.243`, repo at `/home/loki/projects/bot/bot_redonats/`).
- `services/bot@donats_worker.service` is the only systemd unit; it runs the image with `--network host` and `--env-file .../.env`.
- No currencies file is resolved or mounted any more.
- **First deploy after this change:** the operator retires the previously installed getter unit manually — stop/disable it, remove its unit file, `sudo systemctl daemon-reload`, and confirm `docker ps` shows only `donats-worker`. The deploy script intentionally does not touch installed production units it no longer owns.

## Environment Variables

Settings read in `donats/settings.py` (loaded by `python-dotenv`):

| Variable | Default | Used by |
|---|---|---|
| `RABBIT_URL` | `amqp://user:password@localhost:5672/` | Worker (outbound broker; also the default for `RABBIT_ALERTS`) |
| `RABBIT_VHOST` | `gunlinux_bot` | Worker (outbound broker) |
| `RABBIT_ALERTS` | value of `RABBIT_URL` | Worker (inbound broker URL) |
| `BEER_URL` | `http://127.0.0.1:6016/donate` | (unused in current code) |
| `RECLIENT_ID`, `RECLIENT_SECRET`, `REOWNER_ID`, `REBOT_ID` | `""` | (Twitch-related, unused in current code) |
| `TOKEN_FILE`, `CHANNEL_TOKEN_FILE` | `tokens.json`, `channels_tokens.json` | (unused in current code) |
| `COMMAND_DIR` | `./commands/` | (unused in current code) |

Queue names are constants in `settings.py`, not environment variables: `DONATIONS_ALERTS` (`donations_alerts`, consumed), `TWITCH_OUT` (`twitch_out`, output), plus `LOCAL_EVENTS`, `BEER_STAT` and `TWITCH_EVENTS`.

Logging and Sentry are configured in `donats/utils.py` from `LOG_LEVEL` (default `DEBUG`), `LOG_FORMAT`, `SENTRY_DSN` (empty disables Sentry) and `TESTING` (`1` disables Sentry).

## Key Conventions

- **Single quotes** for strings (enforced by ruff format).
- **Line length** not enforced (E501 ignored).
- **No docstrings** required (D rules ignored in ruff, no existing docstrings).
- **Logging:** `logger_setup()` creates a logger with console output + optional Sentry. Use `logger.critical()` for important events, `logger.debug()` for trace-level.
- **Queue consumption:** `RabbitConsumer` binds the already-declared durable queue with manual ack. Successful handling is acked; a failing handler is logged and the message is rejected, and consumption continues.
- **Payload compatibility:** `AlertEventSchema` accepts legacy payloads with `alert_type` and raw donation payloads without it (treated as `DONATION`, donor from `username` falling back to `name`).
- **Amounts are rendered as received:** no currency conversion or duplicate suppression happens in this repository.
- **Error handling:** `on_message` in the handler re-raises after logging; the consumer wrapper catches, logs, and rejects.
- **Async all the way down:** All I/O is async. Tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
- **Type checking:** Pyright in basic mode, with `reportAny`, `reportExplicitAny`, etc. disabled. Tests directory excluded from type checking.

## Message Flow

1. An external producer publishes an alert payload into the `donations_alerts` queue on the `RABBIT_ALERTS` broker.
2. `RabbitConsumer.worker_wrapper()` receives it and calls `DonatEventHandler.on_message`.
3. `AlertEventSchema` (Marshmallow) validates the payload → `AlertEvent` dataclass.
4. `handle_event()` dispatches by `event_type` (DONATION, FOLLOW, SUBSCRIBE) → formats the Twitch chat message.
5. `Sender.send_message()` → `Publisher` publishes an `FQueueMessage` to the `TWITCH_OUT` exchange.
6. The Twitch chat bot (separate service) consumes from `twitch_out`.

## Related Infrastructure

- RabbitMQ runs on the same VPS (`gunlinux.ru`, port 5671 with SSL via the custom CA cert at `/home/loki/cacert.pem`).
- The Twitch chat bot that consumes from the `twitch_out` exchange is a separate service (not in this repo).

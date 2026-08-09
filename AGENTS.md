# Project: GunlinuxBot — Donation Alerts → Twitch Bridge

A Python async message pipeline that ingests donation alerts from [DonationAlerts](https://www.donationalerts.com/) via WebSocket, processes them through RabbitMQ, and forwards formatted notifications to Twitch chat.

## Architecture

```
DonationAlerts (WebSocket)
        │
        ▼
  donats_getter.py          ─── Publisher ──►  RabbitMQ Exchange ("donats_getter")
        │                                          │
        │                                      Consumer
        │                                          │
        ▼                                          ▼
  (currency conversion,                    donats_worker.py
   deduplication, filtering)                   │
                                          Handler (format messages)
                                               │
                                          Sender ──►  RabbitMQ Exchange ("twitch_out")
                                                          │
                                                          ▼
                                                    Twitch chat bot
```

Two standalone services connected via RabbitMQ:

| Service | Entry Point | Role |
|---|---|---|
| **donats-getter** | `donats_getter.py` | Connects to DonationAlerts socket.io, validates/processes alerts, publishes to RabbitMQ |
| **donats-worker** | `donats_worker.py` | Consumes from RabbitMQ, formats messages per event type, publishes to Twitch chat output exchange |

## Stack

- **Python** ≥ 3.10
- **Package manager:** [uv](https://docs.astral.sh/uv/)
- **Message broker:** RabbitMQ via [FastStream](https://faststream.airt.ai/) (`faststream[rabbit]`)
- **Validation:** Marshmallow (`marshmallow`, `marshmallow-enum`)
- **Data models:** Pydantic (queue messages), dataclasses (alert events)
- **WebSocket:** `python-socketio` (async client)
- **Error tracking:** Sentry (`sentry-sdk`)
- **Type checking:** Pyright
- **Linting/formatting:** Ruff (single-quote style, all rules except E501, docs, and a few others)
- **Testing:** pytest + pytest-asyncio (asyncio mode: auto, function-scoped event loops)

## Directory Layout

```
.
├── donats_getter.py       # Entry point: DonationAlerts → RabbitMQ
├── donats_worker.py       # Entry point: RabbitMQ → Twitch chat
├── donats/                # Shared library
│   ├── consumer.py        # RabbitConsumer — FastStream-based queue consumer with DLQ
│   ├── publisher.py       # Publisher — lazy-connect RabbitMQ publisher
│   ├── sender.py          # Sender — formats and publishes Twitch chat messages
│   ├── donats.py          # DonatApi — socket.io client for DonationAlerts
│   ├── handlers.py        # DonatEventHandler — dispatches events by type (donation/follow/sub)
│   ├── models.py          # AlertEvent dataclass + BillingSystem/DonationAlertTypes enums
│   ├── queue_models.py    # FQueueMessage/FQueueEvent — Pydantic models for RabbitMQ messages
│   ├── schemas.py         # Marshmallow schema for DonationAlerts JSON → AlertEvent
│   ├── settings.py        # All config via env vars, loaded by python-dotenv
│   ├── utils.py           # logger_setup (Sentry + file + console), get_currencies
│   └── exceptions.py      # DomainError, CurrencyLoadError
├── services/              # systemd unit files for production deployment
├── tests/
│   ├── units/             # Unit tests (pytest + pytest-asyncio)
│   ├── data/              # Test fixtures (JSON event payloads, currencies)
│   └── mock/              # (empty)
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
uv run python donats_getter.py
uv run python donats_worker.py
```

Both entry points are `asyncio.run(main())` scripts — no CLI argument parsing.

### Production Deployment

systemd unit files live in `services/`:
- `bot@donats_getter.service` — runs `donats_getter.py`
- `bot@donats_worker.service` — runs `donats_worker.py`

Deployed on the **gunlinux.ru** VPS (`185.146.156.243`) at `/home/loki/projects/bot/bot_redonats/`.

## Environment Variables

All configuration is via environment variables (loaded by `python-dotenv` in `settings.py`):

| Variable | Default | Used by |
|---|---|---|
| `RABBIT_URL` | `amqp://user:password@localhost:5672/` | Both |
| `RABBIT_VHOST` | `gunlinux_bot` | Both |
| `RABBIT_EXCHANGE` | `donats_getter` | Getter |
| `DA_ACCESS_TOKEN` | `""` | Getter (DonationAlerts API token) |
| `TWITCH_OUT` | `twitch_out` | Worker (output exchange name) |
| `DONATS_EVENTS` | `da_events` | Worker (queue name to consume) |
| `SENTRY_DSN` | `""` | Both (Sentry error tracking) |
| `LOG_LEVEL` | `DEBUG` | Both |
| `LOG_FORMAT` | see `utils.py` | Both |
| `FILE_LOG` | `gunlinuxbot.log` | Both |
| `CURRENCIES` | `currencies.json` | Getter |
| `TESTING` | `0` | Both (disables Sentry when set) |
| `BEER_URL` | `http://127.0.0.1:6016/donate` | (unused in current code) |
| `RECLIENT_ID`, `RECLIENT_SECRET`, etc. | various | (Twitch-related, unused in current code) |

## Key Conventions

- **Single quotes** for strings (enforced by ruff format).
- **Line length** not enforced (E501 ignored).
- **No docstrings** required (D rules ignored in ruff, no existing docstrings).
- **Logging:** `logger_setup()` creates a logger with console + file output + optional Sentry. Use `logger.critical()` for important events, `logger.debug()` for trace-level.
- **Currency conversion:** The getter converts all non-Twitch donations to RUB using `currencies.json` before publishing.
- **Twitch events are silently dropped** in the getter (billing_system == TWITCH or None).
- **Deduplication:** The getter uses a `deque(maxlen=100)` to track processed message IDs and reject duplicates.
- **DLQ:** The consumer configures `x-dead-letter-exchange` on every queue with manual ack. Failed messages are rejected (not nacked) and routed to the DLQ exchange.
- **Error handling:** `on_message` in the handler re-raises after logging; the consumer wrapper catches, logs, and rejects.
- **Async all the way down:** All I/O is async. Tests use `pytest-asyncio` with `asyncio_mode = "auto"`.
- **Type checking:** Pyright in basic mode, with `reportAny`, `reportExplicitAny`, etc. disabled. Tests directory excluded from type checking.

## Message Flow

1. DonationAlerts pushes JSON via WebSocket → `DonatApi.on_message`
2. JSON validated by `AlertEventSchema` (Marshmallow) → `AlertEvent` dataclass
3. Handler (set up in `init_process`) filters, converts currency, deduplicates
4. `AlertEvent.map_to_fastq_message()` → `FQueueMessage` (Pydantic)
5. `Publisher.publish()` → RabbitMQ exchange
6. `RabbitConsumer.worker_wrapper()` receives → calls `DonatEventHandler.on_message`
7. `handle_event()` dispatches by `event_type` (DONATION, FOLLOW, SUBSCRIBE) → formats Twitch chat message
8. `Sender.send_message()` → publishes `FQueueMessage` to the Twitch output exchange

## Current Branch

`requeue_remove` — recent change related to queue/requeue behavior (commit `489db3d`).

## Related Infrastructure

- RabbitMQ runs on the same VPS (`gunlinux.ru`, port 5671 with SSL via the custom CA cert at `/home/loki/cacert.pem`).
- The Twitch chat bot that consumes from the `twitch_out` exchange is a separate service (not in this repo).

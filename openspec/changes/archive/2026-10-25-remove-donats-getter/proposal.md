# Proposal

## Why

Alert ingestion now happens outside this repository: raw alerts are published into the second RabbitMQ broker (`RABBIT_ALERTS`) and the worker consumes them from `donations_alerts`. The in-repo getter still carries a full DonationAlerts OAuth/WebSocket client, currency conversion, deduplication and its own publisher — code that duplicates an external responsibility, requires DonationAlerts credentials and a `currencies.json` file on the host, and doubles the deployment surface (two systemd units, two container roles).

## What Changes

- **BREAKING** Remove the getter service: `donats_getter.py`, plus its client stack `donats/donats.py` and `donats/da_auth.py`, and the OAuth helper `get_token.py`.
- Remove getter-only currency conversion support: `get_currencies` in `donats/utils.py`, `donats/exceptions.py` (`DomainError`, `CurrencyLoadError`), the `CURRENCIES` setting, and the `currencies.json` mount/resolution in deployment.
- Remove DonationAlerts/OAuth settings (`DA_ACCESS_TOKEN`, `DA_REFRESH_TOKEN`, `DA_TOKEN_EXPIRES_AT`, `DA_CLIENT_ID`, `DA_CLIENT_SECRET`, `DA_REDIRECT_URI`) and the getter-only `RABBIT_EXCHANGE` setting.
- Remove the `aiohttp` dependency (only the removed client and its tests use it) and refresh `uv.lock`.
- Delete tests that exercise removed modules (`test_getter.py`, `test_donats.py`, `test_da_auth.py`) and the unused fixtures under `tests/data/` (`da_events.json`, `data_events.json`, `bad_currencies.json`).
- Make the container and deployment worker-only: `Dockerfile` builds/copies only the worker entry point and defaults `CMD` to `donats_worker.py`; delete `services/bot@donats_getter.service`; `.github/deploy.sh` installs/restarts only the worker and drops currencies handling.
- Update `AGENTS.md` so the documented architecture, directory layout and environment variables describe the worker-only repository.

## Capabilities

### New Capabilities

- `donations-worker`: the single remaining service's observable behavior — consuming alert messages from RabbitMQ, accepting both raw donation payloads and legacy `alert_type` payloads, formatting chat messages per event type, and publishing them to the Twitch output exchange with manual ack/reject semantics.

### Modified Capabilities

None. No existing specs cover this project; the getter's removal is a repository/deployment change, not a modification of a specified capability.

## Impact

- **Removed code:** `donats_getter.py`, `get_token.py`, `donats/donats.py`, `donats/da_auth.py`, `donats/exceptions.py`, `services/bot@donats_getter.service`.
- **Modified code:** `donats/settings.py`, `donats/utils.py`, `donats/models.py` (`map_to_fastq_message` default source), `Dockerfile`, `.dockerignore`, `.github/deploy.sh`, `AGENTS.md`, `pyproject.toml`, `uv.lock`.
- **Kept as-is:** worker entry point, `consumer.py`, `handlers.py`, `sender.py`, `publisher.py`, `schemas.py`, `queue_models.py` (the worker still parses queue payloads with `AlertEventSchema`, including the raw-donation branch).
- **Runtime config:** remaining variables are `RABBIT_URL`, `RABBIT_VHOST`, `RABBIT_ALERTS`, `TWITCH_OUT`, `DONATIONS_ALERTS`, Sentry/logging variables. `DA_*`, `CURRENCIES` and `RABBIT_EXCHANGE` are no longer read; the host no longer needs a currencies file for the worker.
- **Deployment:** the image runs only `donats_worker.py`. The legacy `bot@donats_getter` unit already installed on the production server is stopped/removed manually by the operator after this deploy; the deploy script does not touch it.
- **Risk:** the worker only produces output while an external producer publishes alerts to the consumed queue. If nothing publishes to `donations_alerts`, the bot goes silent — this is expected, since ingestion is now external.

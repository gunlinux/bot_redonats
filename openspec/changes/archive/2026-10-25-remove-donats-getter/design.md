# Design

## Context

See `proposal.md` - Why. The codebase currently has two entry points. The worker path (`donats_worker.py` → `RabbitConsumer` → `DonatEventHandler` → `Sender` → `Publisher`) is independent of the getter path (`donats_getter.py` → `DonatApi` → `AlertEventSchema` → `Publisher`); they share only `models.py`, `schemas.py`, `queue_models.py`, `settings.py`, `utils.py`, `publisher.py` and `exceptions.py`.

Constraints that shape the removal:

- Alerts are published into the second broker (`RABBIT_ALERTS`) by an external producer that forwards raw donation payloads, matching the current `AlertEventSchema.preload` branch for payloads without `alert_type`.
- The worker unit already passes `RABBIT_URL`, `RABBIT_VHOST`, `RABBIT_ALERTS`, `TWITCH_OUT` and `DONATIONS_ALERTS` through `.env`; nothing getter-specific is needed for it to run.
- The legacy `bot@donats_getter` unit remains installed on the production host after this change and is retired by the operator, not by the deploy script.

## Goals / Non-Goals

**Goals:**

- One runtime service, one entry point, one container command.
- No getter-only module, setting, dependency, test, fixture or deployment artifact left behind.
- Worker behavior and its queue/output contract unchanged.

**Non-Goals:**

- Redesigning the consumer, handler or sender, or moving the worker to typed `FQueueMessage` consumption.
- Pruning pre-existing unused settings unrelated to the getter (`BEER_URL`, `RE*`, `LOCAL_EVENTS`, `BEER_STAT`, `TWITCH_EVENTS`, `COMMAND_DIR`, `scripts_path`).
- Removing the production getter unit automatically or changing the external producer.

## Decisions

**Delete the getter path outright instead of deprecating it.** Keeping `donats/donats.py` and `da_auth.py` behind an unused flag would retain `aiohttp`, OAuth settings and their tests without a consumer. Git history preserves the code if ingestion ever returns in-repo.

**Keep `schemas.py` and its raw-donation branch.** The worker's handler still loads queue payloads through `AlertEventSchema`; the external producer sends donation payloads without `alert_type`, and `DONATIONS_ALERTS_PAYLOAD` in `test_handlers.py` depends on that branch. Removing it would break message parsing for every forwarded donation.

**Keep `models.AlertEvent` and `queue_models` unchanged apart from the default `source`.** `map_to_fastq_message` defaults to `source='donats_getter'`; both call sites pass an explicit source, so the default becomes `''` to drop the getter name. `FQueueEvent`/`FQueueMessage` remain the wire contract with the Twitch bot.

**Drop `get_currencies`, `exceptions.py` and `CURRENCIES`.** `CurrencyLoadError` has no other consumer once `get_currencies` is gone, and `DomainError` has no other subclass. `settings.CURRENCIES` and the `currencies.json` mount exist only for getter conversion.

**Remove `aiohttp` from `pyproject.toml` and regenerate `uv.lock`.** Its only importers are `donats/donats.py`, `donats/da_auth.py` and their tests; no other locked package depends on it. `marshmallow` and `marshmallow-enum` stay because `schemas.py` uses Marshmallow (`marshmallow-enum` was already unused before this change and is left alone to keep the diff focused).

**Worker-only image and unit.** `Dockerfile` copies `donats/` and `donats_worker.py` only and sets `CMD` to `donats_worker.py`; the worker unit drops its now-redundant `uv run --no-sync donats_worker.py` override. `services/bot@donats_getter.service` is deleted.

**Deploy script prunes getter artifacts but does not touch the server's legacy unit.** `UNITS` becomes `bot@donats_worker`, the guard checks the worker unit file, and the currencies resolution/`@CURRENCIES_PATH@` substitution is removed. Since `bot@donats_getter.service` is no longer installed from the repo, the operator must stop and remove the installed unit manually after deploy (documented in tasks). Alternative considered: `systemctl disable --now` plus `rm` in `deploy.sh` - rejected to keep production service lifecycle as a manual, explicit operator action.

**Delete dead test data.** `da_events.json`, `data_events.json` and `bad_currencies.json` are unreferenced; the worker tests use inline payloads in `test_schemas.py`/`test_handlers.py`.

## Risks / Trade-offs

- **Old getter keeps publishing after deploy** → the new worker performs no deduplication, so a still-running getter could double-post alerts. Mitigation: stop `bot@donats_getter.service` immediately after the deploy and verify `docker ps` shows only `donats-worker`.
- **External producer payload shape is only inferred** → ingestion happens outside the repo; if it publishes `FQueueMessage`-shaped envelopes instead of raw donation payloads, `AlertEventSchema` rejects them and messages are discarded. Mitigation: observe one message on `donations_alerts` before/after cutover; the schema keeps accepting both raw and legacy `alert_type` shapes.
- **Lost currency conversion** → amounts now reach chat in their original currency. Accepted: conversion belonged to the removed ingestion stage.
- **Lockfile drift** → `uv sync --frozen` in Docker fails if `pyproject.toml` and `uv.lock` disagree. Mitigation: regenerate with `uv lock` and run CI locally (`make lint`, `make types`, `make test`).
- **Silent worker with no producer** → expected if the external service is down; no fallback ingestion remains in this repository.

## Migration Plan

1. Merge the change; CI runs lint, types and tests on the worker-only tree.
2. Deploy builds the image with `CMD donats_worker.py` and installs/restarts only `bot@donats_worker.service`; the deploy script no longer resolves or mounts currencies.
3. Operator on `gunlinux.ru`: `sudo systemctl disable --now bot@donats_getter.service`, remove `/etc/systemd/system/bot@donats_getter.service`, `sudo systemctl daemon-reload`, and remove the host `currencies.json` symlink if no longer needed elsewhere.
4. Verify: `docker ps` shows `donats-worker` only; publish/observe a test donation on `donations_alerts` and confirm it appears in Twitch chat.
5. Rollback: redeploy the previous image tag and re-install the previous units from the pre-change commit, restoring `DA_*` and the currencies file.

# Tasks

## 1. Remove getter code

- [x] 1.1 Delete `donats_getter.py`, `donats/donats.py`, `donats/da_auth.py` and `get_token.py`; verify `grep -rn "DonatApi\|get_access_token\|donats_getter\|get_token" --include=*.py .` finds no importers or callers left in code
- [x] 1.2 Remove getter-only settings (`DA_ACCESS_TOKEN`, `DA_REFRESH_TOKEN`, `DA_TOKEN_EXPIRES_AT`, `DA_CLIENT_ID`, `DA_CLIENT_SECRET`, `DA_REDIRECT_URI`, `RABBIT_EXCHANGE`, `CURRENCIES`) from `donats/settings.py`; verify `grep -rn "DA_\|rabbit_exchange\|CURRENCIES" donats/*.py` returns nothing
- [x] 1.3 Remove `get_currencies` from `donats/utils.py`, delete `donats/exceptions.py`, and change the `map_to_fastq_message` default source in `donats/models.py` to `''`; verify `uv run ruff check donats && uv run pyright` pass
- [x] 1.4 Delete `tests/units/test_getter.py`, `tests/units/test_donats.py`, `tests/units/test_da_auth.py` and `tests/data/da_events.json`, `tests/data/data_events.json`, `tests/data/bad_currencies.json`; verify `uv run pytest -q` passes with `test_consumer.py`, `test_handlers.py` and `test_schemas.py` still collected

## 2. Worker-only runtime artifacts

- [x] 2.1 Remove `aiohttp` from `pyproject.toml`, regenerate with `uv lock`; verify `uv sync --frozen --no-dev` succeeds and `grep -n '"aiohttp' uv.lock` no longer lists it as a project dependency
- [x] 2.2 Update `Dockerfile` to copy only `donats/` and `donats_worker.py` and set `CMD ["uv", "run", "--no-sync", "donats_worker.py"]`, and drop `currencies.json` from `.dockerignore`; verify `docker build -t bot-redonats:test .` succeeds and `docker inspect --format '{{json .Config.Cmd}}' bot-redonats:test` shows the worker entry point
- [x] 2.3 Delete `services/bot@donats_getter.service` and simplify `services/bot@donats_worker.service` to run the image default command; verify `ls services` shows only `bot@donats_worker.service` and the unit contains no `@CURRENCIES_PATH@`

## 3. Deployment and documentation

- [x] 3.1 Update `.github/deploy.sh`: set `UNITS=("bot@donats_worker")`, guard on `services/bot@donats_worker.service`, and remove `CURRENCIES_DEFAULT`/currency resolution and the `@CURRENCIES_PATH@` substitution; verify `bash -n .github/deploy.sh` succeeds and `grep -n "CURRENCIES\|donats_getter" .github/deploy.sh` returns nothing
- [x] 3.2 Update `AGENTS.md` to describe the worker-only repository: single-service architecture, directory layout without getter modules/tests, environment table without `DA_*`/`CURRENCIES`/`RABBIT_EXCHANGE`, worker-only run and deploy commands, and the manual retirement of the legacy `bot@donats_getter` unit; verify every variable in the table exists in `donats/settings.py` and no `donats_getter` reference remains

## 4. Integration verification

- [x] 4.1 Run `make lint && make types && make test` and confirm all three pass on the worker-only tree
- [x] 4.2 Run `grep -rn "donats_getter\|DonatApi\|get_token\|get_currencies\|DA_ACCESS_TOKEN" . --exclude-dir=.git --exclude-dir=.venv --exclude-dir=openspec` and confirm no matches remain
- [x] 4.3 Run `uv run python -c "import donats_worker"` and confirm the worker entry point imports without removed modules

## Workflow follow-up

- After the first deploy, operator retires the installed `bot@donats_getter.service` on the server (stop/disable, remove unit, `daemon-reload`) and confirms only `donats-worker` runs.
- Publish or observe a test alert on `donations_alerts` and confirm the formatted message reaches the Twitch chat output.
- Archive the change once review and deployment verification are complete.

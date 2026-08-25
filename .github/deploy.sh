#!/bin/bash
# =============================================================================
# bot_redonats — deploy the Python container image from Docker Hub.
#
# Runs ON the server, invoked by .github/workflows/deploy.yaml over SSH with
# DEPLOY_TAG=<commit short SHA> exported. The image is built and pushed in CI
# (public repo gunlinuxloki/bot_redonats — no docker login needed here); this
# script pulls that exact tag, installs the systemd units with the tag baked
# in, and restarts the services. Idempotent: safe to re-run.
#
# Replaces the previous native `uv run` deploy; the server no longer needs a
# Python toolchain or a local build.
# =============================================================================
set -euo pipefail

REPO_DIR="/home/loki/projects/bot/bot_redonats"
BRANCH="main"
IMAGE="gunlinuxloki/bot_redonats"
CURRENCIES_DEFAULT="/home/loki/projects/bot/currency_helper/curr.json"
UNITS=("bot@donats_getter" "bot@donats_worker")

cd "$REPO_DIR" || exit 1

TAG="${DEPLOY_TAG:?DEPLOY_TAG is required (commit short SHA)}"

# Enforce the real remote so `git fetch` always pulls this repo.
git remote set-url origin git@github.com:gunlinux/bot_redonats.git

# --- 1. Pull the deployed commit ----------------------------------------------
git fetch --all
git reset --hard "origin/$BRANCH"

# Guard: refuse to run if the checkout lacks the deploy artifacts.
if [ ! -f Dockerfile ] || [ ! -f "services/bot@donats_getter.service" ]; then
    echo "ERROR: origin/$BRANCH lacks Dockerfile or systemd units — refusing to deploy." >&2
    exit 1
fi

# The legacy systemd units carry RABBIT_URL (with the AMQP password) baked in,
# while the Docker units read it from .env. One-time migration: copy it into
# .env if missing. The secret stays on the host, never in this repo.
if ! grep -q '^RABBIT_URL=' .env; then
    URL="$(grep -oP 'Environment="RABBIT_URL=\K[^"]+' /etc/systemd/system/bot@donats_getter.service 2>/dev/null | head -1)"
    if [ -n "$URL" ]; then
        printf '\nRABBIT_URL=%s\n' "$URL" >> .env
        echo "Added RABBIT_URL to .env (migrated from the legacy systemd unit)."
    else
        echo "WARNING: no RABBIT_URL in .env and could not extract it from the old unit — set it manually." >&2
    fi
fi

# docker --env-file does NOT strip quotes (unlike systemd EnvironmentFile);
# normalize any KEY="value" lines so the container gets clean env.
sed -i -E 's/^([A-Z_]+)="(.*)"$/\1=\2/' .env || true

# --- 2. Pull the image ---------------------------------------------------------
docker pull "$IMAGE:$TAG" >/dev/null

# --- 3. Resolve the currencies file (symlinked on the host) --------------------
CURR="$(readlink -f currencies.json 2>/dev/null || echo "$CURRENCIES_DEFAULT")"
if [ ! -f "$CURR" ]; then
    echo "ERROR: currencies file not found at $CURR." >&2
    exit 1
fi

# --- 4. Install the units with the commit-hash tag baked in --------------------
for unit in "${UNITS[@]}"; do
    sed -e "s|@IMAGE_TAG@|$TAG|g" -e "s|@CURRENCIES_PATH@|$CURR|g" \
        "services/$unit.service" | sudo tee "/etc/systemd/system/$unit.service" >/dev/null
done
sudo systemctl daemon-reload

# --- 5. Swap services -----------------------------------------------------------
sudo systemctl enable --now bot@donats_getter.service bot@donats_worker.service
sudo systemctl restart bot@donats_getter.service bot@donats_worker.service

echo "Deployment completed: $IMAGE:$TAG"

#!/bin/bash
# =============================================================================
# bot_redonats — deploy the Python container image from Docker Hub.
#
# Runs ON the server, invoked by .github/workflows/deploy.yaml over SSH with
# DEPLOY_TAG=<commit short SHA> exported. The image is built and pushed in CI
# (public repo gunlinuxloki/bot_redonats — no docker login needed here); this
# script pulls that exact tag, installs the worker systemd unit with the tag
# baked in, and restarts the service. Idempotent: safe to re-run.
#
# Replaces the previous native `uv run` deploy; the server no longer needs a
# Python toolchain or a local build.
# =============================================================================
set -euo pipefail

REPO_DIR="/home/loki/projects/bot/bot_redonats"
BRANCH="main"
IMAGE="gunlinuxloki/bot_redonats"
UNITS=("bot@donats_worker")

cd "$REPO_DIR" || exit 1

TAG="${DEPLOY_TAG:?DEPLOY_TAG is required (commit short SHA)}"

# Enforce the real remote so `git fetch` always pulls this repo.
git remote set-url origin git@github.com:gunlinux/bot_redonats.git

# --- 1. Pull the deployed commit ----------------------------------------------
git fetch --all
git reset --hard "origin/$BRANCH"

# Guard: refuse to run if the checkout lacks the deploy artifacts.
if [ ! -f Dockerfile ] || [ ! -f "services/bot@donats_worker.service" ]; then
    echo "ERROR: origin/$BRANCH lacks Dockerfile or the worker systemd unit — refusing to deploy." >&2
    exit 1
fi

# The Docker unit reads secrets from .env on the host. The secret stays on the
# host, never in this repo.
if ! grep -q '^RABBIT_URL=' .env; then
    echo "WARNING: no RABBIT_URL in .env — set it manually before the service starts." >&2
fi

# docker --env-file does NOT strip quotes (unlike systemd EnvironmentFile);
# normalize any KEY="value" lines so the container gets clean env.
sed -i -E 's/^([A-Z_]+)="(.*)"$/\1=\2/' .env || true

# --- 2. Pull the image ---------------------------------------------------------
docker pull "$IMAGE:$TAG" >/dev/null

# --- 3. Install the unit with the commit-hash tag baked in --------------------
for unit in "${UNITS[@]}"; do
    sed -e "s|@IMAGE_TAG@|$TAG|g" \
        "services/$unit.service" | sudo tee "/etc/systemd/system/$unit.service" >/dev/null
done
sudo systemctl daemon-reload

# --- 4. Swap services -----------------------------------------------------------
sudo systemctl enable --now bot@donats_worker.service
sudo systemctl restart bot@donats_worker.service

echo "Deployment completed: $IMAGE:$TAG"

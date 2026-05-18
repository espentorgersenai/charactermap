#!/usr/bin/env bash
set -euo pipefail

# Phase 1: build on lfc directly (no container registry needed).
# Phase 7 (GitHub Actions + GHCR) will switch to: local build → push to ghcr.io → lfc pull.
# To use the registry flow now, add image: ghcr.io/... to each service in docker-compose.yml
# and set up `docker login ghcr.io` on both local and lfc.

LFC_HOST="${LFC_HOST:-lfc}"   # SSH alias in ~/.ssh/config

LFC_REPO="${LFC_REPO:-~/ClaudeCode/charactermap}"

echo "→ Syncing code to lfc..."
ssh "$LFC_HOST" "cd $LFC_REPO && git pull"

echo "→ Building and starting on lfc..."
ssh "$LFC_HOST" "cd $LFC_REPO && docker compose build && docker compose up -d"

echo "→ Running migrations..."
ssh "$LFC_HOST" "docker exec charmap_api alembic upgrade head"

echo "✓ Deploy complete"

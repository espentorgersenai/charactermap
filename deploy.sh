#!/usr/bin/env bash
set -euo pipefail

LFC_HOST="${LFC_HOST:-lfc}"   # SSH alias in ~/.ssh/config

echo "→ Building and pushing images..."
docker compose build
docker compose push

echo "→ Deploying to lfc..."
ssh "$LFC_HOST" "cd ~/charactermap && docker compose pull && docker compose up -d"

echo "→ Running migrations..."
ssh "$LFC_HOST" "docker exec charmap_api alembic upgrade head"

echo "✓ Deploy complete"

#!/usr/bin/env bash
# Deploy Raqman to a single VPS running Caddy + PM2.
# Usage: ./scripts/deploy.sh
#
# Expects on the server:
#   - Node 20+, npm, pm2 installed globally
#   - Postgres reachable via DATABASE_URL
#   - .env present (copy from .env.example and fill values)
#
# This script does the safe steps only. It will NOT push to a different
# branch, NOT touch unrelated services, and NOT run any vendor traffic.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example and configure values."
  exit 1
fi

echo "==> install dependencies"
npm ci --no-audit --no-fund

echo "==> apply database schema"
npx prisma migrate deploy || npx prisma db push

echo "==> build"
npm run build

echo "==> reload pm2"
if pm2 describe raqman-web >/dev/null 2>&1; then
  pm2 reload ecosystem.config.cjs --update-env
else
  pm2 start ecosystem.config.cjs
fi

pm2 save

echo "==> done"

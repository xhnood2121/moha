#!/usr/bin/env bash
# One-shot local bootstrap for Raqman.
#
# What it does (idempotent):
#   1. Installs Node deps if node_modules is missing.
#   2. Ensures Postgres is installed and running (Homebrew on macOS,
#      service on Linux), creates the raqman role + database if absent.
#   3. Writes .env from .env.example with a freshly generated AUTH_SECRET.
#   4. Pushes the Prisma schema.
#   5. Optionally seeds demo data (--seed).
#   6. Prints next steps.
#
# Usage:
#   bash scripts/setup-local.sh            # bootstrap only
#   bash scripts/setup-local.sh --seed     # bootstrap + demo data

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WANT_SEED=0
for arg in "$@"; do
  case "$arg" in
    --seed) WANT_SEED=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

OS="$(uname -s)"
say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*" >&2; }
die()  { printf '\033[1;31mERR\033[0m %s\n' "$*" >&2; exit 1; }

# 1. Node deps ----------------------------------------------------------
if [ ! -d node_modules ]; then
  say "installing node dependencies"
  npm install --no-audit --no-fund
else
  say "node_modules already present (skipping npm install)"
fi

# 2. Postgres -----------------------------------------------------------
ensure_pg_macos() {
  if ! command -v brew >/dev/null 2>&1; then
    die "Homebrew not found. Install from https://brew.sh and re-run."
  fi
  if ! brew list postgresql@16 >/dev/null 2>&1; then
    say "installing postgresql@16 via Homebrew"
    brew install postgresql@16
  fi
  if ! brew services list | grep -E '^postgresql@16\s+started' >/dev/null 2>&1; then
    say "starting postgresql@16"
    brew services start postgresql@16 >/dev/null
    sleep 2
  fi
}

ensure_pg_linux() {
  if ! command -v psql >/dev/null 2>&1; then
    die "psql not found. Install postgresql-16 via your package manager."
  fi
  if ! pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    say "starting postgres service"
    if command -v service >/dev/null 2>&1; then
      sudo service postgresql start || warn "could not start postgres; ensure it is running"
    else
      warn "no service command; ensure postgres is running on 127.0.0.1:5432"
    fi
    sleep 2
  fi
}

case "$OS" in
  Darwin) ensure_pg_macos ;;
  Linux)  ensure_pg_linux ;;
  *) warn "unsupported OS '$OS' — assuming postgres is already running" ;;
esac

if ! pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
  die "postgres not reachable on 127.0.0.1:5432"
fi

# Pick a superuser. Homebrew Postgres on macOS makes the OS user the
# superuser; the Debian/Ubuntu package uses 'postgres'. Allow override
# via POSTGRES_SUPERUSER, otherwise probe.
choose_superuser() {
  if [ -n "${POSTGRES_SUPERUSER:-}" ]; then
    echo "$POSTGRES_SUPERUSER"
    return
  fi
  for cand in "${USER:-}" postgres; do
    [ -z "$cand" ] && continue
    if psql -h 127.0.0.1 -p 5432 -U "$cand" -d postgres -tAc 'SELECT 1' >/dev/null 2>&1; then
      echo "$cand"
      return
    fi
  done
  echo ""
}

if [ "$OS" = "Linux" ] && ! psql -h 127.0.0.1 -p 5432 -U "${USER:-}" -d postgres -tAc 'SELECT 1' >/dev/null 2>&1; then
  PSQL_ADMIN=(sudo -n -u postgres psql -d postgres -v ON_ERROR_STOP=1)
else
  SUPERUSER="$(choose_superuser)"
  if [ -z "$SUPERUSER" ]; then
    die "could not connect to postgres as $USER or postgres. Set POSTGRES_SUPERUSER and re-run."
  fi
  say "using postgres superuser: $SUPERUSER"
  PSQL_ADMIN=(psql -h 127.0.0.1 -p 5432 -U "$SUPERUSER" -d postgres -v ON_ERROR_STOP=1)
fi

if ! "${PSQL_ADMIN[@]}" -tAc "SELECT 1 FROM pg_roles WHERE rolname='raqman'" 2>/dev/null | grep -q 1; then
  say "creating raqman role"
  "${PSQL_ADMIN[@]}" -c "CREATE ROLE raqman LOGIN PASSWORD 'raqman' CREATEDB;" >/dev/null
else
  say "raqman role already exists"
fi

if ! "${PSQL_ADMIN[@]}" -tAc "SELECT 1 FROM pg_database WHERE datname='raqman'" 2>/dev/null | grep -q 1; then
  say "creating raqman database"
  "${PSQL_ADMIN[@]}" -c "CREATE DATABASE raqman OWNER raqman;" >/dev/null
else
  say "raqman database already exists"
fi

# 3. .env ---------------------------------------------------------------
if [ ! -f .env ]; then
  if [ ! -f .env.example ]; then
    die ".env.example missing"
  fi
  say "writing .env"
  AUTH_SECRET="$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | base64 | tr -d '/+=\n' | cut -c1-64)"
  cp .env.example .env
  # macOS sed needs an empty -i argument; use a portable temp-file approach.
  python3 - "$AUTH_SECRET" <<'PY'
import pathlib, re, sys
secret = sys.argv[1]
p = pathlib.Path(".env")
text = p.read_text()
text = re.sub(r'^DATABASE_URL=.*$',
              'DATABASE_URL="postgresql://raqman:raqman@127.0.0.1:5432/raqman?schema=public"',
              text, flags=re.M)
text = re.sub(r'^AUTH_SECRET=.*$',
              f'AUTH_SECRET="{secret}"',
              text, flags=re.M)
p.write_text(text)
PY
else
  say ".env already present (leaving as-is)"
fi

# 4. Schema -------------------------------------------------------------
say "pushing prisma schema"
npx prisma db push --skip-generate
npx prisma generate >/dev/null

# 5. Seed (optional) ----------------------------------------------------
if [ "$WANT_SEED" = "1" ]; then
  say "seeding demo data"
  npm run db:seed --silent
fi

# 6. Done ---------------------------------------------------------------
printf '\n\033[1;32m✓ ready\033[0m\n\n'
printf '  Start the dev server:\n    npm run dev\n\n'
printf '  Then open:\n    http://127.0.0.1:3000\n\n'

if [ "$WANT_SEED" = "1" ]; then
  printf '  Demo login:\n    email     demo@raqman.test\n    password  demo-password-1234\n\n'
fi

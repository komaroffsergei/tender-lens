#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker не найден." >&2
  exit 2
fi

cp -n .env.example .env || true
docker compose up -d postgres nats
docker compose run --rm migrate
docker compose run --rm crawler python -m tender_lens.crawler --once --source ted --max-items 5
docker compose run --rm crawler python -m tender_lens.crawler --once --source contracts_finder --max-items 5

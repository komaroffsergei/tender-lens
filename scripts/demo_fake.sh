#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker не найден. Установите Docker Engine/Compose и повторите make demo-fake." >&2
  exit 2
fi

cp -n .env.example .env || true
export AI_MODE=fake

docker compose up -d postgres nats
docker compose run --rm migrate
docker compose up -d indexer api

docker compose run --rm api python -m tender_lens.cli seed-demo --fixture-dir /app/examples/fixtures

for _ in $(seq 1 60); do
  ready=$(docker compose exec -T postgres psql -U tender_lens -d tender_lens -Atc \
    "select count(*) from tenders where index_status='ready';" 2>/dev/null || echo 0)
  if [ "${ready}" -ge 2 ]; then break; fi
  sleep 1
done

key_json=$(docker compose run --rm api python -m tender_lens.cli create-api-key --name demo-$(date +%s) --limit 5)
api_key=$(printf '%s' "$key_json" | python -c 'import json,sys; print(json.load(sys.stdin)["api_key"])')

for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8000/health/live >/dev/null; then break; fi
  sleep 1
done

printf '\nSEARCH:\n'
curl -fsS -H "X-API-Key: $api_key" -H 'Content-Type: application/json' \
  -d '{"query":"server equipment storage warranty","limit":5}' \
  http://localhost:8000/api/v1/search | python -m json.tool

printf '\nASK:\n'
curl -fsS -H "X-API-Key: $api_key" -H 'Content-Type: application/json' \
  -d '{"query":"What server and storage equipment is required?","limit":5}' \
  http://localhost:8000/api/v1/ask | python -m json.tool

for _ in 1 2 3; do
  curl -fsS -o /dev/null -H "X-API-Key: $api_key" -H 'Content-Type: application/json' \
    -d '{"query":"server equipment","limit":1}' http://localhost:8000/api/v1/search
done

status=$(curl -sS -o /tmp/tender-lens-429.json -w '%{http_code}' \
  -H "X-API-Key: $api_key" -H 'Content-Type: application/json' \
  -d '{"query":"server equipment","limit":1}' http://localhost:8000/api/v1/search)
if [ "$status" != "429" ]; then
  echo "Ожидался 429, получен $status" >&2
  cat /tmp/tender-lens-429.json >&2
  exit 1
fi

printf '\nRATE LIMIT: шестой общий запрос получил HTTP 429.\n'
printf 'UI: http://localhost:8000\nAPI key текущего demo: %s\n' "$api_key"

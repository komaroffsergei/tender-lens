#!/usr/bin/env bash
set -euo pipefail

: "${API_URL:=http://localhost:8000}"
: "${TENDER_LENS_API_KEY:?Set TENDER_LENS_API_KEY}"

curl --fail-with-body \
  -H "X-API-Key: ${TENDER_LENS_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/api/search-request.json \
  "${API_URL}/api/v1/search"

curl --fail-with-body \
  -H "X-API-Key: ${TENDER_LENS_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/api/ask-request.json \
  "${API_URL}/api/v1/ask"

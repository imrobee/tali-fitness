#!/usr/bin/env bash
# Sends a Shortcut payload to the local API, the same way the iPhone does.
#
# Usage: scripts/send_sample_shortcut_payload.sh [payload.json] [base_url]
#   payload.json  default: docs/samples/health_payload_01.json
#   base_url      default: http://localhost:8000
#
# Note: this writes to the database the API uses (your local warehouse). The samples
# are real days with a made-up weight; your next real Shortcut push for the same days
# replaces their calories and protein.
set -euo pipefail
cd "$(dirname "$0")/.."

payload="${1:-docs/samples/health_payload_01.json}"
base_url="${2:-http://localhost:8000}"
# Read the key from .env without printing it.
api_key="$(grep '^API_KEY=' .env | cut -d= -f2-)"

curl --silent --show-error \
  --header "Content-Type: application/json" \
  --header "X-API-Key: ${api_key}" \
  --data-binary "@${payload}" \
  "${base_url}/api/v1/ingest/health"
echo

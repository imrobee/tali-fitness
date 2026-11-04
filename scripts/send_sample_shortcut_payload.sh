#!/usr/bin/env bash
# Sends a Shortcut payload to the local API, the same way the iPhone does.
#
# Usage: INGEST_TOKEN=ing_... scripts/send_sample_shortcut_payload.sh [payload.json] [base_url]
#   payload.json  default: docs/samples/health_payload_01.json
#   base_url      default: http://localhost:8000
#
# INGEST_TOKEN is the Shortcut's token (from scripts/make_ingest_token.py). It comes from
# the environment only, never from a file: .env holds just its hash. To keep it out of
# shell history, read it without echo first:  read -rs INGEST_TOKEN && export INGEST_TOKEN
#
# Note: this writes to the database the API uses (your local warehouse). The samples
# are real days with a made-up weight; your next real Shortcut push for the same days
# replaces their calories and protein.
set -euo pipefail
cd "$(dirname "$0")/.."

payload="${1:-docs/samples/health_payload_01.json}"
base_url="${2:-http://localhost:8000}"
if [[ -z "${INGEST_TOKEN:-}" ]]; then
  echo "Set INGEST_TOKEN first (see the usage at the top of this script)." >&2
  exit 1
fi

curl --silent --show-error \
  --header "Content-Type: application/json" \
  --header "Authorization: Bearer ${INGEST_TOKEN}" \
  --data-binary "@${payload}" \
  "${base_url}/api/v1/ingest/health"
echo

#!/bin/sh
# Leak check for the front-end bundle (docs/AUTH_SPEC.md section 11).
#
# Builds the app with an obvious canary in every secret-named variable, plain and with
# Vite's VITE_ prefix (the only variables Vite will put into the bundle), then searches the
# built files for each canary and for secret-shaped strings. Any hit fails the check.
set -eu
cd "$(dirname "$0")/.."

NAMES="API_KEY DEV_LOGIN_KEY GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET OAUTH_STATE_SECRET
ALLOWED_GOOGLE_SUB INGEST_TOKEN_SHA256 INGEST_TOKEN_SHA256_NEXT WAREHOUSE_URL
POSTGRES_PASSWORD STRAVA_CLIENT_SECRET AIRFLOW_ADMIN_PASSWORD"

for name in $NAMES; do
  export "$name=canary-bundle-$name"
  export "VITE_$name=canary-bundle-$name"
done

npm run build >/dev/null

# The canaries, Google client secrets (GOCSPX-...), ingest tokens and a 64-hex hash.
if grep -rEo "canary-bundle-[A-Z_0-9]+|GOCSPX-[A-Za-z0-9_-]+|ing_[A-Za-z0-9_-]{20,}|[0-9a-f]{64}" dist; then
  echo "Secret-like values found in the bundle (above)." >&2
  exit 1
fi
echo "Bundle check: no canary or secret-shaped value in dist/."

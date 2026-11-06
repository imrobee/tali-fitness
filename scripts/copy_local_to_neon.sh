#!/bin/sh
# One time, at the first deploy (docs/ARCHITECTURE.md section 13c, D131): copy the rows of
# the local warehouse ("app" in Docker) into Neon's "app" database, which the migrations
# have already built. Your health history exists only here, so it must come along; so do
# the Strava tokens, the targets and the pipeline's history. Browser sessions do not.
#
# Usage, from the repository root, with Neon's owner URL in a shell variable (never a file):
#     read -s NEON_OWNER_URL        # paste the direct (not pooled) URL, press Enter
#     export NEON_OWNER_URL
#     sh scripts/copy_local_to_neon.sh
#
# What it does, in one transaction on Neon (any error and Neon is left as it was):
#   1. refuses to go on if Neon already holds Strava or health data (a second run after
#      going live would otherwise wipe production),
#   2. empties Neon's data tables (only the rows the migrations seeded are there),
#   3. loads the local rows (pg_dump --data-only: rows only, no schema; the migrations
#      made the schema).
# Reads the local database; never changes it.
set -eu

: "${NEON_OWNER_URL:?Set NEON_OWNER_URL first: read -s NEON_OWNER_URL, then export it.}"

GUARD="DO \$\$ BEGIN
  IF (SELECT count(*) FROM raw.strava_activities) + (SELECT count(*) FROM raw.health_batches) > 0 THEN
    RAISE EXCEPTION 'Neon already has Strava or health data: not copying over it.';
  END IF;
END \$\$;"

EMPTY="DO \$\$ DECLARE t record; BEGIN
  FOR t IN SELECT schemaname, tablename FROM pg_tables
           WHERE schemaname IN ('raw', 'core', 'mart', 'ops', 'app') LOOP
    EXECUTE format('TRUNCATE %I.%I CASCADE', t.schemaname, t.tablename);
  END LOOP;
END \$\$;"

{
  echo "$GUARD"
  echo "$EMPTY"
  docker compose exec -T postgres pg_dump -U fitness -d app \
    --data-only --no-owner --no-privileges \
    --exclude-table=public.alembic_version \
    --exclude-table-data=app.session
} | docker compose exec -T -e NEON_OWNER_URL postgres \
    sh -c 'psql "$NEON_OWNER_URL" --single-transaction -v ON_ERROR_STOP=1 -q'

echo "Copied. Compare the counts with the local ones."

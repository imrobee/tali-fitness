#!/bin/sh
# The demo service's start command (DECISIONS D119). Rebuild the demo as of now (it is
# idempotent: same seed, same story, dated to end today), then serve it.
#
# Two credentials, both for the demo database only: DEMO_SEED_URL (demo_writer) builds
# it, and WAREHOUSE_URL (demo_reader, SELECT only) is all the API itself uses.
set -e
python /scripts/seed_demo.py load midweek
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}"

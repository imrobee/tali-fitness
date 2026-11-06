#!/bin/sh
# The demo's clock is never frozen by default (DECISIONS D124). api-demo and demo-seed take
# NOW_OVERRIDE only from DEMO_NOW_OVERRIDE, which `make screenshots` alone sets. A date
# written into docker-compose.yml would freeze the demo on that day, as happened once.
set -e
if grep -nE 'NOW_OVERRIDE: "?[0-9]' docker-compose.yml; then
  echo "docker-compose.yml: a hard-coded NOW_OVERRIDE would freeze the demo's clock."
  exit 1
fi
echo "Demo clock: real time by default."

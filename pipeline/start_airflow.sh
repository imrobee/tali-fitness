#!/usr/bin/env bash
# Starts Airflow for local development.
#
# Why this script: Airflow 3's simple auth manager normally generates a random
# password per user. It reads passwords from a JSON file, so we write that file
# from .env first, making the login AIRFLOW_ADMIN_USER / AIRFLOW_ADMIN_PASSWORD.
#
# Why `airflow standalone`: it runs the api-server, scheduler, dag-processor and
# triggerer in one container with the LocalExecutor (no Celery, no Redis), which
# is the lightest official way to run Airflow for development.
set -euo pipefail

python - <<'EOF'
import json
import os

path = os.environ["AIRFLOW__CORE__SIMPLE_AUTH_MANAGER_PASSWORDS_FILE"]
with open(path, "w") as passwords_file:
    json.dump({os.environ["AIRFLOW_ADMIN_USER"]: os.environ["AIRFLOW_ADMIN_PASSWORD"]}, passwords_file)
EOF

exec airflow standalone

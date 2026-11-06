"""Create (or update) the login the API and the pipeline job use in production (D115, D134).

Usage, once, from this Mac, after the migrations (docs/ARCHITECTURE.md section 13c):
    docker compose run --rm --no-deps -e ADMIN_URL -e API_ROLE_PASSWORD \
        api python /scripts/setup_prod_role.py

ADMIN_URL: Neon's direct URL for the "app" database, as the owner of its tables (the role
that ran the migrations). API_ROLE_PASSWORD: a new password for the role `app_api`.

`app_api` may read and write rows in the data schemas and run the SQL functions; it may
not create, alter or drop anything, so a bug or a stolen API credential can't change the
schema. It is created with SQL, so it gets none of Neon's console-role rights. Prints
nothing secret: the statements carry the password and are never shown.
"""

import os
import sys

from sqlalchemy import Engine, create_engine

from app.demo.setup import ensure_role, run_built

ROLE = "app_api"


def setup_role(admin: Engine, role: str, password: str) -> None:
    """Create or update `role`, then grant it rows only (db/sql/prod/api_grants.sql)."""
    with admin.begin() as conn:
        ensure_role(conn, role, password)
        run_built(conn, "prod/api_grants.sql", {"role": role})


def main() -> int:
    admin_url = os.environ.get("ADMIN_URL", "")
    password = os.environ.get("API_ROLE_PASSWORD", "")
    if not admin_url or len(password) < 24:
        print("Set ADMIN_URL and API_ROLE_PASSWORD (24+ characters).", file=sys.stderr)
        return 2
    # hide_parameters: a failed statement must never print the password.
    setup_role(create_engine(admin_url, hide_parameters=True), ROLE, password)
    print(f"Role {ROLE}: ready (rows only, no DDL).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

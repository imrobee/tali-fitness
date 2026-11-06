"""Build the demo database and load a scenario into it (UI_SPEC.md section 11, D118, D119).

Usage (in the demo-seed container; see `make seed-demo` and `make screenshots`):
    python /scripts/seed_demo.py setup              # admin: roles, lock the real DBs, recreate
    python /scripts/seed_demo.py load [scenario]    # writer: midweek (default), at_risk, edge_empty

`load` replays the scenario's synthetic Strava and Shortcut payloads through the real
pipeline code (app/demo/replay.py), in one transaction under an advisory lock. It empties
the demo database first, so it is safe to run again at any time: by hand
(`make demo-reseed`) or by the daily GitHub Actions job (.github/workflows/demo-reseed.yml).

The demo's "now" is NOW_OVERRIDE when set (the screenshots freeze Sat 2026-10-17 14:00),
otherwise the real time, so the public demo's streak always ends today.

Safety: it only ever touches a database whose name ends in "_demo". `setup` is the only
step with an administrator's URL (DEMO_ADMIN_URL) and runs on this Mac only; `load` uses
demo_seed (DEMO_SEED_URL), which owns the demo database and can open nothing else.
"""

import os
import sys
from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from app.demo.replay import ReseedBusy, replay
from app.demo.scenario import SCENARIOS, build
from app.demo.setup import DemoRoles, prepare_demo_database


def setup() -> None:
    # hide_parameters: a failed role statement would otherwise print its password.
    admin = create_engine(
        make_url(os.environ["DEMO_ADMIN_URL"]), isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    seed_url = make_url(os.environ["DEMO_SEED_URL"])
    roles = DemoRoles(
        reader=os.environ.get("DEMO_READER_ROLE", "demo_reader"),
        reader_password=os.environ["DEMO_READER_PASSWORD"],
        writer=seed_url.username,
        writer_password=seed_url.password,
    )
    lock = [name for name in os.environ.get("DEMO_LOCK_DATABASES", "").split(",") if name]
    prepare_demo_database(admin, seed_url.database, roles, lock)
    admin.dispose()
    print(f"Demo database {seed_url.database} ready; locked: {', '.join(lock) or 'none'}.")


def demo_now() -> datetime:
    override = os.environ.get("NOW_OVERRIDE", "")
    return datetime.fromisoformat(override) if override else datetime.now(UTC)


def load(name: str) -> None:
    if name not in SCENARIOS:
        sys.exit(f"Unknown scenario {name!r}. Choose one of: {', '.join(SCENARIOS)}.")
    engine = create_engine(make_url(os.environ["DEMO_SEED_URL"]), hide_parameters=True)
    scenario = build(name, demo_now())
    try:
        seconds = replay(engine, scenario)
    except ReseedBusy as busy:
        print(busy)  # not a failure: the other rebuild gives the same result
        return
    finally:
        engine.dispose()
    print(f"Demo scenario {name!r} as of {scenario.today} built in {seconds:.1f}s.")


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "setup":
        setup()
    elif command == "load":
        load(sys.argv[2] if len(sys.argv) > 2 else "midweek")
    else:
        sys.exit("Usage: seed_demo.py setup | load [scenario]")


if __name__ == "__main__":
    main()

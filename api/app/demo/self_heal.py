"""When a demo visit starts on stale data, ask GitHub Actions to rebuild it (D121).

The demo is rebuilt every day by the demo-reseed workflow (.github/workflows). If that
ever misses (GitHub delays or drops scheduled runs under load, and switches schedules off
after 60 days without activity in a public repository), the first visitor of the day
starts the same workflow by hand. The visitor never waits: this runs after the response,
and they see the existing data until the rebuild commits.

The demo service holds no database write credential for this: it only asks GitHub, with
a token that can start workflows in one repository. Single flight on three levels: at
most one ask per 30 minutes here, one run at a time in the workflow (concurrency), and
one rebuild at a time in the database (the reseed's advisory lock).
"""

import threading
from datetime import datetime, timedelta

import httpx2
from sqlalchemy import Engine

from app.config import Settings
from app.db import load_sql
from app.github import dispatch_workflow

STALE_AFTER = timedelta(hours=24)
ASK_AT_MOST_EVERY = timedelta(minutes=30)
WORKFLOW = "demo-reseed.yml"


def is_stale(seeded_at: datetime | None, now: datetime) -> bool:
    return seeded_at is None or now - seeded_at > STALE_AFTER


class SelfHeal:
    """One per demo app (app.state.self_heal). transport: a fake GitHub, in tests."""

    def __init__(self, settings: Settings, transport: httpx2.BaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport
        self.last_asked: datetime | None = None
        self.lock = threading.Lock()  # background tasks run in worker threads

    def check(self, engine: Engine, now: datetime) -> bool:
        """Ask for a rebuild if the data is over a day old. True when GitHub accepted."""
        if self.settings.demo_reseed_token is None:
            return False  # not set up (as on this Mac): the schedule alone rebuilds
        with engine.connect() as conn:
            state = conn.execute(load_sql("demo/seed_state_read.sql")).first()
        if not is_stale(state.seeded_at if state else None, now):
            return False
        with self.lock:
            if self.last_asked and now - self.last_asked < ASK_AT_MOST_EVERY:
                return False
            self.last_asked = now
        return self.ask_github()

    def ask_github(self) -> bool:
        """Start the demo-reseed workflow now (app/github.py). The token is never logged."""
        return dispatch_workflow(
            self.settings.demo_reseed_repo or "",
            WORKFLOW,
            self.settings.demo_reseed_token,
            transport=self.transport,
        )

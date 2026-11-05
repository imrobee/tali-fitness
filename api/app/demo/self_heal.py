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

import logging
import threading
from datetime import datetime, timedelta

import httpx2
from sqlalchemy import Engine

from app.config import Settings
from app.db import load_sql

logger = logging.getLogger(__name__)

STALE_AFTER = timedelta(hours=24)
ASK_AT_MOST_EVERY = timedelta(minutes=30)
WORKFLOW = "demo-reseed.yml"
BRANCH = "main"  # GitHub dispatches only workflows on the default branch
GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"  # the current version on docs.github.com, 2026-11-05


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
        """POST .../actions/workflows/demo-reseed.yml/dispatches (docs.github.com, REST
        "Create a workflow dispatch event"). The token is never logged."""
        repo = self.settings.demo_reseed_repo
        url = f"{GITHUB_API}/repos/{repo}/actions/workflows/{WORKFLOW}/dispatches"
        headers = {
            "Authorization": f"Bearer {self.settings.demo_reseed_token.get_secret_value()}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        }
        try:
            with httpx2.Client(transport=self.transport, timeout=10) as client:
                response = client.post(url, json={"ref": BRANCH}, headers=headers)
        except httpx2.HTTPError as error:
            logger.warning("demo_reseed_ask_failed error=%s", type(error).__name__)
            return False
        logger.info("demo_reseed_asked status=%s", response.status_code)
        return response.is_success

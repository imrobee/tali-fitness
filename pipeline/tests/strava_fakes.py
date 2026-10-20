"""A fake Strava API for tests, built from the recorded sample. Tests never call Strava."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from include.strava.time_fields import utc_start

SAMPLE_PATH = Path("/opt/airflow/samples/strava_activity_detail_01.json")
SAMPLE = json.loads(SAMPLE_PATH.read_text())
MANILA_OFFSET = timedelta(hours=8)


def make_activity(
    activity_id: int, start: datetime, description: str = "Logged with hevyapp.com"
) -> dict:
    """A detail payload shaped like the recorded sample, with its own id and start time."""
    activity = copy.deepcopy(SAMPLE)
    activity["id"] = activity_id
    activity["start_date"] = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Same quirk as real Strava: local wall-clock time, still written with a "Z".
    activity["start_date_local"] = (start + MANILA_OFFSET).strftime("%Y-%m-%dT%H:%M:%SZ")
    activity["description"] = description
    # Real payloads carry location data (the committed sample had it redacted).
    # Made-up coordinates, so tests can prove these fields are never stored.
    activity["start_latlng"] = [1.0, 2.0]
    activity["end_latlng"] = [1.1, 2.1]
    activity["map"] = {"id": f"a{activity_id}", "polyline": "fake", "summary_polyline": "fake"}
    activity["segment_efforts"] = [
        {"segment": {"start_latlng": [1.0, 2.0], "end_latlng": [1.1, 2.1], "city": "Faketown"}}
    ]
    return activity


class FakeStrava:
    """Same four methods as StravaClient. `fail_on_detail` makes detail call N raise `failure`."""

    def __init__(
        self,
        activities: list[dict],
        fail_on_detail: int | None = None,
        failure: Exception | None = None,
    ) -> None:
        self.activities = {activity["id"]: activity for activity in activities}
        self.fail_on_detail = fail_on_detail
        self.failure = failure or ConnectionError("simulated crash")
        self.detail_calls = 0
        self.refreshed_with: list[str] = []

    def edit_description(self, activity_id: int, description: str) -> None:
        self.activities[activity_id]["description"] = description

    def list_activities(
        self, access_token: str, after_epoch: int, page: int, per_page: int
    ) -> list[dict]:
        after = datetime.fromtimestamp(after_epoch, UTC)
        matching = sorted(
            (a for a in self.activities.values() if utc_start(a) > after), key=utc_start
        )
        page_items = matching[(page - 1) * per_page : page * per_page]
        # Like the real list endpoint: summaries have no description.
        return [{k: v for k, v in a.items() if k != "description"} for a in page_items]

    def get_activity(self, access_token: str, activity_id: int) -> dict:
        self.detail_calls += 1
        if self.fail_on_detail is not None and self.detail_calls == self.fail_on_detail:
            raise self.failure
        return copy.deepcopy(self.activities[activity_id])

    def refresh(self, refresh_token: str) -> dict:
        self.refreshed_with.append(refresh_token)
        return {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_at": int((datetime.now(UTC) + timedelta(hours=6)).timestamp()),
        }

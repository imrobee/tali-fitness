"""Slice 0 spike: confirm which Strava fields we get for a Hevy session.

Run from the repo root:  python3 scripts/spikes/strava_spike.py
Optional:                python3 scripts/spikes/strava_spike.py <activity_id>

Standard library only. Tokens stay in memory and are never printed or saved.
Raw responses go to spike_out/ (gitignored). A redacted copy of the detail
response goes to docs/samples/ for review before committing.
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://www.strava.com/api/v3"
AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
TOKEN_URL = "https://www.strava.com/oauth/token"
# activity:read_all is needed to see activities set to "Only You" (Strava auth docs).
SCOPE = "read,activity:read_all"
REDIRECT_URI = "http://localhost/exchange_token"

OUT_DIR = Path("spike_out")
SAMPLE_PATH = Path("docs/samples/strava_activity_detail_01.json")

# Fields we need for the pipeline; the report shows where each one appears.
FIELDS_TO_CHECK = [
    "description", "sport_type", "type", "name", "start_date", "start_date_local",
    "timezone", "utc_offset", "elapsed_time", "moving_time", "distance",
    "average_heartrate", "calories", "device_name", "private", "visibility",
]

# Allowlist for the committed sample: anything not listed (GPS, map, athlete,
# location, gear, photos, segment efforts) is dropped.
SAMPLE_KEYS = FIELDS_TO_CHECK + ["max_heartrate", "has_heartrate", "manual", "trainer"]
FAKE_ID = 1000000001


def read_env_file(path: Path) -> dict[str, str]:
    """Read KEY=VALUE lines from .env (no quotes handling beyond stripping)."""
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def extract_code(pasted: str) -> str:
    """Accept either the full redirect URL or just the code."""
    pasted = pasted.strip()
    if pasted.startswith("http"):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query)
        if "error" in query:
            sys.exit(f"Strava returned an error: {query['error'][0]}")
        return query["code"][0]
    return pasted


def post_form(url: str, fields: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(fields).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data)) as resp:
        return json.load(resp)


def get_json(path: str, token: str) -> tuple[object, dict[str, str]]:
    """GET an API path; return the parsed body and the response headers."""
    request = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request) as resp:
        return json.load(resp), dict(resp.headers)


def save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"  saved {path}")


def pick_activity_id(activities: list[dict]) -> int | None:
    """Prefer a WeightTraining activity whose description we can then inspect."""
    for activity in activities:
        if activity.get("sport_type") == "WeightTraining":
            return activity["id"]
    return None


def print_field_report(summary: dict, detail: dict) -> None:
    print("\nField          in list   in detail")
    for field in FIELDS_TO_CHECK:
        in_list = "yes" if field in summary else "no"
        in_detail = "yes" if field in detail else "no"
        print(f"  {field:<18} {in_list:<9} {in_detail}")

    print("\nRaw time fields (detail):")
    for field in ["start_date", "start_date_local", "timezone", "utc_offset"]:
        print(f"  {field}: {detail.get(field)!r}")

    description = detail.get("description") or ""
    print(f"\nDescription has the Hevy marker: {'Logged with hevyapp.com' in description}")
    print("First lines of description:")
    for line in description.splitlines()[:5]:
        print(f"  | {line}")


def print_rate_limits(headers: dict[str, str]) -> None:
    print("\nRate limit headers (15-min usage, daily usage):")
    for name in ["X-RateLimit-Limit", "X-RateLimit-Usage",
                 "X-ReadRateLimit-Limit", "X-ReadRateLimit-Usage"]:
        # Header name case can vary, so match case-insensitively.
        value = next((v for k, v in headers.items() if k.lower() == name.lower()), None)
        print(f"  {name}: {value}")


def redact_for_sample(detail: dict) -> dict:
    sample = {key: detail[key] for key in SAMPLE_KEYS if key in detail}
    sample["id"] = FAKE_ID
    return sample


def main() -> None:
    env = read_env_file(Path(".env"))
    client_id = env.get("STRAVA_CLIENT_ID")
    client_secret = env.get("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit("Put STRAVA_CLIENT_ID and STRAVA_CLIENT_SECRET in .env at the repo root.")

    # Step 1: authorize in the browser.
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "approval_prompt": "force",
        "scope": SCOPE,
    })
    print("1. Open this URL, approve (keep the private-activities box ticked):\n")
    print(f"   {AUTHORIZE_URL}?{params}\n")
    print("   The browser then fails to load localhost. That is expected.")
    code = extract_code(input("2. Paste the full URL from the address bar: "))

    # Step 2: exchange the one-time code for tokens (kept in memory only).
    tokens = post_form(TOKEN_URL, {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    })
    access_token = tokens["access_token"]
    granted = tokens.get("scope", "(not returned)")
    print(f"\nToken OK. Granted scope: {granted}")
    if "activity:read_all" not in granted:
        print("  WARNING: activity:read_all not granted; 'Only You' activities will be missing.")

    # Step 3: list recent activities.
    print("\n3. Listing recent activities...")
    activities, _ = get_json("/athlete/activities?per_page=30", access_token)
    save_json(OUT_DIR / "strava_list.json", activities)
    print(f"  {len(activities)} activities returned")

    # Step 4: fetch one detail (WeightTraining by default, or the id passed in).
    activity_id = int(sys.argv[1]) if len(sys.argv) > 1 else pick_activity_id(activities)
    if activity_id is None:
        sys.exit("No WeightTraining activity in the last 30. Rerun with an activity id.")
    print(f"\n4. Fetching detail for activity {activity_id}...")
    detail, headers = get_json(f"/activities/{activity_id}", access_token)
    save_json(OUT_DIR / "strava_detail.json", detail)

    summary = next((a for a in activities if a["id"] == activity_id), {})
    print_field_report(summary, detail)
    print_rate_limits(headers)

    # Step 5: redacted sample for docs/samples (review before committing).
    print("\n5. Writing redacted sample...")
    save_json(SAMPLE_PATH, redact_for_sample(detail))
    print("\nDone. Review the sample file before committing it.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        # The body explains what went wrong (bad code, wrong scope, rate limit).
        sys.exit(f"HTTP {error.code} from {error.url}: {error.read().decode()[:500]}")

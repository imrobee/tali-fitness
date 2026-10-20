"""One-time Strava authorization. Run with `make strava-auth`.

Same flow as the Slice 0 spike, but the tokens are saved to ops.oauth_tokens so the
strava_sync DAG can refresh them from then on. Tokens are never printed.
"""

import sys
import urllib.parse

from include.db import get_engine
from include.strava.client import StravaClient
from include.strava.sync import save_tokens

AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
# activity:read_all is needed to see activities set to "Only You".
SCOPE = "read,activity:read_all"
REDIRECT_URI = "http://localhost/exchange_token"


def extract_code(pasted: str) -> str:
    """Accept the full redirect URL from the browser, or just the code."""
    pasted = pasted.strip()
    if not pasted.startswith("http"):
        return pasted
    query = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query)
    if "error" in query:
        sys.exit(f"Strava returned an error: {query['error'][0]}")
    return query["code"][0]


def main() -> None:
    client = StravaClient.from_env()
    params = urllib.parse.urlencode(
        {
            "client_id": client.client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "approval_prompt": "force",
            "scope": SCOPE,
        }
    )
    print("1. Open this URL and approve (keep the private-activities box ticked):\n")
    print(f"   {AUTHORIZE_URL}?{params}\n")
    print("   The browser then fails to load localhost. That is expected.")
    code = extract_code(input("2. Paste the full URL from the address bar: "))

    tokens = client.exchange_code(code)
    with get_engine().begin() as conn:
        save_tokens(conn, tokens)

    granted = tokens.get("scope", "")
    print(f"\nSaved to ops.oauth_tokens. Granted scope: {granted}")
    if "activity:read_all" not in granted:
        print("WARNING: activity:read_all not granted; 'Only You' activities will be missing.")


if __name__ == "__main__":
    main()

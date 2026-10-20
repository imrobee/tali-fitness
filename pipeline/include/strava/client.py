"""Small Strava API client (standard library only).

Tests never call this class: they pass a fake with the same four methods
(ARCHITECTURE.md section 6.1, "never call the live Strava API in tests").
Endpoints and limits checked against developers.strava.com on 2026-10-20.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"
TIMEOUT_SECONDS = 30


class RateLimitError(Exception):
    """Strava returned 429. Its 15-minute window resets at :00, :15, :30 and :45."""


class StravaClient:
    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    @classmethod
    def from_env(cls) -> "StravaClient":
        return cls(os.environ["STRAVA_CLIENT_ID"], os.environ["STRAVA_CLIENT_SECRET"])

    def exchange_code(self, code: str) -> dict:
        """One-time: trade the code from the authorize redirect for tokens."""
        return self._post_form(
            TOKEN_URL,
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )

    def refresh(self, refresh_token: str) -> dict:
        """Get a fresh access token. The response may contain a new refresh token."""
        return self._post_form(
            TOKEN_URL,
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

    def list_activities(
        self, access_token: str, after_epoch: int, page: int, per_page: int
    ) -> list[dict]:
        """Summaries of activities that started after `after_epoch`. No description field."""
        query = urllib.parse.urlencode({"after": after_epoch, "page": page, "per_page": per_page})
        return self._get_json(f"/athlete/activities?{query}", access_token)

    def get_activity(self, access_token: str, activity_id: int) -> dict:
        """Full activity, including the description that holds Hevy's sets."""
        return self._get_json(f"/activities/{activity_id}", access_token)

    def _get_json(self, path: str, access_token: str):
        request = urllib.request.Request(
            API + path, headers={"Authorization": f"Bearer {access_token}"}
        )
        return self._send(request)

    def _post_form(self, url: str, fields: dict) -> dict:
        data = urllib.parse.urlencode(fields).encode()
        return self._send(urllib.request.Request(url, data=data))

    def _send(self, request: urllib.request.Request):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            # The URL and body explain the problem; neither contains a token.
            body = error.read().decode(errors="replace")[:300]
            if error.code == 429:
                raise RateLimitError(f"Strava rate limit reached: {body}") from error
            raise RuntimeError(f"Strava HTTP {error.code} for {error.url}: {body}") from error

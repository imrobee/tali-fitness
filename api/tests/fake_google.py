"""A fake Google for the sign-in tests (docs/AUTH_SPEC.md section 12): no real network in CI.

It answers the three calls Authlib makes (the discovery document, Google's public keys, and
the token endpoint) through an httpx2 MockTransport, with its own RSA key pair. Each test
can change what the ID token says, or how it is signed, to check that the app refuses it.
"""

import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

import httpx2
from joserfc import jwt
from joserfc.jwk import RSAKey

ISSUER = "https://accounts.google.com"
METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"

# Obviously fake canaries: none may ever appear in a log or a response body.
CLIENT_ID = "canary-client-id.apps.googleusercontent.com"
CLIENT_SECRET = "canary-google-client-secret"
ACCESS_TOKEN = "canary-google-access-token"
EMAIL = "canary-person@example.com"
KEY_ID = "fake-google-key"


def s256(verifier: str) -> str:
    """The PKCE S256 challenge for a verifier (RFC 7636)."""
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def json_response(status: int, body: dict) -> httpx2.Response:
    return httpx2.Response(
        status, content=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )


class FakeGoogle:
    def __init__(self) -> None:
        self.key = RSAKey.generate_key(2048, parameters={"kid": KEY_ID})
        self.transport = httpx2.MockTransport(self.handle)
        self.reset("unset-sub")

    def reset(self, sub: str) -> None:
        """Back to an honest Google that signs in `sub`."""
        self.sub = sub
        self.claim_changes: dict = {}  # e.g. {"aud": "someone-else"}
        self.sign_with = self.key
        self.send_id_token = True
        self.codes: dict[str, tuple[str, str]] = {}  # code -> (nonce, PKCE challenge)
        self.id_tokens_issued: list[str] = []

    def approve(self, login_location: str) -> tuple[str, str]:
        """The user says yes on Google's page: returns the (code, state) of the callback."""
        query = parse_qs(urlsplit(login_location).query)
        code = f"canary-code-{len(self.codes) + 1}"
        self.codes[code] = (query["nonce"][0], query["code_challenge"][0])
        return code, query["state"][0]

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        url = str(request.url).split("?")[0]
        if url == METADATA_URL:
            return json_response(
                200,
                {
                    "issuer": ISSUER,
                    "authorization_endpoint": AUTHORIZE_URL,
                    "token_endpoint": TOKEN_URL,
                    "jwks_uri": JWKS_URL,
                    "id_token_signing_alg_values_supported": ["RS256"],
                    "code_challenge_methods_supported": ["plain", "S256"],
                },
            )
        if url == JWKS_URL:
            return json_response(200, {"keys": [self.key.as_dict(private=False)]})
        if url == TOKEN_URL and request.method == "POST":
            return self.token(parse_qs(request.read().decode()))
        return json_response(404, {"error": "not_found"})

    def token(self, form: dict[str, list[str]]) -> httpx2.Response:
        code = form.get("code", [""])[0]
        verifier = form.get("code_verifier", [""])[0]
        if code not in self.codes:
            return json_response(400, {"error": "invalid_grant"})  # unknown or used code
        nonce, challenge = self.codes.pop(code)  # a code works once
        if s256(verifier) != challenge:
            return json_response(400, {"error": "invalid_grant"})  # PKCE mismatch
        now = int(time.time())
        claims = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": self.sub,
            "email": EMAIL,
            "iat": now,
            "exp": now + 3600,
            "nonce": nonce,
        }
        claims.update(self.claim_changes)
        id_token = jwt.encode({"alg": "RS256", "kid": KEY_ID}, claims, self.sign_with)
        self.id_tokens_issued.append(id_token)
        body = {"access_token": ACCESS_TOKEN, "token_type": "Bearer", "expires_in": 3600}
        if self.send_id_token:
            body["id_token"] = id_token
        return json_response(200, body)

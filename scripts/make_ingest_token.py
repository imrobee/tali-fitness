"""Make a new ingest token for the iOS Shortcut (docs/AUTH_SPEC.md sections 4 and 7).

Usage: python3 scripts/make_ingest_token.py

Prints the token once, with its SHA-256. The token goes into the Shortcut; only the hash
goes into the server's environment (INGEST_TOKEN_SHA256). Nothing is written to disk.
Standard library only, so it runs with the Mac's own python3.
"""

import hashlib
import secrets

PREFIX = "ing_"


def make_token() -> str:
    # 32 random bytes = 256 bits; token_urlsafe gives 43 URL-safe characters.
    return PREFIX + secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def main() -> None:
    token = make_token()
    print("Shortcut header (shown once; it is not saved anywhere):")
    print(f"  Authorization: Bearer {token}")
    print()
    print("Server environment (.env, or the host's secret store):")
    print(f"  INGEST_TOKEN_SHA256={token_hash(token)}")
    print()
    print("Rotating? Put the new hash in INGEST_TOKEN_SHA256_NEXT, update the Shortcut,")
    print("then move it to INGEST_TOKEN_SHA256 and remove the old one.")


if __name__ == "__main__":
    main()

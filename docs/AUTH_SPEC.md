# Auth Spec: Google sign-in for the web app, scoped token for the Shortcut

Supersedes the "API key" parts of `ARCHITECTURE.md` section 12 and the web key gate in `UI_SPEC.md` section 1. When this task is done, update those sections to point here.

**Status (2026-11-04):** built (Slice 8a, steps 1-9). Where the build departs from this text, the reason is in `docs/DECISIONS.md`: the Origin check covers cookie routes, not the Shortcut's (D109); the route test is black-box (D110); `GET /auth/method` is an extra public route (D112); rate limits cover the sign-in pages, not every `/auth/*` route (D113); the database role moves to Slice 8 (D115).

**Design goal:** defense in depth. No single mistake (a leaked log, a committed file, a stolen cookie, a misconfigured flag) should expose the data or a credential. "No chance of a leak" is not achievable by any app, so every control below assumes one other control has already failed.

## 0. Instructions for the agent

1. **Read first, then plan, then stop.** Read `CLAUDE.md`, this file, `ARCHITECTURE.md` section 12, and every place in the code that touches the old API key, secrets, the Shortcut script, or the web key gate. Reply with the plan and wait for approval (see the prompt that points here).
2. **Verify against official docs before using any library or protocol detail** (Authlib's Starlette client, Google's OpenID Connect discovery document and claims, Starlette/FastAPI cookie and middleware behavior, Uvicorn proxy-header options). Do not rely on memory. Report what you verified, with links. If the docs disagree with this spec, stop and tell Rob.
3. **Do not hand-write cryptography or JWT verification.** Use the vetted library for the OIDC flow and token validation. Add the dependency with a one-line reason in `docs/DECISIONS.md`.
4. **Simple, readable code Rob can explain line by line.** Small functions, one FastAPI dependency per credential type, no clever abstractions. After each step give 3 to 5 interview-note bullets (what, why, trade-off).
5. **Step order** (run `make check` after each; CI must stay green): (1) config, secrets handling and startup guards; (2) ingest token; (3) sessions table and cookie; (4) CSRF/Origin check and route protection; (5) Google OIDC endpoints; (6) front end; (7) hardening (headers, docs off, rate limits, log redaction); (8) leak-prevention tests and CI; (9) docs.
6. **Git:** do not run git write commands. Tell Rob the branch name to create and suggest commit messages at each checkpoint.
7. **Never print, log, commit, or echo a secret value**, including in test output, error messages, and your own replies. Use obviously fake canary values in tests.

## 1. Scope

**In scope:** Google sign-in (OIDC) for the web app with exactly one allowed Google account; server-side sessions; CSRF protection; a separate scoped ingest token for the iOS Shortcut; removal of the old API key from production code paths; startup guards; hardening; leak-prevention tests.

**Out of scope for this task (do not build):** the public demo deployment, multiple users, a users table, roles, passwords, email, password reset, Google API calls on the user's behalf, refresh tokens, the Scriptable `GET /streak` token (it will get its own read-only token later), WebAuthn/passkeys in the app itself.

## 2. Threat model

| Threat | Control |
|---|---|
| Secret committed to git or baked into a Docker image | `.gitignore` and `.dockerignore`, secret scanning in CI, placeholders only in `.env.example` |
| Secret exposed in the front-end bundle | No secrets in `web/`; CI greps the built bundle for canary values |
| Secret exposed in logs or error pages | `SecretStr` everywhere, a log redaction filter, access-log query stripping, no stack traces in production |
| Any Google user signing in | Server-side allowlist on the stable `sub` claim, not email, plus Google test-user restriction |
| Login CSRF / forged callback | `state`, `nonce` and PKCE, all validated |
| Open redirect after login | Only relative paths accepted |
| Cookie theft by script (XSS) | HttpOnly cookie, strict CSP, no tokens in `localStorage` or `sessionStorage` |
| Cookie theft from a database leak | Database stores only a SHA-256 hash of the session id |
| CSRF on state-changing requests | SameSite=Lax cookie plus exact `Origin` check on every non-GET request, no CORS |
| Replay or guessing of the ingest token | 256-bit random token, only its SHA-256 hash stored on the server, constant-time compare, HTTPS only in production, rate limiting, rotation supported |
| A leaked ingest token reading data | The token is accepted on one route only |
| Misconfigured production (debug on, key mode, HTTP) | Startup guards refuse to boot |
| Host header or proxy header spoofing | Redirect URI and origin come from `PUBLIC_BASE_URL`, never from the request; proxy headers trusted only from the configured proxy |

**Residual risks (state them in the README):** compromise of the allowed Google account (mitigated by Rob enabling a passkey or 2-step verification), compromise of the host or its secret store, and someone using Rob's unlocked phone, where the Shortcut's token is readable.

## 3. Credential inventory

| Credential | Purpose | Where it lives | Notes |
|---|---|---|---|
| Google client ID | identifies the app to Google | env `GOOGLE_CLIENT_ID` | not secret, but keep out of the front-end bundle anyway |
| Google client secret | server-to-Google code exchange | env `GOOGLE_CLIENT_SECRET` (`SecretStr`), host secret store in production | never in git, image, bundle or logs |
| OAuth state secret | signs the short-lived login-state cookie | env `OAUTH_STATE_SECRET` (`SecretStr`, at least 32 bytes) | rotating it only invalidates logins in progress |
| Allowed Google `sub` | the one authorized account | env `ALLOWED_GOOGLE_SUB` | an identifier, not a secret, but treat it as config |
| Session id | proves a signed-in browser | cookie holds a random 256-bit id; the database stores only its SHA-256 | |
| Ingest token | lets the Shortcut POST health data | plaintext only on Rob's phone; env `INGEST_TOKEN_SHA256` holds the hash | format `ing_` plus 32 random bytes, url-safe |
| Dev login key | local development only | env `DEV_LOGIN_KEY` (replaces the old `API_KEY`) | refused in production |
| Google's access and ID tokens | one-time identity proof | **never stored** | verified once, then discarded; no refresh tokens, no `offline` access |

## 4. Environment variables and startup guards

New or renamed: `APP_ENV` (`dev`, `test`, `production`), `AUTH_MODE` (`google`, `key`), `PUBLIC_BASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_STATE_SECRET`, `ALLOWED_GOOGLE_SUB`, `INGEST_TOKEN_SHA256`, optional `INGEST_TOKEN_SHA256_NEXT` (accepted during rotation), `DEV_LOGIN_KEY`. Config constants in `src/config`: `SESSION_ABSOLUTE_DAYS = 60`, `SESSION_IDLE_DAYS = 30`, `LOGIN_STATE_MINUTES = 10`.

Update `.env.example` with placeholders only (`change-me`), and a comment on how to generate each value.

**Fail-fast guards** (app refuses to start; the error names the variable, never its value). In `production`: `AUTH_MODE` must be `google`; `PUBLIC_BASE_URL` must be `https://`; Google client ID and secret, `ALLOWED_GOOGLE_SUB`, `OAUTH_STATE_SECRET` and `INGEST_TOKEN_SHA256` must be set; `OAUTH_STATE_SECRET` must be at least 32 bytes and not a placeholder; `INGEST_TOKEN_SHA256` must be 64 hex characters; `DEV_LOGIN_KEY` must be unset; the cookie `Secure` flag must be on. `AUTH_MODE=key` is allowed only when `APP_ENV=dev`.

All secrets are Pydantic `SecretStr` (or equivalent) so an accidental `print` or log shows asterisks.

`scripts/make_ingest_token.py`: generates `ing_` + `secrets.token_urlsafe(32)`, prints the plaintext **once** with the matching SHA-256 hex, and tells Rob to put the plaintext in the Shortcut and the hash in the environment. It writes nothing to disk.

## 5. Web sign-in flow (Google OpenID Connect)

Endpoints on the API, served at the same origin as the front end (the Vite dev server proxies `/auth` and `/api` to the API):

- `GET /auth/login` starts the flow: builds the authorization request with scopes **`openid email`** only (request nothing else), a random `state`, a random `nonce`, and PKCE (`S256`). The redirect URI is `PUBLIC_BASE_URL + /auth/callback`, taken from config, never from the `Host` header. An optional `next` value is accepted only if it is a relative path starting with a single `/`; otherwise it is ignored.
- `GET /auth/callback`: validates `state`; exchanges the code (with the PKCE verifier) server-side; validates the ID token through the library (signature against Google's keys, `iss`, `aud` equals our client ID, `exp`, `nonce`). Then it compares the `sub` claim with `ALLOWED_GOOGLE_SUB` using a constant-time compare.
  - Match: create a new session (section 6), clear the login-state cookie, redirect to the `next` path or `/`. Google's tokens are discarded and not stored, cached, or logged.
  - No match or any validation error: 403 with a generic page ("This account isn't authorized"), no detail about why. Log a WARNING with the event name and the `sub` value only (not the email, not any token), so Rob can find his own `sub` on the first attempt.
- `POST /auth/logout`: Origin-checked; deletes the session row, clears the cookie, returns 204.
- `GET /auth/me`: returns `{"signed_in": true}` or 401. No email, no name, nothing from Google.
- `POST /auth/dev-login` exists **only** when `AUTH_MODE=key` and `APP_ENV=dev`. It takes `{key}`, compares in constant time with `DEV_LOGIN_KEY`, rate-limited, and creates a normal session. The key never lives in browser storage. In any other mode this route must not be registered (test it).
- Do not store the email address anywhere. Do not request or store the profile.
- Login-state cookie (state, nonce, PKCE verifier) is short-lived (`LOGIN_STATE_MINUTES`), HttpOnly, SameSite=Lax, signed with `OAUTH_STATE_SECRET`, and deleted after the callback.

## 6. Sessions, cookies, CSRF

- Table `app.session(session_hash text primary key, sub text not null, created_at timestamptz not null, last_seen_at timestamptz not null, expires_at timestamptz not null)` through an Alembic migration. Index on `expires_at`. Delete expired rows during login.
- On sign-in create a **new** random session id with `secrets.token_urlsafe(32)` (never reuse an id: prevents fixation). Store only `sha256(id)`. A request is valid when the row exists, `expires_at` has not passed (`SESSION_ABSOLUTE_DAYS`), and `last_seen_at` is within `SESSION_IDLE_DAYS`. Update `last_seen_at` at most once per hour.
- Cookie name `__Host-session` in production (requires `Secure`, `Path=/`, no `Domain`), plain `session` when `APP_ENV=dev` (plain HTTP on the LAN). Flags: `HttpOnly`, `Secure` (always in production), `SameSite=Lax`, `Max-Age` matching the absolute lifetime.
- **CSRF:** every non-GET/HEAD/OPTIONS request must carry an `Origin` header exactly equal to the origin of `PUBLIC_BASE_URL`; missing or different means 403. Mutating endpoints accept only `application/json`. No CORS middleware at all (same origin), and never `Access-Control-Allow-Credentials` with a wildcard.
- `Cache-Control: no-store` on `/auth/*` and every authenticated API response.

## 7. Ingest token (iOS Shortcut)

- Header: `Authorization: Bearer ing_...`. Never accepted in a query string, a cookie or a body field.
- The server stores **only** the SHA-256 hex of the token (`INGEST_TOKEN_SHA256`). Compute the hash of the presented token and compare with `hmac.compare_digest`. Also accept `INGEST_TOKEN_SHA256_NEXT` when set, so Rob can rotate with zero downtime (add the new hash, update the Shortcut, remove the old hash).
- Valid **only** on `POST /api/v1/ingest/health`. Any other route presented with this token returns 401, and the ingest route presented with a session cookie also returns 401.
- Failure response is identical for missing, malformed, wrong or expired credentials: 401 `{"error":{"code":"unauthorized"}}`. Log the event (client IP, route), never the token.
- Keep the existing request-body limit. In production the ingest route is HTTPS only (the HTTP-to-HTTPS redirect and HSTS handle this). On the local LAN over HTTP it works but logs a startup warning that it is unencrypted.
- Update `scripts/send_sample_shortcut_payload.sh` and its docs to use the bearer token from an environment variable, never as a literal in a file.

## 8. Route protection model

- One FastAPI dependency `require_user` (valid session) and one `require_ingest_token`. Every `/api/v1/*` route except `GET /api/v1/health` uses exactly one of them. `/auth/login`, `/auth/callback`, `/auth/logout` and `/auth/me` are the only other routes.
- **Route-coverage test:** enumerate every registered route and assert it is either on an explicit public allowlist (`/api/v1/health`, `/auth/login`, `/auth/callback`) or has one of the two dependencies. Adding an unprotected route must fail CI.
- The old `X-API-Key` header is not accepted anywhere when `AUTH_MODE=google`. Remove the old API-key dependency and its tests; do not leave it behind a flag in production code paths. There is **no backdoor and no break-glass key**: recovery is changing `ALLOWED_GOOGLE_SUB` in the host's environment and redeploying.

## 9. Front end

- Remove the API-key prompt and every read or write of the key in `localStorage`/`sessionStorage`. On app load, delete the old key's storage entry (`localStorage.removeItem`) so a leaked old key does not linger on Rob's devices.
- On a 401 from the API or `/auth/me`, show a sign-in screen with one **"Sign in with Google"** button that is a plain link to `/auth/login` (a full-page navigation; no Google script is loaded in the page, which keeps the CSP tight). In `dev` with `AUTH_MODE=key`, show the dev key form instead, posting to `/auth/dev-login`.
- All requests use `credentials: 'same-origin'`. No tokens, secrets, or email in JavaScript variables, URLs, or logs. The page never reads the cookie.
- Me page gets a **Sign out** button (calls `POST /auth/logout`, then shows the sign-in screen). Show "Signed in" only, with no email.
- No third-party scripts, fonts or analytics.

## 10. Hardening

- **Headers** on API responses (and documented for whatever serves the static files in Slice 8): `Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'` (tighten or fix violations using the screenshot loop; do not loosen to `unsafe-inline` or `unsafe-eval` without telling Rob), `Strict-Transport-Security: max-age=31536000` (production only), `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Permissions-Policy` with everything disabled, `Cross-Origin-Opener-Policy: same-origin`.
- **Production hygiene:** debug off, no stack traces in responses, FastAPI `/docs`, `/redoc` and `/openapi.json` disabled when `APP_ENV=production`, generic 500 body.
- **Rate limits** (simple, in-process, keyed by client IP): `/auth/*` 10 per minute; ingest 60 per minute; dev-login 5 per minute. Explain the choice in `DECISIONS.md` (single instance, so in-process is enough).
- **Proxy headers:** run Uvicorn with proxy headers trusted only from the configured proxy address, never `*`. Take the client IP and scheme only from those.
- **Logging:** a redaction filter removes values for `Authorization`, `Cookie`, `Set-Cookie`, `client_secret`, `code`, `state`, `id_token`, `access_token`, `refresh_token`, and anything starting with `ing_`. The access log must **strip the query string** for `/auth/callback` (the OAuth `code` and `state` are in it).
- **Docker:** add `.dockerignore` with `.env*`, `.git`, `docs/samples`, `spike_out/`. No `COPY .env` anywhere. Secrets are passed at runtime through environment variables, never build arguments.
- **Database role:** note in DECISIONS that the API should connect as a role without DDL rights in production (migrations use a separate role). Implement only if it takes under an hour; otherwise log it as a Slice 8 task.

## 11. Leak-prevention tests and CI

- **Bundle test:** build the front end with canary values for every secret env var, then grep `web/dist` for every canary and for `GOOGLE_CLIENT_SECRET`-like patterns. Any hit fails CI.
- **Log test:** run the full sign-in, denied sign-in, failed ingest, and dev-login flows with canary secrets and capture all log output and responses. Assert no canary, no `ing_` token, no session id, no OAuth `code` or `state` appears.
- **Repository scan:** add secret scanning (gitleaks or an equivalent) to CI over the full history and the working tree, plus a `.pre-commit-config.yaml` entry for Rob to install. Add a custom rule for the `ing_` prefix.
- **Startup-guard tests:** one test per guard in section 4.
- **Route-coverage test** from section 8.

## 12. Test matrix (mock Google; no real network in CI)

Build a fake OIDC provider for tests: a test key pair, a stubbed discovery document and token endpoint.

| Case | Expected |
|---|---|
| Valid code, correct `sub` | session created, cookie set with all flags, redirect to `/` |
| Valid ID token, different `sub` | 403 generic, no session, `sub` logged |
| Wrong `aud`, wrong `iss`, expired, wrong `nonce` | 403, no session |
| Tampered or missing `state`, replayed callback | 403 |
| PKCE verifier mismatch | 403 |
| `next=https://evil.example` or `//evil.example` | ignored, redirect to `/` |
| Request with no cookie | 401 on every protected route |
| Expired or idle session, deleted session row | 401 |
| Session id presented that is not in the database (including a guessed hash) | 401 |
| POST with missing or wrong `Origin` | 403; correct `Origin` passes |
| Logout then reuse the old cookie | 401 |
| Ingest: valid token | 200 on `POST /ingest/health` only |
| Ingest token on any other route; session cookie on ingest; old `X-API-Key` anywhere | 401 |
| Ingest: rotation (`_NEXT` hash) | both tokens valid, removing one invalidates it |
| `/auth/dev-login` in production or with `AUTH_MODE=google` | route does not exist (404) |
| 11th login request in a minute from one IP | 429 |
| Response headers on API and auth responses | all section 10 headers present, `no-store` on authenticated responses |
| `/docs`, `/openapi.json` in production | 404 |

## 13. Rob's manual checklist (the agent cannot do these)

1. **Secure the Google account first.** Add a passkey or 2-step verification to the Google account you will allow. This account is the root of trust.
2. **Google Cloud Console:** create a project; configure the OAuth consent screen as **External**, publishing status **Testing**, and add only yourself as a test user; scopes `openid` and `email` only. Create an OAuth client of type **Web application**. Authorized redirect URIs: `http://localhost:5173/auth/callback` now (open the app via `localhost`, not the LAN IP, for Google sign-in testing), and the production `https://<your-domain>/auth/callback` once the host is chosen. Leave "Authorized JavaScript origins" empty. Do not download the client JSON into the repo; copy the two values into `.env`.
3. **Generate secrets:** run `scripts/make_ingest_token.py`; put the plaintext in the Shortcut's `Authorization` header (`Bearer ing_...`) and the hash in `.env`. Generate `OAUTH_STATE_SECRET` with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. **Find your `sub`:** sign in once; it will be denied and the API log prints your `sub`. Put it in `ALLOWED_GOOGLE_SUB`, restart, and sign in again.
5. **Burn the old API key:** treat it as compromised. Remove it from `.env`, the Shortcut, your password manager and notes, shell history, any chat or message where you pasted it. Run the repository scan over the history; if the key or any other secret ever appears, rotate it.
6. **Production:** set variables in the host's secret store (not in the repo or image), `APP_ENV=production`, `AUTH_MODE=google`, and the production redirect URI in Google Console. Confirm the startup guards pass. Test sign-in from your phone and from a second Google account (it must be denied).
7. **Calendar a rotation:** rotate the ingest token and the Google client secret on a schedule you will keep (for example every 6 months), and immediately after any suspected exposure.

## 14. Docs to update in the same change

`ARCHITECTURE.md` section 12 (point here, remove the API-key language), `UI_SPEC.md` section 1 (sign-in screen replaces the key gate), `PROJECT_PLAN.md` (Slice 8 auth tasks), `docs/DECISIONS.md` (library choice, server-side sessions over signed cookies, hashed ingest token, no break-glass key, in-process rate limiting), `README.md` ("Authentication and security" section with the residual risks from section 2), `.env.example`, `.gitignore`, `.dockerignore`.

## 15. Definition of done

Every item in sections 11 and 12 passes in CI; the guards refuse a bad production config; Rob has completed his checklist and signed in with Google at `http://localhost:5173` on the Mac (the mocked-OIDC tests are the rest of the proof; signing in on the iPhone moves to Slice 8, once there is an HTTPS URL, because Google refuses IP-address redirect URIs); a second Google account is denied; the Shortcut posts with the new token; the old key no longer works anywhere.

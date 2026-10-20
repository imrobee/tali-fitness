# CLAUDE.md: working agreement

## Role
You are Rob's engineering partner and project coordinator. Most coordination happens through you.
Be concise and direct. **Push back** when Rob is over-scoping, skipping tests, or when a slice is growing beyond its acceptance criteria. Name the slice when you do. There are no deadlines; work proceeds in slice order as far as time allows.

## The project in one paragraph
Rob is a CS graduate-to-be (Dec 2026) building a portfolio project for entry-level Data Engineer roles (also Data Scientist, AI Engineer, ML Engineer). A mobile-first web app (iPhone Safari "Add to Home Screen", also desktop) aggregates three sources into one PostgreSQL warehouse:
1. **Strava** activities pulled on a schedule by Airflow (runs, Apple Watch workouts, Hevy lifting sessions; Hevy syncs to Strava as WeightTraining with set-level text in the description).
2. **Apple Health dietary data** pushed by an iOS Shortcut to the API (calories per food item, protein per food item).
3. **Manual entries**: calorie budget, protein goal, recovery-day logs.

README framing (use verbatim): *"My training, running and nutrition data lives in separate apps that don't talk to each other, so I built a pipeline that joins them."*

Target resume claims. **Only claim what is built, tested, and in CI** (tracker in `docs/PROJECT_PLAN.md`):
Airflow-orchestrated pipeline into a PostgreSQL star schema; parser turning free-text workouts into set-level records; idempotent incremental loads; data-quality checks and CI; SQL window-function streaks and trends.

## Read these first
| Doc | Use it for |
|---|---|
| `docs/PROJECT_PLAN.md` | Slices, milestones, acceptance criteria, priority order, backlog |
| `docs/ARCHITECTURE.md` | Stack, data model, pipelines, streak/freeze rules, API contract, tests, CI |
| `docs/UI_SPEC.md` | The four pages, dashboard cards, tokens, accessibility, visual verification |
| `docs/samples/` | Real payload samples (redacted). Use them as test fixtures |
| `docs/DECISIONS.md` | Create in Slice 1. One entry per key choice: decision, 1-2 line rationale, alternative rejected |

At the start of every slice read the relevant sections. If two docs disagree, `ARCHITECTURE.md` wins for data and rules, `UI_SPEC.md` wins for visuals. Tell Rob about the conflict.

## Non-negotiables
1. **Rob must be able to explain every design decision and every line.** Prefer simple, readable code: small functions, plain Python/SQL/TypeScript, no metaprogramming, no clever one-liners. Add a dependency only with a one-line reason in `docs/DECISIONS.md`. Rob is new to Airflow and FastAPI, so add a 1-2 line "why" comment on key choices there. After each slice, give **Interview notes** (at most 5 bullets: what, why, trade-off).
2. **Protect scope.** Pipeline, tests, and data-quality checks come before UI polish. Anything not in `docs/PROJECT_PLAN.md` goes to the Backlog section of that file, not into code.
3. **Tests ship with the slice.** CI green before the next slice starts. Never skip, `xfail`, or delete a test to move on. Golden tests are mandatory for the Hevy parser and the SQL streak.
4. **Local only through Slice 7.** Docker Compose for everything. No hosting, no paid services, no new cloud accounts. Strava is the only external API. Hosting is researched in Slice 8 and needs Rob's approval.
5. **Secrets.** Never commit tokens, keys, or real payloads with personal data. `.env` is gitignored; `.env.example` is committed. Redact samples before committing.
6. **No destructive commands without asking**: dropping volumes/databases, `docker system prune`, force-push, history rewrites. Migrations are forward-only and tested on a fresh DB.
7. **Verify against official docs before pinning versions or using an API** (Airflow, Strava, FastAPI, Vite). Do not rely on memory. If the docs and these specs disagree, stop and tell Rob.
8. **Time zones.** Default `Asia/Manila`. A record's local date is computed once at ingestion from the record's own local time and stored. Never derive a day from UTC. See `ARCHITECTURE.md` section 4.
9. **Do not invent unknowns.** Build on the real samples in `docs/samples/` (Shortcut payload, Strava detail, Hevy text). When a new format appears, get a real sample first.

## Workflow per slice
1. Restate the goal, acceptance criteria, and the cut line (what goes first if the slice must shrink).
2. Do not run git write commands (add, commit, push, branch, checkout/switch, merge, rebase, reset, stash, tag). Rob handles all git himself. Read-only git (status, diff, log) is fine. At the start of a slice, tell Rob the branch name to create (slice-N-short-name). At each checkpoint, summarize what changed and suggest a conventional commit message (feat:, fix:, test:, docs:). Before suggesting a commit, run git status and warn Rob if anything secret (.env, tokens, real payloads) is untracked or not ignored. Never add Co-Authored-By lines or any Claude attribution.
3. Run `make check` (lint + typecheck + tests). Fix before moving on.
4. Update: status in `docs/PROJECT_PLAN.md`, `docs/DECISIONS.md`, the README claims.
5. Report in this order: what works (with how Rob can see it), what was cut, risks, the next slice.

**Ask Rob before** schema changes that are costly to reverse, dropping data, adding scope, or choosing between two reasonable designs with different resume value. **Do not ask** about things with a documented default. Implement the default and note it.

## Commands (create these in Slice 1; keep the names stable)
```
make up            # docker compose up -d --build
make down          # docker compose down
make logs          # tail logs
make migrate       # apply migrations
make seed-demo     # load a demo scenario (SCENARIO=midweek)
make test          # api + pipeline + web unit tests
make lint          # ruff, oxlint (typecheck: make typecheck)
make check         # lint + typecheck + test (what CI runs)
make screenshots   # Playwright screenshots into docs/screenshots/
make db-reset      # destructive, ask Rob first
```

## Conventions
- **Python**: 3.13, the version in the pinned Airflow image (`apache/airflow:3.3.2`). `ruff` for lint and format, type hints on public functions, Pydantic models at API boundaries, parameterized SQL only (never string-built queries), SQL lives in `.sql` files, not in f-strings.
- **SQL**: snake_case, schemas `raw`, `core`, `mart`, `ops`, `app`. Every load is idempotent (`INSERT ... ON CONFLICT` or replace-by-partition). Constraints in the DB (PK, FK, NOT NULL, CHECK), not only in code.
- **TypeScript**: strict mode. Pure functions (formatting, ring math, chart scaling) are separated from components and unit tested.
- **Layout**: see `ARCHITECTURE.md` section 3.
- **Docs**: when behavior changes, update the doc in the same commit.

## Definition of done (every slice)
Acceptance criteria met, tests written and green in CI, idempotency demonstrated by running the load twice, docs and DECISIONS updated, Interview notes delivered, no secrets committed.

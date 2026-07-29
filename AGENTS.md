# FlyRank Backend AI — Agent Guide

## Entrypoints

| What | Command |
|------|---------|
| API server | `uvicorn app.main:app --reload --port 8000` |
| RQ worker (watches `ai-jobs`, `report-jobs`, `enrichment-jobs`) | `python -m app.core.worker` |
| Docker stack | `docker compose up --build` |
| Full test suite (excludes E2E) | `pytest` or the verbatim CI command below |

## CI pipeline (`.github/workflows/ci.yml` — source of truth)

Runs on `main` push/PR. Order: **isort → black → ruff → pytest**.

```yaml
# lint
isort --check-only --diff .
black --check --diff .
ruff check .

# test (exact CI path — use this to match CI)
python -m pytest \
  tests/embed/ \
  tests/leads/ \
  tests/widgets/ \
  tests/middleware/ \
  tests/models/ \
  tests/repositories/ \
  tests/routers/ \
  tests/services/ \
  tests/test_main.py \
  tests/test_background_jobs.py \
  tests/test_db_schema.py \
  tests/test_e2e_widget.py \
  tests/test_lead_worker.py \
  tests/test_report_worker.py \
  tests/test_worker.py \
  --ignore=tests/test_e2e.py \
  --ignore=tests/test_ai_e2e.py \
  --cov=app --cov-report=term-missing --tb=short -v
```

Single-file: `pytest tests/routers/test_ai.py -v` (works for any test path).

## Architecture

- **FastAPI** with `lifespan` pattern. Routers: `tasks`, `auth`, `scrape`, `ai`, `reports`, `widgets`, `embed`, `leads`.
- **3 RQ queues**: `ai-jobs`, `report-jobs`, `enrichment-jobs` — enqueued via `app.core.queue`. Worker runs all three.
- **Job state**: Redis hash `job:{id}` / `report_job:{id}` / `enrichment_job:{id}` — status lifecycle: `queued → started → finished/failed`.
- **Retry**: exponential backoff 10s → 60s → 300s, max 3, job timeout 600s.
- **Idempotency**: `Idempotency-Key` header → Redis `idempotency:{key}` with 24h TTL.
- **Database**: SQLite by default (no `DATABASE_URL` set). PostgreSQL via asyncpg when `DATABASE_URL` is provided. Postgres required for `scraped_books`, `widgets`, `leads`, `reports` tables (see `db/init.sql`).
- **Auth**: Supabase JWT. Require `SUPABASE_URL` + `SUPABASE_KEY` in `.env` — app refuses to start without them.
- **Middleware**: `BodyLimitMiddleware` (50KB), CORS (all origins, GET/POST/OPTIONS only).

## Testing quirks

- `conftest.py` sets `DATABASE_URL=""` and `REDIS_URL=""`, patches all `is_postgres_enabled` calls to `False`, and installs `_FakeRedis` + `_FakeQueue`. Tests are fully offline.
- `pyproject.toml`: `asyncio_mode = "auto"`.
- E2E tests (`test_e2e.py`, `test_ai_e2e.py`) are **always excluded from CI** — need real Supabase/Redis/server.

## Framework quirks

- **Ruff**: per-file ignores for `B008` in `app/routers/auth.py`, `app/dependencies/auth.py`, `app/routers/reports.py`.
- **isort**: profile `black`.
- **Python 3.13** in CI (Docker is `python:3.13-slim`); `requires-python = ">=3.10"`.
- **Worker uses `SimpleWorker`** on Windows (`os.name == "nt"`), regular `Worker` on Linux.
- **Docker Redis**: mapped to host port **6380** (not 6379). Postgres on 5432.
- **Groq mock**: when `GROQ_API_KEY` is unset, `call_ai` returns `"Mock response to: {prompt}"`.

## Pre-commit guardrail

This project has a history of unintended file bundling in fix commits (commits `2715feb` and `39e94a0` both swept up unrelated files via `git add -A`). **Before every commit**, run:

```bash
git status
git diff --cached --stat
```

Visually confirm that only intended files are staged. If binary docs, PDFs, or unrelated source files appear, unstage them with `git reset HEAD -- <path>` before committing.

## ⚠️ .env contains real credentials

`.env` has live `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, and `GROQ_API_KEY`. **Do not commit `.env` or expose these values.**

## Health endpoint

- **`GET /health`** — Returns `{"status": "ok"}` with optional `redis` and `postgres` connectivity fields. Add `?` to any app for liveness/readiness checks. Docker Compose `app` service includes a HEALTHCHECK stanza (same pattern as `db`/`redis`). Dockerfile has `HEALTHCHECK` instruction.

## Open Tier C items (needs Ahmed's sign-off)

- **`POST /widgets` status code** — Plan (`docs/implementation-plan.md` §4.2 line 383) says `400` for validation errors but code returns `422` (FastAPI default). Two options: update the plan to `422`, or add a `RequestValidationError` handler returning `400`. See `docs/reviews/m1-architecture.md` Tier C table for full entry.

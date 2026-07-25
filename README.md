# FlyRank Backend AI

A FastAPI backend with task management, book scraping, Supabase authentication, and asynchronous AI job processing via RQ and Groq.

## Features

- **Task CRUD** with SQLite/PostgreSQL persistence, search/filter, and statistics
- **Supabase Auth** — signup, login, logout, and protected endpoints
- **Book Scraper** — polite scraping of `books.toscrape.com` with robots.txt compliance
- **AI Background Jobs** — async LLM inference via RQ (Redis Queue) and Groq
- **Docker Compose** stack with PostgreSQL, Redis, and the app
- **Comprehensive testing** — unit, integration, and end-to-end

## Technologies Used

| Component       | Technology                        |
|-----------------|-----------------------------------|
| API             | FastAPI + Uvicorn                 |
| Database        | SQLite (dev) / PostgreSQL 16      |
| DB Driver       | asyncpg / sqlite3 (stdlib)        |
| Cache / Queue   | Redis 7 + RQ                      |
| LLM Client      | Groq SDK (llama3-8b-8192)         |
| Auth            | Supabase Auth                     |
| Scraping        | requests + BeautifulSoup4 + lxml  |
| Container       | Docker + Docker Compose           |
| Config          | python-dotenv                     |

## Requirements

- Python 3.10+
- pip
- Docker (optional, for PostgreSQL/Redis)
- Supabase project (for auth)
- Groq API key (optional, for AI jobs)

## Installation

```bash
pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env`:

```
DATABASE_URL=postgresql://user:password@host:5432/dbname
REDIS_URL=redis://host:6379/0
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_role_key
GROQ_API_KEY=your_groq_api_key
PORT=8000
```

| Variable                | Required | Purpose                              |
|-------------------------|----------|--------------------------------------|
| `DATABASE_URL`          | No       | PostgreSQL connection (omit for SQLite) |
| `REDIS_URL`             | No       | Redis connection for caching + RQ    |
| `SUPABASE_URL`          | Yes      | Supabase project URL                 |
| `SUPABASE_KEY`          | Yes      | Supabase anon/public key             |
| `SUPABASE_SERVICE_KEY`  | No       | Only needed for e2e tests            |
| `GROQ_API_KEY`          | No       | Groq API key (mock fallback if unset)|
| `PORT`                  | No       | Server port (default 8000)           |

## Running Locally (SQLite)

```bash
uvicorn app.main:app --reload --port 8000
```

App at `http://localhost:8000`, Swagger at `http://localhost:8000/docs`.

## Running with Docker (PostgreSQL + Redis)

```bash
docker compose up --build
```

## Running the RQ Worker

For AI background jobs, start the worker in a separate terminal:

```bash
rq worker ai-jobs --url redis://localhost:6379/0
```

Or use the convenience script:

```bash
.\run_e2e.ps1
```

## API Endpoints

### System

| Method | Path            | Auth | Description                   |
|--------|-----------------|------|-------------------------------|
| GET    | `/`             | No   | API info + Redis status       |
| GET    | `/health`       | No   | Health check + Redis status   |
| GET    | `/public/info`  | No   | Public welcome message        |

### Tasks

| Method | Path           | Auth | Description                    |
|--------|----------------|------|--------------------------------|
| GET    | `/tasks`       | No   | List tasks (`?search=&done=`)  |
| GET    | `/tasks/{id}`  | No   | Get a task by ID               |
| POST   | `/tasks`       | No   | Create a task                  |
| PUT    | `/tasks/{id}`  | No   | Update a task                  |
| DELETE | `/tasks/{id}`  | No   | Delete a task                  |
| GET    | `/stats`       | No   | Task statistics                |

### Auth

| Method | Path                    | Auth     | Description                    |
|--------|-------------------------|----------|--------------------------------|
| POST   | `/auth/signup`          | No       | Create a new account           |
| POST   | `/auth/login`           | No       | Sign in, returns tokens        |
| POST   | `/auth/logout`          | Bearer   | Sign out                       |
| GET    | `/protected/profile`    | Bearer   | Get user profile               |
| GET    | `/protected/dashboard`  | Bearer   | User dashboard                 |

### Scraper

| Method | Path          | Auth | Description                    |
|--------|---------------|------|--------------------------------|
| POST   | `/scrape`     | No   | Scrape books (`?max_pages=5`)  |

### AI / Background Jobs

| Method | Path              | Auth | Description                    |
|--------|-------------------|------|--------------------------------|
| POST   | `/ai`             | No   | Enqueue AI inference job       |
| GET    | `/jobs/{job_id}`  | No   | Poll job status                |

## Database

### SQLite (Default)

When `DATABASE_URL` is not set, the app uses SQLite via `sqlite3` (stdlib). The `tasks.db` file is created automatically at the project root with auto-seeded schema and 3 example tasks.

### PostgreSQL

When `DATABASE_URL` is set, the app connects via asyncpg with a connection pool (min 2, max 10) and automatic retry on startup. The `db/init.sql` creates both `tasks` and `scraped_books` tables with indexes.

## Authentication

Uses **Supabase Auth** — all credential and token operations go through the Supabase SDK. Protected routes use FastAPI's `HTTPBearer` scheme — click **Authorize** in Swagger UI and paste your Bearer token.

## Scraper Architecture

The scraper fetches book data from `http://books.toscrape.com/`:

| Component   | Role                                                |
|-------------|-----------------------------------------------------|
| Session     | HTTP session with retry, rate-limiting, robots.txt  |
| Parser      | BeautifulSoup parsing of listing + detail pages     |
| Cleaner     | Normalise prices, ratings, availability             |
| Pipeline    | Orchestrates page iteration, detail fetch, merge    |
| Repository  | PostgreSQL bulk_upsert via `ON CONFLICT`            |

Requires `DATABASE_URL` pointing to a running PostgreSQL instance.

## AI Background Jobs

AI inference runs asynchronously via RQ (Redis Queue). The worker is a separate process.

### Usage

```
POST /ai  { "prompt": "Tell me a joke", "model": "llama3-8b-8192" }
→ 202  { "job_id": "<uuid>", "status_url": "/jobs/<uuid>" }

GET /jobs/<uuid>
→ 200  { "status": "queued" | "processing" | "completed" | "failed" }
```

### Idempotency

Pass an `Idempotency-Key` header on `POST /ai` to prevent duplicate enqueues. If a job with the same key was created within 24h, the existing `job_id` is returned.

### Retries

Jobs retry up to 3 times with exponential backoff (10s, 60s, 300s). After exhaustion, status is `"failed"` with `attempts: 3` and the last error.

### Alerts

On permanent failure, `send_alert()` in `app/services/alert.py` logs at CRITICAL level — swap for a Slack/email/PagerDuty webhook in production.

## Architecture

### Project Structure

```
app/
    main.py                     # FastAPI app, lifespan, router mounting
    database.py                 # asyncpg connection pool
    supabase_client.py          # Supabase async client singleton
    dependencies/
        auth.py                 # Bearer token dependency
    models/
        task.py, auth.py, scraped_book.py
    services/
        task_service.py         # Task business logic
        scraped_book_service.py # Scrape orchestration
        ai_service.py           # Groq API call (with mock fallback)
        ai_worker.py            # RQ worker function
        alert.py                # Failure alert stub
    repositories/
        protocol.py             # TaskRepository Protocol
        sqlite_repo.py          # SQLite (default)
        postgres_repo.py        # PostgreSQL via asyncpg
        inmemory_repo.py        # In-memory fallback
        scraped_book_repo.py    # ScrapedBook PostgreSQL
    routers/
        tasks.py                # Task CRUD + stats
        auth.py                 # Auth endpoints
        scrape.py               # Scrape trigger
        ai.py                   # AI job enqueue + status
    scrapers/
        session.py, parser.py, cleaner.py, pipeline.py
db/
    init.sql                    # PostgreSQL DDL (tasks + scraped_books)
scripts/
    seed_explain.py             # EXPLAIN ANALYZE index benchmark
```

### Request Flow

```
Client → Routes → Services → Repositories → Database
                                    │
                              ┌─────┴─────┐
                              │  SQLite    │
                              │  Postgres  │
                              │  InMemory  │
                              └───────────┘

AI Jobs: Client → POST /ai → RQ (Redis) → Worker → Groq API
                                    │
                              GET /jobs/{id} ← status update
```

## Testing

```bash
# All unit tests (mocked Supabase, no network)
pytest

# Auth tests
pytest tests/routers/test_auth.py -v

# AI job tests
pytest tests/test_ai_unit.py -v

# E2E auth (requires real Supabase + running server)
pytest tests/test_e2e.py -v -s

# E2E AI (requires real Redis + RQ worker running)
pytest tests/test_ai_e2e.py -v -s
```

Test coverage: 22 test files covering models, routers, services, repositories, scrapers, and end-to-end flows.

## Example Requests

```bash
# Task CRUD
curl http://localhost:8000/tasks?search=fastapi
curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{"title":"Demo","done":false}'
curl http://localhost:8000/stats

# Auth
curl -X POST http://localhost:8000/auth/signup -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"pass123"}'
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"pass123"}'
curl http://localhost:8000/protected/profile -H "Authorization: Bearer <token>"

# Scrape (requires PostgreSQL)
curl -X POST "http://localhost:8000/scrape?max_pages=3"

# AI Job
curl -X POST http://localhost:8000/ai -H "Content-Type: application/json" -d '{"prompt":"Hello","model":"llama3-8b-8192"}'
```

## Known Limitations

- Scraped books require PostgreSQL (cannot use SQLite)
- AI jobs require Redis running with an RQ worker
- No email verification flow (for development, Supabase "Confirm email" should be disabled)
- Scraper runs synchronously in the request thread
- Rate limiting on Supabase free tier may affect auth e2e tests

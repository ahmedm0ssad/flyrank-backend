# FlyRank — AI Background Jobs

A FastAPI backend combining task management, web scraping, authentication, and asynchronous AI job processing via RQ (Redis Queue) and Groq LLM inference.

## Assignment Goal

Add an asynchronous background job system for AI inference using Redis Queue, with idempotent job creation, status polling, retry logic, and a dedicated RQ worker process.

## Features

- Asynchronous AI inference via RQ (Redis Queue) and Groq API
- Job lifecycle management (queued → started → finished/failed)
- Idempotent job creation via `Idempotency-Key` header
- Job status polling (`GET /jobs/{id}`) and listing (`GET /jobs`)
- Automatic retries with exponential backoff (up to 3 retries)
- Failure alert stub (CRITICAL log — replace with Slack/email/webhook)
- Mock AI response when `GROQ_API_KEY` is unset
- Full test suite with mocked Redis and RQ
- Task CRUD with SQLite/PostgreSQL persistence
- Supabase Authentication (signup, login, logout, protected endpoints)
- Book scraper with robots.txt compliance and rate limiting
- Docker Compose stack (PostgreSQL + Redis + App)
- CI pipeline with automated linting and testing via GitHub Actions

## Technologies Used

| Component       | Technology                        |
|-----------------|------------------------------------|
| Framework       | FastAPI                            |
| Server          | Uvicorn                           |
| Validation      | Pydantic                          |
| Authentication  | Supabase Auth                     |
| Database        | SQLite (default) / PostgreSQL 16  |
| DB Driver       | asyncpg / sqlite3 (stdlib)        |
| Cache / Queue   | Redis 7 + RQ                      |
| LLM Client      | Groq SDK (llama-3.1-8b-instant)   |
| Scraping        | requests + BeautifulSoup4 + lxml  |
| Container       | Docker + Docker Compose           |
| Linting         | Ruff, Black, isort                |
| CI              | GitHub Actions                    |
| Config          | python-dotenv                     |

## Requirements

- Python 3.10+
- pip
- Docker (optional — required for PostgreSQL/Redis)
- A Supabase project (for authentication)
- A Groq API key (optional — falls back to mock)

## Installation

```bash
pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```env
DATABASE_URL=postgresql://user:password@host:5432/dbname
REDIS_URL=redis://host:6379/0
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_role_key
GROQ_API_KEY=your_groq_api_key
PORT=8000
```

| Variable               | Required | Purpose                                  |
|------------------------|----------|------------------------------------------|
| `DATABASE_URL`         | No       | PostgreSQL connection string (omit to use SQLite) |
| `REDIS_URL`            | No       | Redis connection for caching and RQ       |
| `SUPABASE_URL`         | Yes      | Supabase project URL                      |
| `SUPABASE_KEY`         | Yes      | Supabase anon/public key                  |
| `SUPABASE_SERVICE_KEY` | No       | Required only for end-to-end tests        |
| `GROQ_API_KEY`         | No       | Groq API key (falls back to mock if unset) |
| `PORT`                 | No       | Server port (default: `8000`)             |

## Running Locally (SQLite)

```bash
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

## Running with Docker (PostgreSQL + Redis)

```bash
docker compose up --build
```

## Starting the AI Worker

Background jobs require a running Redis instance and a worker process:

```bash
# Terminal 1: start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2: start the worker
python -m app.worker

# Terminal 3: start the API
uvicorn app.main:app --port 8000
```

## API Endpoints

### System

| Method | Path           | Auth | Description                 |
|--------|----------------|------|-----------------------------|
| GET    | `/`            | No   | API info and Redis status   |
| GET    | `/health`      | No   | Health check and Redis status |
| GET    | `/public/info` | No   | Public welcome message       |

### Tasks

| Method | Path          | Auth | Description                    |
|--------|---------------|------|----------------------------------|
| GET    | `/tasks`      | No   | List tasks (`?search=&done=`)     |
| GET    | `/tasks/{id}` | No   | Get a task by ID                  |
| POST   | `/tasks`      | No   | Create a task                     |
| PUT    | `/tasks/{id}` | No   | Update a task                     |
| DELETE | `/tasks/{id}` | No   | Delete a task                     |
| GET    | `/stats`      | No   | Task statistics                   |

### Auth

| Method | Path                   | Auth   | Description             |
|--------|------------------------|--------|---------------------------|
| POST   | `/auth/signup`         | No     | Create a new account       |
| POST   | `/auth/login`          | No     | Sign in, returns tokens    |
| POST   | `/auth/logout`         | Bearer | Sign out                   |
| GET    | `/protected/profile`   | Bearer | Get user profile           |
| GET    | `/protected/dashboard` | Bearer | User dashboard              |

### Scraper

| Method | Path      | Auth | Description                   |
|--------|-----------|------|---------------------------------|
| POST   | `/scrape` | No   | Scrape books (`?max_pages=5`)    |

### AI / Background Jobs

| Method | Path             | Auth | Description               |
|--------|------------------|------|-----------------------------|
| POST   | `/ai`            | No   | Enqueue an AI inference job  |
| GET    | `/jobs/{job_id}` | No   | Poll job status               |
| GET    | `/jobs`          | No   | List recent jobs              |

## AI Background Jobs — Architecture

AI inference is processed asynchronously via RQ (Redis Queue), with a dedicated worker process consuming jobs from the `ai-jobs` queue.

### Queue Flow

1. Client sends `POST /ai` with a prompt and optional model
2. API validates the request, creates a job record in Redis with status `queued`
3. Job is enqueued to the `ai-jobs` RQ queue
4. API immediately returns `202 Accepted` with the `job_id`
5. Worker picks up the job, sets status to `started`
6. Worker calls the AI service (Groq API or mock)
7. On success: status set to `finished`, result stored
8. On failure: status set to `failed`, error stored; retries if attempts remain

### Retry Policy

| Attempt | Interval |
|---------|----------|
| 1st     | 10s      |
| 2nd     | 60s      |
| 3rd     | 300s (5m)|

Jobs time out after 600s (10 minutes). Job data is persisted in Redis with a 24h TTL.

### Idempotency

Include an `Idempotency-Key` header to prevent duplicate job creation. The key-to-job mapping is stored in Redis with a 24h TTL.

## Project Structure

```
app/
    main.py                     # FastAPI app, lifespan, router mounting
    database.py                 # asyncpg connection pool
    supabase_client.py          # Supabase async client singleton
    queue.py                    # Redis connection, RQ queue, job CRUD
    worker.py                   # Standalone RQ worker entry point
    dependencies/
        auth.py                 # Bearer token dependency
    models/
        task.py, auth.py, scraped_book.py, job.py
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
.github/
    workflows/
        ci.yml                  # GitHub Actions CI pipeline
```

## Testing

Run all unit tests (mocked Redis, no network required):

```bash
pytest
```

With coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

Run specific test suites:

```bash
# Router tests
pytest tests/routers/test_ai.py -v

# Worker tests
pytest tests/test_worker.py -v

# Background job tests (comprehensive)
pytest tests/test_background_jobs.py -v

# End-to-end auth (requires real Supabase + a running server)
pytest tests/test_e2e.py -v -s

# End-to-end AI (requires real Redis + a running RQ worker)
pytest tests/test_ai_e2e.py -v -s
```

### CI Pipeline

Every push and pull request to `main` triggers a GitHub Actions workflow that lints (isort, Black, Ruff) and tests the full suite. The pipeline is defined in `.github/workflows/ci.yml`.

## Example Requests

```bash
# Enqueue an AI job
curl -X POST http://localhost:8000/ai \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tell me a joke", "model": "llama3-8b-8192"}'

# Response: 202 Accepted
# {"job_id":"<uuid>","status":"queued"}

# Poll job status
curl http://localhost:8000/jobs/<uuid>

# List recent jobs
curl http://localhost:8000/jobs?limit=10&offset=0

# Enqueue with idempotency key
curl -X POST http://localhost:8000/ai \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-unique-key" \
  -d '{"prompt": "Hello"}'

# Task CRUD
curl http://localhost:8000/tasks?search=fastapi
curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d '{"title":"Demo","done":false}'
curl http://localhost:8000/stats

# Auth
curl -X POST http://localhost:8000/auth/signup -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"pass123"}'
curl -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"test@example.com","password":"pass123"}'

# Scrape (requires PostgreSQL)
curl -X POST "http://localhost:8000/scrape?max_pages=3"
```

## Known Limitations

- Scraped book persistence requires PostgreSQL — SQLite is not supported for this feature
- AI jobs require Redis with an active RQ worker
- No email verification flow (disable Supabase's "Confirm email" setting for local development)
- The scraper runs synchronously within the request thread
- Supabase free-tier rate limits may affect auth end-to-end tests
- Job listing uses Redis `SCAN` which may be slow with very large job sets

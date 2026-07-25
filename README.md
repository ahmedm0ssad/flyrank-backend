# FlyRank Backend AI

[![CI](https://github.com/ahmedm0ssad/flyrank-backend/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmedm0ssad/flyrank-backend/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.13-blue)](https://www.python.org/downloads/release/python-3130/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-059485?logo=fastapi)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

A FastAPI backend combining task management, web scraping, authentication, and asynchronous AI job processing in a single, production-oriented service.

Built with FastAPI, PostgreSQL/SQLite, Redis, Supabase Auth, and the Groq LLM API, the project demonstrates a clean layered architecture (routers → services → repositories) alongside a background job pipeline for LLM inference.

## Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Requirements](#requirements)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Database](#database)
- [Authentication](#authentication)
- [Scraper Architecture](#scraper-architecture)
- [AI Background Jobs](#ai-background-jobs)
- [Project Architecture](#project-architecture)
- [Testing](#testing)
- [Example Requests](#example-requests)
- [Known Limitations](#known-limitations)

## Features

- **Task CRUD** — SQLite/PostgreSQL persistence with search, filtering, and statistics
- **Supabase Authentication** — signup, login, logout, and protected endpoints
- **Book Scraper** — polite, robots.txt-compliant scraping of `books.toscrape.com`
- **AI Background Jobs** — asynchronous LLM inference via RQ (Redis Queue) and Groq
- **Docker Compose Stack** — PostgreSQL, Redis, and the application, orchestrated together
- **Comprehensive Test Suite** — unit, integration, and end-to-end coverage

## Technology Stack

| Component       | Technology                        |
|-----------------|------------------------------------|
| API             | FastAPI + Uvicorn                 |
| Database        | SQLite (dev) / PostgreSQL 16       |
| DB Driver       | asyncpg / sqlite3 (stdlib)         |
| Cache / Queue   | Redis 7 + RQ                       |
| LLM Client      | Groq SDK (llama3-8b-8192)          |
| Auth            | Supabase Auth                      |
| Scraping        | requests + BeautifulSoup4 + lxml   |
| Container       | Docker + Docker Compose            |
| Config          | python-dotenv                      |

## Requirements

- Python 3.10+
- pip
- Docker (optional — required for PostgreSQL/Redis)
- A Supabase project (for authentication)
- A Groq API key (optional — for AI jobs)

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in the required values (see [Environment Variables](#environment-variables)).

### 3. Run the application

**Locally with SQLite:**

```bash
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`, with interactive Swagger docs at `http://localhost:8000/docs`.

**With Docker (PostgreSQL + Redis):**

```bash
docker compose up --build
```

### 4. Start Redis

Background jobs require a running Redis instance:

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### 5. Start the AI worker

```bash
python -m app.worker
```

Or using the RQ CLI directly:

```bash
rq worker ai-jobs --url redis://localhost:6379/0
```

## Environment Variables

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
|------------------------|----------|-------------------------------------------|
| `DATABASE_URL`         | No       | PostgreSQL connection string (omit to use SQLite) |
| `REDIS_URL`            | No       | Redis connection for caching and RQ        |
| `SUPABASE_URL`         | Yes      | Supabase project URL                       |
| `SUPABASE_KEY`         | Yes      | Supabase anon/public key                   |
| `SUPABASE_SERVICE_KEY` | No       | Required only for end-to-end tests         |
| `GROQ_API_KEY`         | No       | Groq API key (falls back to a mock if unset) |
| `PORT`                 | No       | Server port (default: `8000`)              |

## API Reference

### System

| Method | Path           | Auth | Description                 |
|--------|----------------|------|------------------------------|
| GET    | `/`            | No   | API info and Redis status    |
| GET    | `/health`      | No   | Health check and Redis status |
| GET    | `/public/info` | No   | Public welcome message        |

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

## Database

### SQLite (Default)

When `DATABASE_URL` is not set, the app uses SQLite via the standard library `sqlite3` module. A `tasks.db` file is created automatically at the project root, with the schema auto-seeded and three example tasks.

### PostgreSQL

When `DATABASE_URL` is set, the app connects via `asyncpg` using a connection pool (min 2, max 10) with automatic retry on startup. `db/init.sql` defines both `tasks` and `scraped_books` tables with appropriate indexes.

## Authentication

Authentication is handled entirely through the **Supabase Auth** SDK — all credential and token operations are delegated to Supabase. Protected routes use FastAPI's `HTTPBearer` scheme; in Swagger UI, click **Authorize** and paste a valid Bearer token to access them.

## Scraper Architecture

The scraper retrieves book data from `http://books.toscrape.com/`:

| Component  | Role                                                  |
|------------|--------------------------------------------------------|
| Session    | HTTP session with retry logic, rate-limiting, and robots.txt compliance |
| Parser     | BeautifulSoup-based parsing of listing and detail pages |
| Cleaner    | Normalizes prices, ratings, and availability             |
| Pipeline   | Orchestrates page iteration, detail fetching, and merging |
| Repository | Bulk upsert into PostgreSQL via `ON CONFLICT`            |

> **Note:** The scraper requires `DATABASE_URL` to point to a running PostgreSQL instance.

## AI Background Jobs

AI inference is processed asynchronously via RQ (Redis Queue), with a dedicated worker process consuming jobs from the `ai-jobs` queue.

### Architecture Diagram

```
┌──────────┐     POST /ai     ┌──────────────┐     enqueue     ┌───────────┐
│          │ ──────────────── │              │ ────────────── │           │
│  Client  │                  │  FastAPI      │                │  Redis    │
│          │ ◀────────────── │  (app.main)   │ ◀───────────── │  (Queue)  │
└──────────┘   202 Accepted  └──────────────┘    job status   └─────┬─────┘
       │                                                             │
       │                    GET /jobs/{id}                           │
       │ ─────────────────────────────────────────────────────        │
       │ ◀────────────────────────────────────────────────────        │
       │                                                              │
                                                          ┌──────────▼──────────┐
                                                          │    RQ Worker         │
                                                          │  (app/worker.py)     │
                                                          │                     │
                                                          │  1. Dequeue job      │
                                                          │  2. Set status:      │
                                                          │     started          │
                                                          │  3. Call AI service  │
                                                          │  4. Set status:      │
                                                          │     finished/failed  │
                                                          └─────────────────────┘
```

### Queue Flow

1. Client sends `POST /ai` with a prompt and optional model
2. API validates the request, creates a job record in Redis with status `queued`
3. Job is enqueued to the `ai-jobs` RQ queue
4. API immediately returns `202 Accepted` with the `job_id`
5. Worker picks up the job, sets status to `started`
6. Worker calls the AI service (Groq API or mock)
7. On success: status set to `finished`, result stored
8. On failure: status set to `failed`, error stored; retries if attempts remain

### Worker Flow

1. Worker connects to Redis and starts listening on `ai-jobs` queue
2. When a job arrives, it calls `run_ai_job` from `app.services.ai_worker`
3. Worker updates job status to `started`
4. Worker delegates AI logic to `app.services.ai_service.call_ai`
5. On completion, status is set to `finished` with the result
6. On failure, status is set to `failed` with the error message
7. The worker logs each state transition for observability

### Running Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Verify
redis-cli ping
# PONG
```

### Running Worker

```bash
# Using the dedicated worker entry point (recommended)
python -m app.worker

# Or using the RQ CLI directly
rq worker ai-jobs --url redis://localhost:6379/0

# With logging
python -m app.worker 2>&1 | tee worker.log
```

### Running API

```bash
uvicorn app.main:app --reload --port 8000
```

### Example Requests

```bash
# Enqueue an AI job
curl -X POST http://localhost:8000/ai \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Tell me a joke", "model": "llama3-8b-8192"}'

# Response: 202 Accepted
# {"job_id":"<uuid>","status":"queued"}

# Poll job status
curl http://localhost:8000/jobs/<uuid>

# Response examples:
# {"job_id":"<uuid>","status":"queued","created_at":"...","attempts":0}
# {"job_id":"<uuid>","status":"started","created_at":"...","started_at":"...","attempts":0}
# {"job_id":"<uuid>","status":"finished","result":"...","created_at":"...","started_at":"...","finished_at":"...","attempts":0}
# {"job_id":"<uuid>","status":"failed","error":"...","created_at":"...","finished_at":"...","attempts":3}

# List recent jobs
curl http://localhost:8000/jobs?limit=10&offset=0

# Response:
# {"jobs":[...],"total":2}

# Enqueue with idempotency key
curl -X POST http://localhost:8000/ai \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: my-unique-key" \
  -d '{"prompt": "Hello"}'
```

### How Retries Work

Failed jobs are retried up to **3 times** with exponential backoff:

| Attempt | Interval |
|---------|----------|
| 1st     | 10s      |
| 2nd     | 60s      |
| 3rd     | 300s (5m)|

- Retries are configured at the RQ level via `Retry(max=3, interval=[10, 60, 300])`
- The worker increments `current_attempt` in job meta on each failure
- If `retries_left > 0`, the job is requeued with status `queued`
- After all retries are exhausted, the job status is set to `failed` with the last error
- An alert is sent via `app.services.alert.send_alert()` (stub — replace with Slack/email/webhook in production)
- Jobs have a timeout of 600s (10 minutes); any job exceeding this is automatically failed
- Job data is persisted in Redis with a 24h TTL, ensuring no job data is lost during retry cycles

### How Idempotency Works

Idempotency is handled via the **`Idempotency-Key`** header:

1. Client includes an `Idempotency-Key` header on `POST /ai`
2. The system checks if a job with this key was created within the last 24 hours
3. If found: the existing `job_id` is returned — no duplicate job is created
4. If not found: a new job is created and the key → job_id mapping is stored with a 24h TTL
5. The idempotency key is stored in Redis as `idempotency:<key>` with 86400s TTL

**Idempotency guarantee:** Running the same request with the same idempotency key will always return the same `job_id`. This prevents duplicate AI inferences when clients retry requests due to network issues.

## Project Architecture

### Project Structure

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

AI Jobs: Client → POST /ai → app.queue → RQ (Redis) → Worker → Groq API
                                       │
                                 GET /jobs/{id} ← status updates
                                       │
                                 GET /jobs ← list recent jobs
```

## Testing

```bash
# All unit tests (mocked Redis, no network required)
pytest

# With coverage
pytest --cov=app --cov-report=term-missing

# AI job tests
pytest tests/test_ai_unit.py -v

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

Test coverage spans models, routers, services, repositories, workers, and end-to-end flows.

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

# AI job
curl -X POST http://localhost:8000/ai -H "Content-Type: application/json" -d '{"prompt":"Hello","model":"llama3-8b-8192"}'
```

## Known Limitations

- Scraped book persistence requires PostgreSQL — SQLite is not supported for this feature
- AI jobs require Redis with an active RQ worker
- No email verification flow (disable Supabase's "Confirm email" setting for local development)
- The scraper runs synchronously within the request thread
- Supabase free-tier rate limits may affect auth end-to-end tests
- Job listing uses Redis `SCAN` which may be slow with very large job sets

# FlyRank Backend AI

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

### 4. Start the AI worker (optional)

AI background jobs require a running RQ worker in a separate process:

```bash
rq worker ai-jobs --url redis://localhost:6379/0
```

Alternatively, use the provided convenience script:

```bash
.\run_e2e.ps1
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
|--------|------------------|------|------------------------------|
| POST   | `/ai`            | No   | Enqueue an AI inference job    |
| GET    | `/jobs/{job_id}` | No   | Poll job status                 |

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

AI inference is processed asynchronously via RQ (Redis Queue), with the worker running as a separate process.

### Usage

```
POST /ai
{ "prompt": "Tell me a joke", "model": "llama3-8b-8192" }
→ 202 { "job_id": "<uuid>", "status_url": "/jobs/<uuid>" }

GET /jobs/<uuid>
→ 200 { "status": "queued" | "processing" | "completed" | "failed" }
```

### Idempotency

Include an `Idempotency-Key` header on `POST /ai` to prevent duplicate enqueues. If a job with the same key was created within the last 24 hours, the existing `job_id` is returned instead of creating a new job.

### Retries

Failed jobs are retried up to 3 times with exponential backoff (10s, 60s, 300s). After all retries are exhausted, the job status is set to `"failed"`, with `attempts: 3` and the last recorded error.

### Alerting

On permanent failure, `send_alert()` in `app/services/alert.py` logs at `CRITICAL` level. This is a stub intended to be replaced with a Slack, email, or PagerDuty webhook in production.

## Project Architecture

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
# All unit tests (mocked Supabase, no network required)
pytest

# Auth tests
pytest tests/routers/test_auth.py -v

# AI job tests
pytest tests/test_ai_unit.py -v

# End-to-end auth (requires real Supabase + a running server)
pytest tests/test_e2e.py -v -s

# End-to-end AI (requires real Redis + a running RQ worker)
pytest tests/test_ai_e2e.py -v -s
```

Test coverage spans 22 test files across models, routers, services, repositories, scrapers, and end-to-end flows.

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
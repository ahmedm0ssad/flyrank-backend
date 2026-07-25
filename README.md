# FlyRank — Auth, Login & Protect

A FastAPI task management API with Supabase authentication, PostgreSQL persistence, and a book scraping subsystem.

## Assignment Goal

Add user authentication with Supabase Auth (signup, login, logout) and protect specific endpoints behind Bearer token authorization.

## Features

- User authentication via Supabase Auth (signup, login, logout)
- Protected endpoints (profile, dashboard) behind Bearer token
- Public info endpoint (no auth required)
- Full CRUD for tasks with filtering and statistics
- Database-backed persistence (SQLite default, PostgreSQL optional)
- Book scraping from `http://books.toscrape.com/`
- Robots.txt compliance with rate-limited scraping
- Repository Protocol abstraction for database swap
- Redis health check on startup
- Docker Compose stack (PostgreSQL + Redis + App)

## Technologies Used

| Component      | Technology                              |
|----------------|-----------------------------------------|
| Framework      | FastAPI                                 |
| Server         | Uvicorn                                 |
| Validation     | Pydantic                                |
| Authentication | Supabase Auth                           |
| Database       | SQLite (default) / PostgreSQL 16        |
| DB Driver      | asyncpg (PostgreSQL) / sqlite3 (stdlib) |
| Cache          | Redis 7 (optional)                      |
| Container      | Docker + Docker Compose                 |
| Scraping       | requests + BeautifulSoup4 + lxml        |
| Config         | python-dotenv                           |

## Requirements

- Python 3.10+
- pip
- Supabase project (free tier)
- Docker (optional, for PostgreSQL stack)

## Installation

```bash
pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```
DATABASE_URL=postgresql://user:password@host:5432/dbname
REDIS_URL=redis://host:6379/0
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_anon_key_here
SUPABASE_SERVICE_KEY=your_service_role_key
PORT=8000
```

### Supabase Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. Go to Authentication → Settings and **disable "Confirm email"** for development
3. Copy your project URL and anon (public) key from the API settings
4. Set `SUPABASE_URL` and `SUPABASE_KEY` in `.env`

The `service_role` key is **never used** in the application code — it is only required for e2e tests.

## Running Locally (SQLite)

```bash
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

## Running with Docker (PostgreSQL)

```bash
docker compose up --build
```

## API Endpoints

### Auth

| Method | Path                  | Auth Required | Description                          |
|--------|-----------------------|---------------|--------------------------------------|
| POST   | `/auth/signup`        | No            | Create a new account                 |
| POST   | `/auth/login`         | No            | Sign in with email + password        |
| POST   | `/auth/logout`        | Yes (Bearer)  | Sign out (invalidate session)        |

### Protected

| Method | Path                    | Auth Required | Description                              |
|--------|-------------------------|---------------|------------------------------------------|
| GET    | `/protected/profile`    | Yes (Bearer)  | Get the authenticated user's profile     |
| GET    | `/protected/dashboard`  | Yes (Bearer)  | Authenticated user's dashboard           |

### Tasks

| Method | Path          | Auth Required | Description               |
|--------|---------------|---------------|---------------------------|
| GET    | `/tasks`      | No            | List tasks (filterable)   |
| GET    | `/tasks/{id}` | No            | Get a task by ID          |
| POST   | `/tasks`      | No            | Create a task             |
| PUT    | `/tasks/{id}` | No            | Update a task             |
| DELETE | `/tasks/{id}` | No            | Delete a task             |
| GET    | `/stats`      | No            | Task statistics           |

### Scraper

| Method | Path              | Auth Required | Description                          |
|--------|-------------------|---------------|--------------------------------------|
| POST   | `/scrape`         | No            | Scrape books (query: `?max_pages=5`) |

### General

| Method | Path          | Auth Required | Description                     |
|--------|---------------|---------------|---------------------------------|
| GET    | `/`           | No            | Welcome message                 |
| GET    | `/health`     | No            | Health check                    |
| GET    | `/public/info`| No            | Public information endpoint     |

## Authentication

The API uses **Supabase Auth** for user authentication. All credential and token operations go through the Supabase SDK — no self-rolled password hashing, JWT signing, or crypto.

Protected routes are wired with FastAPI's `HTTPBearer` security scheme. Open `/docs` in your browser, click the **Authorize** button, paste your Bearer token, and call protected endpoints directly from the Swagger UI.

The `get_current_user` dependency in `app/dependencies/auth.py` validates the Bearer token against Supabase and returns the user profile. Invalid or expired tokens return `401 Unauthorized`.

## Database

### SQLite (Default)

When `DATABASE_URL` is not set, the app uses SQLite via Python's standard library `sqlite3`. The database file `tasks.db` is created automatically in the project root on first run. Schema is auto-created with seed data on first startup.

### PostgreSQL (via DATABASE_URL)

When `DATABASE_URL` is set, the app connects to PostgreSQL via asyncpg with a connection pool (min 2, max 10). The `db/init.sql` file creates both the `tasks` and `scraped_books` tables with relevant indexes.

## Scraper Architecture

The app scrapes book data from `http://books.toscrape.com/` — a demo bookstore.

| Component | File                       | Role                                                |
|-----------|----------------------------|-----------------------------------------------------|
| Session   | `app/scrapers/session.py`  | HTTP session with retry, rate-limiting, robots.txt  |
| Parser    | `app/scrapers/parser.py`   | BeautifulSoup parsing of listing + detail pages     |
| Cleaner   | `app/scrapers/cleaner.py`  | Normalise prices, ratings, availability             |
| Pipeline  | `app/scrapers/pipeline.py` | Orchestrates page iteration, detail fetch, merge    |
| Repository| `app/repositories/scraped_book_repo.py` | PostgreSQL bulk_upsert via ON CONFLICT |
| Service   | `app/services/scraped_book_service.py` | Manages scrape lifecycle and persistence   |
| Endpoint  | `POST /scrape?max_pages=5` | Triggers a scrape; returns (books_saved, errors)    |

Requires `DATABASE_URL` pointing to a running PostgreSQL instance (e.g. via Docker).

## Architecture

### Request Flow

```
Client
  │
  ▼
 Routes (app/routers/ — auth.py, tasks.py, scrape.py)
  │
  ▼
 Service (app/services/ — task_service.py, scraped_book_service.py)
  │
  ▼
 Repository (app/repositories/ — TaskRepository Protocol)
  │
  ├── PostgresRepository (PostgreSQL via asyncpg)
  ├── SqliteRepository (SQLite via stdlib sqlite3)    ← default
  └── ScrapedBookRepository (PostgreSQL for scraped books)
```

### Project Structure

```
app/
    main.py                 # FastAPI app, router mounting, lifespan
    database.py             # asyncpg connection pool from .env
    supabase_client.py      # Supabase async client singleton
    dependencies/
        auth.py             # Bearer token dependency (get_current_user)
    models/
        task.py             # Task Pydantic schemas
        auth.py             # Auth request schemas
        scraped_book.py     # ScrapedBook Pydantic schemas
    services/
        task_service.py     # Task business logic
        scraped_book_service.py  # Scrape orchestration
    repositories/
        protocol.py         # TaskRepository Protocol
        sqlite_repo.py      # SQLite repository (default)
        postgres_repo.py    # Postgres repository (asyncpg)
        inmemory_repo.py    # In-memory fallback
        scraped_book_repo.py # ScrapedBook PostgreSQL repository
    routers/
        tasks.py            # Task HTTP endpoints
        auth.py             # Auth HTTP endpoints (signup, login, logout)
        scrape.py           # Scrape HTTP endpoint
    scrapers/
        session.py          # HTTP session with retry + robots.txt
        parser.py           # BeautifulSoup parsing
        cleaner.py          # Data normalisation
        pipeline.py         # Scrape orchestration
db/
    init.sql                # PostgreSQL DDL (tasks + scraped_books)
scripts/
    seed_explain.py         # EXPLAIN ANALYZE before/after index
```

## Testing

Run all unit tests (mocked Supabase, no network required):

```bash
pytest
```

Run auth-specific tests:

```bash
pytest tests/routers/test_auth.py -v
```

Auth tests cover:

| Test class      | What it tests                                    |
|-----------------|--------------------------------------------------|
| `TestSignup`    | signup success, missing fields, Supabase errors  |
| `TestLogin`     | login success, invalid credentials, other errors |
| `TestProtected` | profile/dashboard with valid, missing, tampered tokens |
| `TestLogout`    | logout with and without a Bearer token           |

The Supabase client is fully mocked via `monkeypatch` — no real Supabase calls are made in unit tests.

### End-to-End Auth Tests

`tests/test_e2e.py` hits a real Supabase project and the running FastAPI server:

```bash
# 1. Start the server (ensure .env has SUPABASE_URL and SUPABASE_KEY)
uvicorn app.main:app --port 8000

# 2. In another terminal
pytest tests/test_e2e.py -v -s
```

The e2e test creates a real user, then exercises signup, login, protected endpoints, tampered tokens, and logout.

## Example Requests

```bash
# Sign up
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass"}'

# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass"}'

# Use the returned access_token for protected endpoints
curl http://localhost:8000/protected/profile \
  -H "Authorization: Bearer <access_token>"

# List tasks with filtering
curl "http://localhost:8000/tasks?search=fastapi&done=false"

# Get task statistics
curl http://localhost:8000/stats

# Trigger a book scrape (requires PostgreSQL with DATABASE_URL set)
curl -X POST "http://localhost:8000/scrape?max_pages=3"
```

## Known Limitations

- Scraped books require PostgreSQL — not available with SQLite
- No rate limiting on auth endpoints
- Supabase email confirmation should be disabled in development
- No background job queue (scraping runs synchronously in the request)
- Supabase `service_role` key is used only for e2e tests

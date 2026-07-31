# FlyRank — AI Background Jobs + PDF Report Generator

A FastAPI backend combining task management, web scraping, authentication, asynchronous AI job processing via RQ (Redis Queue) and Groq LLM inference, and automated PDF report generation.

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
- **PDF Report Generation** — asynchronous background report generation via RQ with real database aggregation

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
REDIS_URL=redis://host:6380/0
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
# Terminal 1: start Redis (host port 6380 - matches the Compose stack)
docker run -d -p 6380:6379 redis:7-alpine

# Terminal 2: start the worker
python -m app.core.worker

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

### Reports

| Method | Path                                    | Auth | Description                       |
|--------|-----------------------------------------|------|-----------------------------------|
| POST   | `/reports`                              | No   | Enqueue a PDF report generation    |
| GET    | `/reports/{job_id}`                     | No   | Poll report status and metadata    |
| GET    | `/reports/files/{filename}`             | No   | Download a generated PDF file      |

### Widgets

| Method | Path           | Auth   | Description                 |
|--------|----------------|--------|-----------------------------|
| GET    | `/widgets`     | Bearer | List widgets (`?search=&active=&page=&page_size=`) |
| POST   | `/widgets`     | Bearer | Create a widget              |
| GET    | `/widgets/{id}`| Bearer | Get a widget by ID           |
| PUT    | `/widgets/{id}`| Bearer | Update a widget              |
| DELETE | `/widgets/{id}`| Bearer | Delete a widget              |

### Widget Embedding

| Method | Path                              | Auth | Description                         |
|--------|-----------------------------------|------|-------------------------------------|
| GET    | `/public/widget/{id}/config`      | No   | Public widget config (JSON)         |
| GET    | `/public/widget/{id}/widget.js`   | No   | Embeddable widget JS bundle         |
| POST   | `/public/widget/{id}/submit`      | No   | Submit a lead from the widget       |

### Leads

| Method | Path                                      | Auth   | Description                         |
|--------|-------------------------------------------|--------|-------------------------------------|
| GET    | `/widgets/{id}/leads`                     | Bearer | List leads for a widget (filters/pagination) |
| GET    | `/widgets/{id}/leads/{lead_id}`           | Bearer | Get a single lead                   |
| GET    | `/widgets/{id}/stats`                     | Bearer | Lead statistics for a widget        |
| GET    | `/widgets/{id}/export`                    | Bearer | Export widget leads as CSV          |
| DELETE | `/widgets/{id}/leads/{lead_id}`           | Bearer | Delete a lead                       |
| POST   | `/widgets/{id}/leads/batch-delete`        | Bearer | Batch delete leads                  |
| POST   | `/widgets/{id}/leads/{lead_id}/re-enrich` | Bearer | Re-run enrichment for a lead        |
| GET    | `/leads`                                  | Bearer | List leads across all widgets       |
| GET    | `/leads/stats`                            | Bearer | Global lead statistics              |

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

## PDF Report Generation — Architecture

Reports are generated asynchronously via RQ (Redis Queue), with a dedicated worker consuming jobs from the `report-jobs` queue. The PDF is produced server-side using ReportLab and stored on disk in the `generated_reports/` directory.

### Queue Flow

1. Client sends `POST /reports` — the API creates a job record in Redis and enqueues it
2. API immediately returns `202 Accepted` with the `job_id`
3. Worker picks up the job, sets status to `started`, updates the reports DB record
4. Worker queries the database for aggregations (scraped books stats, AI jobs stats)
5. Worker generates a PDF using ReportLab with tables, sections, and page numbering
6. On success: status set to `finished`, file path stored in DB
7. On failure: status set to `failed`, error stored; retries if attempts remain

### Retry Policy

Same three-tier backoff as AI jobs: 10s → 60s → 300s.

### Download

PDFs are served via `GET /reports/files/{filename}` with path-traversal protection and filename validation. Only files within the `generated_reports/` directory can be downloaded.

## Widget & Lead Capture — Architecture

Widgets are embedded on third-party sites and load a JS bundle (`/public/widget/{id}/widget.js`) that renders a configurable form (`/public/widget/{id}/config`). Submissions go through a validation and anti-abuse pipeline before the lead is stored; enrichment and a confirmation webhook run asynchronously afterwards.

### Submission Pipeline

1. Visitor submits the widget form → `POST /public/widget/{id}/submit`
2. API looks up the widget and rejects unknown or inactive widgets (`404`)
3. Origin validation checks the `Origin`/`Referer` header against the widget's configured domain — rejected requests return `403`
4. Rate limiting checks the visitor across three tiers (per-IP, per-widget-IP, per-widget-global) in a 60s window and returns `429` with a `Retry-After` header when exceeded
5. A hidden honeypot field, if filled in, records the lead as spam (score `1.0`) and skips enrichment and webhook dispatch
6. A visitor fingerprint is computed and compared against previously seen submissions — duplicates return the existing lead instead of creating a new one
7. Legitimate submissions are spam-scored, then stored as a lead
8. An enrichment job is enqueued (async): a worker resolves IP geolocation and updates the lead
9. A confirmation webhook is dispatched (async, fire-and-forget) to the widget's configured `webhook_url` — it never blocks or fails the submission
10. The `201` response returns the new `lead_id`; the lead is immediately visible in the dashboard

```mermaid
flowchart TD
    A[Visitor submits form] --> B[POST /public/widget/:id/submit]
    B --> C{Widget active?}
    C -- no --> C404[404 Widget not found]
    C -- yes --> D{Origin allowed?}
    D -- no --> D403[403 Origin rejected]
    D -- yes --> E{Rate limit ok?}
    E -- no --> E429[429 Retry-After]
    E -- yes --> F{Honeypot filled?}
    F -- yes --> H[Mark spam score 1.0]
    F -- no --> G{Duplicate fingerprint?}
    G -- yes --> G2[Return existing lead]
    G -- no --> I[Spam score submission]
    H --> J[Store lead]
    G2 --> J
    I --> J
    J --> K[Enqueue enrichment job]
    J --> L[Dispatch webhook fire-and-forget]
    J --> M[201 lead_id returned]
    K --> N[Worker: geo enrichment updates lead]
    M --> O[Visible in dashboard list / stats / export]
    N --> O
```

### Webhook

When a widget's config sets a `webhook_url`, a POST with `{lead_id, widget_id, form_data, created_at}` is fired after each legitimate submission. Dispatch is asynchronous and fail-open: timeouts and provider errors are logged, never raised, so a webhook outage cannot turn a successful submission into an error.

## Project Structure

```
app/
    main.py                     # FastAPI app, lifespan, router mounting
    core/
        database.py             # asyncpg pool (Postgres) / sqlite3 (default)
        queue.py                # Redis connection, RQ queue, job CRUD
        supabase.py             # Supabase admin client
        worker.py               # Standalone RQ worker entry point
    dependencies/
        auth.py                 # Bearer token dependency
        embed.py                # Widget origin validation
        leads.py                # Rate limiting dependencies
        services.py             # DI providers (get_lead_repo, get_widget_repo, get_redis)
    middleware/
        body_limit.py           # 50KB request body size limit
    models/
        task.py, auth.py, scraped_book.py, job.py, report.py
        lead.py, widget.py
    services/
        task_service.py         # Task business logic
        scraped_book_service.py # Scrape orchestration
        ai_service.py           # Groq API call (with mock fallback)
        ai_worker.py            # RQ worker function
        report_service.py       # Report enqueue + metadata + aggregation
        report_worker.py        # RQ worker function for PDF generation
        pdf_generator.py        # ReportLab PDF document builder
        alert.py                # Failure alert stub
        embed_service.py        # Public widget config/JS lookup
        widget_service.py       # Widget CRUD business logic
        widget_js.py            # Widget JS bundle renderer
        lead_service.py         # Lead submission pipeline, stats, export
        lead_worker.py          # RQ worker for lead enrichment
        spam_service.py         # Spam scoring
        fingerprint_service.py  # Fingerprint computation + dedup
        geo_service.py          # IP geolocation enrichment (ipapi.co/ipinfo/ip-api)
        webhook_service.py      # Fail-open webhook dispatch
    repositories/
        protocol.py             # Repository Protocols
        sqlite_repo.py          # SQLite (default)
        postgres_repo.py        # PostgreSQL via asyncpg
        postgres_widget_repo.py # Widget PostgreSQL implementation
        widget_repo.py          # Widget in-memory implementation
        lead_repo.py            # Lead in-memory implementation
        scraped_book_repo.py    # ScrapedBook PostgreSQL
        report_repo.py          # Report CRUD (SQLite + PostgreSQL)
    routers/
        tasks.py                # Task CRUD + stats
        auth.py                 # Auth endpoints
        scrape.py               # Scrape trigger
        ai.py                   # AI job enqueue + status
        reports.py              # Report enqueue, status, download
        widgets.py              # Widget CRUD
        embed.py                # Public widget config + JS
        leads.py                # Lead submission + dashboard + cross-widget
    scrapers/
        session.py, parser.py, cleaner.py, pipeline.py
db/
    init.sql                    # PostgreSQL DDL (tasks, scraped_books, reports, widgets, leads, rate_limits)
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

# Report tests
pytest tests/routers/test_reports.py -v
pytest tests/services/test_pdf_generator.py -v
pytest tests/services/test_report_service.py -v
pytest tests/test_report_worker.py -v
pytest tests/repositories/test_report_repo.py -v
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

# Enqueue a PDF report
curl -X POST http://localhost:8000/reports

# Response: 202 Accepted
# {"job_id":"<uuid>","status":"queued"}

# Poll report status
curl http://localhost:8000/reports/<uuid>

# Download generated PDF
curl -o report.pdf http://localhost:8000/reports/files/hr_report_<uuid>.pdf
```

## Known Limitations

- Scraped book persistence requires PostgreSQL — SQLite is not supported for this feature
- AI jobs and report generation require Redis with an active RQ worker
- No email verification flow (disable Supabase's "Confirm email" setting for local development)
- The scraper runs synchronously within the request thread
- Supabase free-tier rate limits may affect auth end-to-end tests
- Job listing uses Redis `SCAN` which may be slow with very large job sets

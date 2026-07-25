# FlyRank — The Polite Scraper

A FastAPI task management API with a polite web scraping subsystem for books.toscrape.com, backed by database persistence and Docker Compose.

## Assignment Goal

Add a polite web scraper that respects robots.txt, rate-limits requests, and persists scraped book data to PostgreSQL with proper error handling and data cleaning.

## Features

- Full CRUD for tasks with search/filter and statistics
- Database-backed persistence (SQLite default, PostgreSQL optional)
- Book scraping from `http://books.toscrape.com/`
- Robots.txt compliance with automatic crawl delay
- Rate-limited HTTP requests with exponential backoff retry
- BeautifulSoup parsing of listing and detail pages
- Data cleaning and normalisation (prices, ratings, availability)
- PostgreSQL bulk upsert for scraped books (`ON CONFLICT`)
- Docker Compose stack (PostgreSQL + Redis + App)
- Redis health check on startup
- EXPLAIN ANALYZE script for index performance

## Technologies Used

| Component      | Technology                              |
|----------------|-----------------------------------------|
| Framework      | FastAPI                                 |
| Server         | Uvicorn                                 |
| Validation     | Pydantic                                |
| Database       | SQLite (default) / PostgreSQL 16        |
| DB Driver      | asyncpg (PostgreSQL) / sqlite3 (stdlib) |
| Cache          | Redis 7 (optional)                      |
| Container      | Docker + Docker Compose                 |
| Scraping       | requests + BeautifulSoup4 + lxml        |
| Config         | python-dotenv                           |

## Requirements

- Python 3.10+
- pip
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
```

- `DATABASE_URL` — if set, the app uses PostgreSQL via asyncpg. If omitted, the app uses SQLite (`tasks.db`).
- `REDIS_URL` — if set, the app pings Redis on startup and includes connection status in responses.

## Running Locally (SQLite)

```bash
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

## Running with Docker (PostgreSQL + Redis)

```bash
docker compose up --build
```

## API Endpoints

| Method | Path              | Description                           |
|--------|-------------------|---------------------------------------|
| GET    | `/`               | Welcome message                       |
| GET    | `/health`         | Health check                          |
| GET    | `/tasks`          | List tasks (`?search=&done=true`)     |
| GET    | `/tasks/{id}`     | Get a task by ID                      |
| POST   | `/tasks`          | Create a task                         |
| PUT    | `/tasks/{id}`     | Update a task                         |
| DELETE | `/tasks/{id}`     | Delete a task                         |
| GET    | `/stats`          | Task statistics                       |
| POST   | `/scrape`         | Scrape books (`?max_pages=5`)         |

## Scraper Architecture

The scraper fetches book data from `http://books.toscrape.com/` — a demo bookstore with catalogue and detail pages.

### Components

| Component  | File                           | Role                                                |
|------------|--------------------------------|-----------------------------------------------------|
| Session    | `app/scrapers/session.py`      | HTTP session with retry, rate-limiting, robots.txt  |
| Parser     | `app/scrapers/parser.py`       | BeautifulSoup parsing of listing + detail pages     |
| Cleaner    | `app/scrapers/cleaner.py`      | Normalise prices, ratings, availability             |
| Pipeline   | `app/scrapers/pipeline.py`     | Orchestrates page iteration, detail fetch, merge    |
| Repository | `app/repositories/scraped_book_repo.py` | PostgreSQL bulk_upsert via ON CONFLICT    |
| Service    | `app/services/scraped_book_service.py` | Manages scrape lifecycle and persistence   |

### ScrapeSession

The `ScrapeSession` class in `app/scrapers/session.py` provides:

- **User-Agent**: Identifies as `FlyRankBot/1.0` (educational project)
- **Retry strategy**: Up to 5 retries with exponential backoff for 429, 500, 502, 503, 504 responses
- **Robots.txt compliance**: Fetches and parses `/robots.txt`, respects `Disallow` rules and `Crawl-Delay`
- **Rate limiting**: Enforces minimum delay between requests (default 1s, overridden by robots.txt `Crawl-Delay`)

### Pipeline

The `run()` function in `app/scrapers/pipeline.py`:

1. Starts at `catalogue/page-1.html`
2. Parses each listing page for book URLs, titles, ratings, prices, availability
3. Fetches each book's detail page for description, category, UPC, image URL
4. Merges listing and detail data
5. Cleans and normalises fields
6. Returns `(books_data, errors)` tuple

### Persistence

Scraped books require PostgreSQL. When `DATABASE_URL` is set:
- Books are saved via `bulk_upsert` which uses `INSERT ... ON CONFLICT (url) DO UPDATE`
- The `scraped_books` table has indexes on `category` and `url`
- Returns `(books_scraped, books_saved, errors, duration_seconds)`

Without PostgreSQL, the endpoint returns an informative error.

## Database

### SQLite (Default)

The app uses SQLite via Python's standard library `sqlite3` when `DATABASE_URL` is not set. The `tasks.db` file is created automatically with the `tasks` table and 3 seed tasks on first run.

### PostgreSQL

When `DATABASE_URL` is set, the app connects to PostgreSQL via asyncpg with a connection pool. The `db/init.sql` creates both `tasks` and `scraped_books` tables with indexes:

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    done BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks(done);

CREATE TABLE IF NOT EXISTS scraped_books (
    id SERIAL PRIMARY KEY,
    url VARCHAR(500) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    price NUMERIC(10,2),
    availability VARCHAR(100),
    rating INTEGER,
    description TEXT,
    category VARCHAR(200),
    upc VARCHAR(50),
    image_url VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scraped_books_category ON scraped_books(category);
CREATE INDEX IF NOT EXISTS idx_scraped_books_url ON scraped_books(url);
```

## Architecture

### Request Flow

```
Client
  │
  ▼
 Routes (app/routers/ — tasks.py, scrape.py)
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
     │
     ▼
 PostgreSQL (db service, pgdata volume)
```

### Project Structure

```
app/
    main.py                 # FastAPI app, router mounting, lifespan
    database.py             # asyncpg connection pool from .env
    models/
        task.py             # Task Pydantic schemas
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

### Repository Protocol

`app/repositories/protocol.py` defines the `TaskRepository` Protocol for database-agnostic task operations.

## Testing

Run all unit tests:

```bash
pytest
```

Tests cover:

| Directory       | Tests                                          |
|-----------------|------------------------------------------------|
| `test_main`     | Home, health, validation, and error handlers   |
| `routers/`      | Task CRUD, scrape endpoint, SQLite e2e         |
| `services/`     | Task and scraped book service logic            |
| `repositories/` | InMemory, SQLite, Postgres, ScrapedBook repos  |
| `models/`       | Task and ScrapedBook model validation          |
| `scrapers/`     | Session, parser, and cleaner unit tests        |

### Redis Connectivity

Redis is optional. If `REDIS_URL` is configured, the app pings Redis on startup and includes `"redis": "connected"` in `/health` and `/` responses. The app functions normally if Redis is unavailable.

## Example Requests

```bash
# List tasks with search and filter
curl "http://localhost:8000/tasks?search=fastapi&done=false"

# Get task statistics
curl http://localhost:8000/stats

# Trigger a book scrape (requires PostgreSQL with DATABASE_URL set)
curl -X POST "http://localhost:8000/scrape?max_pages=3"

# Scrape response
# {"books_scraped": 60, "books_saved": 60, "errors": [], "duration_seconds": 12.34}
```

## Known Limitations

- Scraper requires PostgreSQL — not available with SQLite
- Scraping runs synchronously in the request (may time out for many pages)
- No authentication on any endpoint
- No background job queue for long-running scrapes

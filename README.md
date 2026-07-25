# FlyRank — Connecting to the Database

A FastAPI task management API with database-backed persistence. Uses SQLite by default with PostgreSQL as a production-grade alternative, selectable via environment variable.

## Assignment Goal

Replace in-memory storage with a real database while keeping the service and route layer unchanged through a repository abstraction.

## Features

- Full CRUD for tasks with database persistence
- SQLite as the default database (zero configuration)
- PostgreSQL support via `DATABASE_URL` environment variable
- Task filtering by `search` (title) and `done` status on `GET /tasks`
- Task statistics endpoint (`GET /stats`)
- Repository Protocol abstraction for database swap
- Docker Compose stack with PostgreSQL and Redis
- Redis health check on startup
- EXPLAIN ANALYZE script for index performance benchmarking

## Technologies Used

| Component  | Technology                           |
|------------|--------------------------------------|
| Framework  | FastAPI                              |
| Server     | Uvicorn                              |
| Validation | Pydantic                             |
| Database   | SQLite (default) / PostgreSQL 16     |
| DB Driver  | asyncpg (PostgreSQL) / sqlite3 (stdlib) |
| Cache      | Redis 7 (optional)                   |
| Container  | Docker + Docker Compose              |
| Config     | python-dotenv                        |

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

- `DATABASE_URL` — if set, the app uses PostgreSQL via asyncpg. If omitted, the app uses SQLite (file: `tasks.db`).
- `REDIS_URL` — if set, the app pings Redis on startup and includes connection status in responses.

## Running Locally (SQLite — default)

```bash
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

## Running with Docker (PostgreSQL + Redis)

```bash
docker compose up --build
```

This starts PostgreSQL 16, Redis 7, and the FastAPI app. Ensure `.env` has `DATABASE_URL` and `REDIS_URL` set.

## API Endpoints

| Method | Path          | Description               | Query Parameters                      |
|--------|---------------|---------------------------|---------------------------------------|
| GET    | `/`           | Welcome message           |                                       |
| GET    | `/health`     | Health check              |                                       |
| GET    | `/tasks`      | List tasks (filterable)   | `?search=&done=true`                  |
| GET    | `/tasks/{id}` | Get a task by ID          |                                       |
| POST   | `/tasks`      | Create a task             |                                       |
| PUT    | `/tasks/{id}` | Update a task             |                                       |
| DELETE | `/tasks/{id}` | Delete a task             |                                       |
| GET    | `/stats`      | Task statistics           |                                       |

## Database

### SQLite (Default)

When `DATABASE_URL` is not set, the app uses SQLite via Python's standard library `sqlite3`. The database file `tasks.db` is created automatically in the project root on first run.

- Schema auto-created with `CREATE TABLE IF NOT EXISTS tasks(...)` on startup.
- If the table is empty, 3 example tasks are seeded automatically.
- All queries use `?` placeholders with parameter tuples — no string concatenation of user input.
- Each request opens a new connection (safe at this scale).

### PostgreSQL (via DATABASE_URL)

When `DATABASE_URL` is set, the app connects to PostgreSQL via asyncpg with a connection pool (min 2, max 10) and automatic retry on startup (up to 5 attempts).

The `db/init.sql` file is mounted into the PostgreSQL container to auto-create the `tasks` table and an index on `done`:

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    done BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks(done);
```

## Architecture

### Request Flow

```
Client
  │
  ▼
 Routes (app/routers/tasks.py)
  │
  ▼
 Service (app/services/task_service.py)
  │
  ▼
 Repository (app/repositories/ — TaskRepository Protocol)
  │
  ├── PostgresRepository (PostgreSQL via asyncpg)
  ├── SqliteRepository (SQLite via stdlib sqlite3)    ← default
  └── InMemoryRepository (in-memory dict fallback)
```

The `task_service.py` module selects the repository at import time:
- If `DATABASE_URL` is set → `PostgresRepository`
- Otherwise → `SqliteRepository`

### Repository Protocol

`app/repositories/protocol.py` defines the `TaskRepository` Protocol:

| Method          | Signature                                      |
|-----------------|------------------------------------------------|
| `create_task`   | `(task_data: TaskCreate) -> TaskResponse`      |
| `get_all_tasks` | `(search?, done?) -> list[TaskResponse]`       |
| `get_task`      | `(task_id: int) -> Optional[TaskResponse]`     |
| `update_task`   | `(task_id: int, task_data: TaskUpdate) -> TaskResponse?` |
| `delete_task`   | `(task_id: int) -> bool`                       |
| `get_stats`     | `() -> dict`                                   |

### Project Structure

```
app/
    main.py                 # FastAPI app, router mounting, Redis ping, lifespan
    database.py             # asyncpg connection pool from .env
    models/
        task.py             # Pydantic schemas
    services/
        task_service.py     # Business logic — delegates to repository
    repositories/
        protocol.py         # TaskRepository Protocol
        sqlite_repo.py      # SQLite repository (default)
        postgres_repo.py    # Postgres repository (asyncpg)
        inmemory_repo.py    # In-memory fallback
    routers/
        tasks.py            # HTTP endpoints (async)
db/
    init.sql                # PostgreSQL table DDL + index
scripts/
    seed_explain.py         # EXPLAIN ANALYZE before/after index
```

### Redis Connectivity

Redis is an optional dependency. If `REDIS_URL` is configured:
- The app pings Redis on startup and logs the result.
- The `/health` and `/` endpoints include `"redis": "connected"` when the connection is alive.
- The app continues to function normally if Redis is unavailable.

## EXPLAIN ANALYZE — Index Performance

Run the seed script against the running PostgreSQL stack:

```bash
pip install -r requirements.txt
python scripts/seed_explain.py --rows 10000
```

The script seeds N rows, then runs `EXPLAIN ANALYZE` on a filtered query before and after creating an index on `tasks(done)`.

## Persistence Proof

### SQLite

```bash
# 1. Start the app
uvicorn app.main:app --reload

# 2. Create a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "persistent task", "done": false}'

# 3. Stop the server (Ctrl+C), then start again

# 4. Fetch the task — it still exists
curl http://localhost:8000/tasks/1
```

### Docker (PostgreSQL)

```bash
# 1. Start the stack
docker compose up --build

# 2. Create a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "persistent task", "done": false}'

# 3. Stop everything
docker compose down

# 4. Start again
docker compose up

# 5. Fetch the task — it still exists
curl http://localhost:8000/tasks/1
```

The volume `pgdata` in `docker-compose.yml` ensures PostgreSQL data persists across container restarts.

## Known Limitations

- No authentication — all endpoints are public
- SQLite used in single-connection mode (not suitable for high concurrency)
- No scraping functionality

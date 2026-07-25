# FlyRank — Containerize Your Stack

A containerized FastAPI task management API with PostgreSQL persistence, Redis caching, and Docker Compose orchestration.

## Assignment Goal

Containerize the full application stack — FastAPI, PostgreSQL, and Redis — using Docker and Docker Compose, with environment-based repository switching.

## Features

- Full CRUD for tasks with PostgreSQL persistence
- Docker Compose stack (FastAPI + PostgreSQL 16 + Redis 7)
- Repository Protocol abstraction for database swap
- In-memory fallback when no `DATABASE_URL` is set
- Redis health check on startup
- EXPLAIN ANALYZE script for index performance benchmarking
- `.dockerignore` for optimized Docker build context

## Technologies Used

| Component  | Technology                        |
|------------|-----------------------------------|
| Framework  | FastAPI                           |
| Server     | Uvicorn                           |
| Validation | Pydantic                          |
| Database   | PostgreSQL 16                     |
| DB Driver  | asyncpg                           |
| Cache      | Redis 7                           |
| Container  | Docker + Docker Compose           |
| Config     | python-dotenv                     |

## Requirements

- Python 3.10+
- pip
- Docker and Docker Compose

## Installation

```bash
pip install -r requirements.txt
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```
DATABASE_URL=postgresql://flyrank:flyrank_pass@db:5432/flyrank
REDIS_URL=redis://redis:6379/0
```

- `DATABASE_URL` — if set, the app uses PostgreSQL via asyncpg. If omitted, the app uses in-memory storage.
- `REDIS_URL` — if set, the app pings Redis on startup and includes connection status in responses.

## Running with Docker (Recommended)

```bash
docker compose up --build
```

This starts PostgreSQL 16, Redis 7, and the FastAPI app. The app is available at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

## Running Locally (In-Memory)

```bash
uvicorn app.main:app --reload
```

Without `DATABASE_URL` set, the app uses in-memory storage with seed data. Data is lost when the server stops.

## API Endpoints

| Method | Path          | Description      | Status Codes |
|--------|---------------|------------------|--------------|
| GET    | `/`           | Welcome message  | 200          |
| GET    | `/health`     | Health check     | 200          |
| GET    | `/tasks`      | List all tasks   | 200          |
| GET    | `/tasks/{id}` | Get a task by ID | 200, 404     |
| POST   | `/tasks`      | Create a task    | 201          |
| PUT    | `/tasks/{id}` | Update a task    | 200, 404     |
| DELETE | `/tasks/{id}` | Delete a task    | 204, 404     |

## Database

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

The volume `pgdata` in `docker-compose.yml` ensures PostgreSQL data persists across container restarts.

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
  └── InMemoryRepository (in-memory dict fallback)
  │
  ▼
 PostgreSQL (db service, pgdata volume)
```

The `task_service.py` module selects the repository at import time:
- If `DATABASE_URL` is set → `PostgresRepository`
- Otherwise → `InMemoryRepository`

### Repository Protocol

`app/repositories/protocol.py` defines the `TaskRepository` Protocol:

| Method          | Signature                                      |
|-----------------|------------------------------------------------|
| `create_task`   | `(task_data: TaskCreate) -> TaskResponse`      |
| `get_all_tasks` | `() -> list[TaskResponse]`                     |
| `get_task`      | `(task_id: int) -> Optional[TaskResponse]`     |
| `update_task`   | `(task_id: int, task_data: TaskUpdate) -> TaskResponse?` |
| `delete_task`   | `(task_id: int) -> bool`                       |

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

Redis runs as a `redis:7-alpine` service in `docker-compose.yml` with a health check. On startup, the app pings Redis and logs the result. When connected, the `/health` and `/` endpoints include `"redis": "connected"`. The app continues to function normally if Redis is unavailable.

## Persistence Proof

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

## EXPLAIN ANALYZE — Index Performance

Run the seed script against the running PostgreSQL stack:

```bash
pip install -r requirements.txt
python scripts/seed_explain.py --rows 10000
```

The script seeds N rows, then runs `EXPLAIN ANALYZE` on a filtered query before and after creating an index on `tasks(done)`.

## Example Requests

```bash
# List all tasks
curl http://localhost:8000/tasks

# Create a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "My task", "done": false}'

# Get a task by ID
curl http://localhost:8000/tasks/1
```

## Known Limitations

- No authentication — all endpoints are public
- No SQLite support (PostgreSQL or in-memory only)
- No task filtering or statistics endpoints

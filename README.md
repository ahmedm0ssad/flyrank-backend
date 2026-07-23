# FlyRank Backend AI Engineering

## Week 3 · Assignment A2 — Connecting CRUD to SQLite

### Run (dev — SQLite, default)

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

App available at `http://localhost:8000`, Swagger at `http://localhost:8000/docs`.

### Run (Docker — PostgreSQL)

```bash
docker compose up --build
```

### Endpoints

| Method | Path             | Description              |
|--------|------------------|--------------------------|
| GET    | `/`              | Welcome message          |
| GET    | `/health`        | Health check             |
| GET    | `/tasks`         | List all tasks           |
| GET    | `/tasks/{id}`    | Get a task by ID         |
| POST   | `/tasks`         | Create a task            |
| PUT    | `/tasks/{id}`    | Update a task            |
| DELETE | `/tasks/{id}`    | Delete a task            |
| GET    | `/stats`         | Task statistics          |
| POST   | `/scrape`        | Scrape books to database |

Swagger docs at `/docs`.

### SQLite (default, no Docker)

When `DATABASE_URL` is not set, the app uses **SQLite** via Python's standard library `sqlite3` (no extra dependencies). Why SQLite? It's a single file, requires zero setup, and survives restarts — the simplest path from in-memory to persistence.

- **Database file**: `tasks.db` — created automatically at the project root on first run, gitignored so each clone starts fresh.
- **Schema**: Auto-created `CREATE TABLE IF NOT EXISTS tasks(...)` on startup.
- **Seeding**: If the table is empty on startup, 3 example tasks are inserted. The guard is `SELECT COUNT(*) FROM tasks` — never duplicates rows. Deleting `tasks.db` transparently recreates and reseeds.
- **Persistence**: Data survives app restarts as long as `tasks.db` remains on disk.
- **Connection strategy**: One `sqlite3.connect()` per request. Safe at this scale. No thread sharing.
- **SQL safety**: All queries use `?` placeholders with parameter tuples. No string concatenation of user input.

Example SQL query run behind `GET /tasks`:

```sql
SELECT id, title, done, created_at, updated_at
FROM tasks
WHERE done = 1
ORDER BY title;
```

> **Screenshot**: Open `tasks.db` in [DB Browser for SQLite](https://sqlitebrowser.org/) to view rows and run queries. Add your screenshot at `screenshots/database.png`.

### Persistence proof

```bash
# 1. Start the app
uvicorn app.main:app --reload

# 2. Create a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "persistent task", "done": false}'

# 3. Note the returned ID (e.g. 4)

# 4. Stop the server (Ctrl+C), then start again

# 5. Fetch the task — it still exists
curl http://localhost:8000/tasks/4
```

---

### Scraper subsystem

The app scrapes book data from `http://books.toscrape.com/` — a demo bookstore.

| Component | File | Role |
|-----------|------|------|
| Session | `app/scrapers/session.py` | HTTP session with retry, rate-limiting, `robots.txt` compliance |
| Parser | `app/scrapers/parser.py` | BeautifulSoup parsing of listing + detail pages |
| Cleaner | `app/scrapers/cleaner.py` | Normalise prices, ratings, availability |
| Pipeline | `app/scrapers/pipeline.py` | Orchestrates page iteration, detail fetch, merge, clean |
| Repository | `app/repositories/scraped_book_repo.py` | PostgreSQL `bulk_upsert` via `ON CONFLICT` |
| Endpoint | `POST /scrape?max_pages=5` | Triggers a scrape; returns `(books, errors)` |

Requires `DATABASE_URL` pointing to a running PostgreSQL instance (e.g. via Docker).

### Request flow

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
   ├── SqliteRepository (SQLite via stdlib sqlite3)   ← default
   └── InMemoryRepository (in-memory dict fallback)
  │
  ▼
 PostgreSQL (db service, pgdata volume)
```

### Architecture

```
app/
    main.py                 # FastAPI app, router mounting, Redis ping, lifespan
    database.py             # asyncpg connection pool from .env
    models/
        task.py             # Pydantic schemas
    services/
        task_service.py     # Business logic — delegates to SQLite or Postgres repo
    repositories/
        postgres_repo.py    # Postgres repository (asyncpg)
        sqlite_repo.py      # SQLite repository (stdlib sqlite3) — default
        inmemory_repo.py    # In-memory fallback (still conforms to protocol)
        protocol.py         # TaskRepository Protocol
    routers/
        tasks.py            # HTTP endpoints (async)
db/
    init.sql                # Table DDL + index
scripts/
    seed_explain.py         # EXPLAIN ANALYZE before/after index
```

### Stack

| Component | Technology            |
|-----------|-----------------------|
| API       | FastAPI + uvicorn     |
| Database  | PostgreSQL 16 (Docker)|
| Cache     | Redis 7 (Docker)      |
| DB Driver | asyncpg               |
| Config    | .env (gitignored)     |

### Key design note — Repository Swap

The repository implementation was swapped from in-memory to Postgres without changing the rest of the stack.

A `TaskRepository` Protocol (`app/repositories/protocol.py`) defines the contract:

| Method          | Signature                                      |
|-----------------|------------------------------------------------|
| `create_task`   | `(task_data: TaskCreate) -> TaskResponse`      |
| `get_all_tasks` | `() -> list[TaskResponse]`                     |
| `get_task`      | `(task_id: int) -> Optional[TaskResponse]`     |
| `update_task`   | `(task_id: int, task_data: TaskUpdate) -> Optional[TaskResponse]` |
| `delete_task`   | `(task_id: int) -> bool`                       |

Both `PostgresRepository` and `InMemoryRepository` conform to this interface.

The `task_service.py` module selects the repository at import time:
- If `DATABASE_URL` is set → `PostgresRepository`
- Otherwise → `SqliteRepository`

Only the repository implementation changed:
- **Service contract** stayed the same.
- **Routes contract** stayed the same.
- **API behavior** stayed the same.

### Persistence proof

To verify data survives restarts:

```bash
# 1. Start the stack
docker compose up --build

# 2. Create a task
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "persistent task", "done": false}'

# 3. Note the returned ID (e.g. 1)

# 4. Stop everything
docker compose down

# 5. Start again
docker compose up

# 6. Fetch the task — it still exists
curl http://localhost:8000/tasks/1
# → {"id":1,"title":"persistent task","done":false,...}
```

The volume `pgdata` in `docker-compose.yml` ensures Postgres data persists across container restarts.

### Redis connectivity (Stretch Goal)

Redis was added as the optional Stretch Goal. It runs as a `redis:7-alpine` service in `docker-compose.yml` with a health check.

Verification:
- On startup, the app pings Redis (`PONG`) and logs the result.
- The `/health` and `/` endpoints include `"redis": "connected"` when the connection is alive.
- The app continues to function normally if Redis is unavailable — it only reports the status.

### EXPLAIN ANALYZE — index performance

Run the seed script against the running stack:

```bash
# Ensure the stack is up, then:
pip install -r requirements.txt
python scripts/seed_explain.py --rows 10000
```

Example output (actual values will vary):

```
=== BEFORE INDEX ===
Seq Scan on tasks  (cost=0.00..180.00 rows=5000 width=68)
  Filter: (done = true)
  Planning Time: 0.123 ms
  Execution Time: 15.234 ms

=== AFTER INDEX ===
Bitmap Heap Scan on tasks  (cost=4.52..125.34 rows=5000 width=68)
  Recheck Cond: (done = true)
  ->  Bitmap Index Scan on idx_tasks_done  (cost=0.00..4.52 rows=5000 width=0)
        Index Cond: (done = true)
  Planning Time: 0.234 ms
  Execution Time: 2.456 ms
```

The index on `tasks(done)` replaces a sequential scan with a bitmap index scan, reducing execution time significantly on a 10,000-row table.

### Assignment W3 A2 requirements checklist

- [x] Same 5 CRUD endpoints as A1 — `GET /tasks`, `GET /tasks/:id`, `POST /tasks`, `PUT /tasks/:id`, `DELETE /tasks/:id`
- [x] Tasks stored in SQLite (`tasks.db`), not in memory
- [x] Data survives server restart (verified via API + DB Browser)
- [x] `tasks.db` created automatically if missing
- [x] `tasks` table created automatically if missing
- [x] 3 example tasks seeded only on first run — no duplication on restart
- [x] All queries use `?` parameterized placeholders (no string-glued SQL)
- [x] Correct status codes: 200 / 201 / 204 / 400 / 404 with JSON error messages
- [x] Public GitHub repo with ≥6 commits

**Extras (stretch):**
- [x] Search with SQL — `GET /tasks?search=milk` via `WHERE title LIKE ?`
- [x] Filter by status — `GET /tasks?done=true` via `WHERE done = ?`
- [x] Sort alphabetically — `ORDER BY title`
- [x] Real statistics — `GET /stats` computed via `SELECT COUNT(*)`
- [x] Timestamps — `created_at` / `updated_at` columns set on insert/update
- [x] Index on `tasks(done)` with `EXPLAIN ANALYZE` before/after
- [x] Transactions — seeding wrapped in `commit()` for all-or-nothing
- [ ] AI rematch (Stage 6 bonus) — `ai-version/` folder with AI-generated code + "AI vs me" section

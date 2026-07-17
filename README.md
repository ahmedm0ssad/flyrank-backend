# FlyRank Backend AI Engineering

## Assignment BE-02 — Task CRUD API

### Run

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Endpoints

| Method | Path           | Description        |
|--------|----------------|--------------------|
| GET    | `/`            | Welcome message    |
| GET    | `/health`      | Health check       |
| GET    | `/tasks`       | List all tasks     |
| GET    | `/tasks/{id}`  | Get a task by ID   |
| POST   | `/tasks`       | Create a task      |
| PUT    | `/tasks/{id}`  | Update a task      |
| DELETE | `/tasks/{id}`  | Delete a task      |

Swagger docs at `/docs`.

### Architecture

```
app/
    main.py              # FastAPI app, router mounting
    models/
        task.py          # Pydantic schemas
    services/
        task_service.py  # Business logic (in-memory)
    routers/
        tasks.py         # HTTP endpoints
```

### Future evolution

- **PostgreSQL**: Add `repositories/`, inject into service layer
- **Tests**: `pytest` + `TestClient`, services are pure functions
- **Docker**: Multi-stage build, layered architecture maps naturally
- **Auth**: FastAPI dependencies on routers

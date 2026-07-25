# FlyRank — Build Your First CRUD API

A minimal FastAPI-based task management API using in-memory storage. No database required — data lives in memory for the lifetime of the process.

## Assignment Goal

Build a RESTful CRUD API for managing tasks with FastAPI, demonstrating route setup, request validation, and error handling.

## Features

- Full CRUD for tasks (create, read, update, delete)
- In-memory storage with seed data on startup
- Request validation via Pydantic schemas
- Consistent error responses (400 for validation, 404 for missing resources)
- Health check endpoint

## Technologies Used

| Component  | Technology     |
|------------|----------------|
| Framework  | FastAPI        |
| Server     | Uvicorn        |
| Validation | Pydantic       |
| Storage    | In-memory dict |

## Requirements

- Python 3.10+
- pip

## Installation

```bash
pip install -r requirements.txt
```

## Running Locally

```bash
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Interactive Swagger docs at `http://localhost:8000/docs`.

## API Endpoints

| Method | Path          | Description        | Status Codes              |
|--------|---------------|--------------------|---------------------------|
| GET    | `/`           | Welcome message    | 200                       |
| GET    | `/health`     | Health check       | 200                       |
| GET    | `/tasks`      | List all tasks     | 200                       |
| GET    | `/tasks/{id}` | Get a task by ID   | 200, 404                  |
| POST   | `/tasks`      | Create a task      | 201                       |
| PUT    | `/tasks/{id}` | Update a task      | 200, 404                  |
| DELETE | `/tasks/{id}` | Delete a task      | 204, 404                  |

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

# Update a task
curl -X PUT http://localhost:8000/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "Updated task", "done": true}'

# Delete a task
curl -X DELETE http://localhost:8000/tasks/1
```

## Project Structure

```
app/
    main.py              # FastAPI app, router mounting, error handlers
    models/
        task.py          # Pydantic schemas (TaskCreate, TaskUpdate, TaskResponse)
    services/
        task_service.py  # Business logic with in-memory dict storage
    routers/
        tasks.py         # HTTP endpoints for /tasks
```

## Known Limitations

- Data is lost when the server stops (in-memory storage)
- No persistent database
- No authentication
- No Docker containerization

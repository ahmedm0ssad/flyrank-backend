import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.sqlite_repo import SqliteRepository
from app.services import task_service


@pytest.fixture
def _temp_sqlite_repo():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    repo = SqliteRepository(db_path=tmp.name)
    original = task_service._repo
    task_service._repo = repo
    yield
    task_service._repo = original
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def client(_temp_sqlite_repo):
    return TestClient(app)


class TestE2ESqlite:
    def test_full_crud_cycle(self, client):
        # GET /tasks/ — 3 seeded tasks, alphabetical by title
        resp = client.get("/tasks/")
        assert resp.status_code == 200
        tasks = resp.json()
        assert len(tasks) == 3
        titles = [t["title"] for t in tasks]
        assert titles == sorted(titles)
        assert tasks[0]["title"] == "Build a project"

        # POST /tasks/ — create a new task
        resp = client.post("/tasks/", json={"title": "E2E test task", "done": True})
        assert resp.status_code == 201
        created = resp.json()
        assert created["title"] == "E2E test task"
        assert created["done"] is True
        assert isinstance(created["id"], int)
        assert created["id"] == 4
        task_id = created["id"]

        # GET /tasks/ — count is now 4
        resp = client.get("/tasks/")
        assert resp.status_code == 200
        assert len(resp.json()) == 4

        # GET /tasks/{id} — fetch the just-created task
        resp = client.get(f"/tasks/{task_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "E2E test task"
        assert body["id"] == task_id
        assert body["done"] is True

        # PUT /tasks/{id} — update title and done
        resp = client.put(
            f"/tasks/{task_id}",
            json={"title": "Updated E2E", "done": False},
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["title"] == "Updated E2E"
        assert updated["done"] is False
        assert updated["id"] == task_id
        assert updated["updated_at"] > created["updated_at"]
        assert updated["created_at"] == created["created_at"]

        # DELETE /tasks/{id}
        resp = client.delete(f"/tasks/{task_id}")
        assert resp.status_code == 204

        # GET /tasks/{id} — confirm 404 after deletion
        resp = client.get(f"/tasks/{task_id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["error"].lower()

        # GET /stats — final count reflects deletion
        resp = client.get("/stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert stats["total"] == 3
        assert stats["done"] == 0
        assert stats["not_done"] == 3

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.models.task import TaskResponse


def _make_response(id: int, title: str, done: bool = False):
    now = datetime.now(timezone.utc)
    return TaskResponse(id=id, title=title, done=done, created_at=now, updated_at=now)


@pytest.fixture(autouse=True)
def mock_task_service(monkeypatch):
    mock = AsyncMock()
    monkeypatch.setattr("app.routers.tasks.task_service", mock)
    return mock


class TestListTasks:
    def test_list_tasks_returns_list(self, client: TestClient, mock_task_service):
        mock_task_service.get_all_tasks.return_value = [
            _make_response(1, "Task 1"),
            _make_response(2, "Task 2"),
        ]

        response = client.get("/tasks/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Task 1"
        assert data[1]["title"] == "Task 2"

    def test_list_tasks_empty(self, client: TestClient, mock_task_service):
        mock_task_service.get_all_tasks.return_value = []

        response = client.get("/tasks/")

        assert response.status_code == 200
        assert response.json() == []


class TestGetTask:
    def test_get_task_found(self, client: TestClient, mock_task_service):
        mock_task_service.get_task.return_value = _make_response(1, "Found Task")

        response = client.get("/tasks/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["title"] == "Found Task"

    def test_get_task_not_found(self, client: TestClient, mock_task_service):
        mock_task_service.get_task.return_value = None

        response = client.get("/tasks/999")

        assert response.status_code == 404
        assert response.json() == {"detail": "Task 999 not found"}

    def test_get_task_invalid_id(self, client: TestClient):
        response = client.get("/tasks/abc")
        assert response.status_code == 422


class TestCreateTask:
    def test_create_task_returns_201(self, client: TestClient, mock_task_service):
        async def side_effect(task_data):
            return _make_response(1, task_data.title, task_data.done)

        mock_task_service.create_task.side_effect = side_effect

        response = client.post("/tasks/", json={"title": "New Task", "done": True})

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Task"
        assert data["done"] is True

    def test_create_task_empty_title(self, client: TestClient):
        response = client.post("/tasks/", json={"title": "", "done": False})
        assert response.status_code == 422

    def test_create_task_missing_title(self, client: TestClient):
        response = client.post("/tasks/", json={"done": False})
        assert response.status_code == 422

    def test_create_task_default_done(self, client: TestClient, mock_task_service):
        async def side_effect(task_data):
            return _make_response(1, task_data.title, task_data.done)

        mock_task_service.create_task.side_effect = side_effect

        response = client.post("/tasks/", json={"title": "Task"})

        assert response.status_code == 201
        data = response.json()
        assert data["done"] is False


class TestUpdateTask:
    def test_update_task_found(self, client: TestClient, mock_task_service):
        mock_task_service.update_task.return_value = _make_response(
            1, "Updated", done=True
        )

        response = client.put("/tasks/1", json={"title": "Updated", "done": True})

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated"
        assert data["done"] is True

    def test_update_task_not_found(self, client: TestClient, mock_task_service):
        mock_task_service.update_task.return_value = None

        response = client.put("/tasks/999", json={"title": "Nope", "done": False})

        assert response.status_code == 404
        assert "999" in response.json()["detail"]

    def test_update_task_invalid_data(self, client: TestClient):
        response = client.put("/tasks/1", json={"title": "", "done": False})
        assert response.status_code == 422

    def test_update_task_missing_done_returns_422(self, client: TestClient):
        response = client.put("/tasks/1", json={"title": "No done"})
        assert response.status_code == 422


class TestGetStats:
    def test_stats_returns_shape(self, client, mock_task_service):
        mock_task_service.get_stats.return_value = {
            "total": 5,
            "done": 2,
            "not_done": 3,
        }
        response = client.get("/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert data["done"] == 2
        assert data["not_done"] == 3


class TestDeleteTask:
    def test_delete_task_found(self, client: TestClient, mock_task_service):
        mock_task_service.delete_task.return_value = True

        response = client.delete("/tasks/1")

        assert response.status_code == 204
        assert response.content == b""

    def test_delete_task_not_found(self, client: TestClient, mock_task_service):
        mock_task_service.delete_task.return_value = False

        response = client.delete("/tasks/999")

        assert response.status_code == 404
        assert "999" in response.json()["detail"]

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient


class TestHomeEndpoint:
    def test_home_returns_info(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Task API"
        assert data["version"] == "1.0"
        assert "/tasks" in data["endpoints"]
        assert "/scrape" in data["endpoints"]
        assert "redis" not in data

    def test_home_with_redis_connected(self, client: TestClient, monkeypatch):
        fake_redis = object()
        monkeypatch.setattr("app.main.get_redis", lambda: fake_redis)

        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["redis"] == "connected"


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "redis" not in data

    def test_health_with_redis_connected(self, client: TestClient, monkeypatch):
        fake_redis = object()
        monkeypatch.setattr("app.main.get_redis", lambda: fake_redis)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["redis"] == "connected"


class TestValidationErrorHandler:
    def test_validation_error_returns_400(self, client: TestClient):
        response = client.post("/tasks/", json={"title": "", "done": False})
        assert response.status_code == 400
        assert "error" in response.json()

    def test_validation_error_message(self, client: TestClient):
        response = client.post("/tasks/", json={})
        assert response.status_code == 400
        data = response.json()
        assert isinstance(data["error"], str)
        assert len(data["error"]) > 0


class TestHTTPExceptionHandler:
    def test_http_exception_returns_proper_status(
        self, client: TestClient, monkeypatch
    ):
        mock_service = AsyncMock()
        mock_service.get_task.return_value = None
        monkeypatch.setattr("app.routers.tasks.task_service", mock_service)

        response = client.get("/tasks/999")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert "999" in data["error"]

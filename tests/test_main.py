from unittest.mock import AsyncMock

from fastapi.testclient import TestClient


class TestHomeEndpoint:
    def test_home_not_found(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 404


class TestHealthEndpoint:
    def test_health_not_found(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 404


class TestValidationErrorHandler:
    def test_validation_error_returns_422(self, client: TestClient):
        response = client.post("/tasks/", json={"title": "", "done": False})
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_validation_error_message(self, client: TestClient):
        response = client.post("/tasks/", json={})
        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) > 0


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
        assert "detail" in data
        assert "999" in data["detail"]

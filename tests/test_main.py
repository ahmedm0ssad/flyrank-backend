from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestLifespan:
    def test_lifespan_missing_supabase_raises(self, monkeypatch):
        import asyncio
        from unittest.mock import MagicMock

        monkeypatch.setattr("app.main.get_client_credentials", lambda: ("", ""))
        from app.main import lifespan

        app = MagicMock()

        async def run_lifespan():
            async with lifespan(app):
                pass

        with pytest.raises(RuntimeError, match="Missing Supabase credentials"):
            asyncio.run(run_lifespan())

    def test_lifespan_supabase_configured(self, monkeypatch):
        monkeypatch.setattr("app.main.get_client_credentials", lambda: ("https://test.supabase.co", "test-key"))
        monkeypatch.setattr("app.main.is_postgres_enabled", lambda: False)
        monkeypatch.setenv("REDIS_URL", "")

        from app.main import lifespan
        import asyncio

        app = MagicMock()
        async def run_lifespan():
            async with lifespan(app):
                pass
        asyncio.run(run_lifespan())

    def test_lifespan_redis_connection_success(self, monkeypatch):
        monkeypatch.setattr("app.main.get_client_credentials", lambda: ("https://test.supabase.co", "test-key"))
        monkeypatch.setattr("app.main.is_postgres_enabled", lambda: False)

        fake_redis = AsyncMock()
        fake_redis.ping = AsyncMock(return_value="PONG")
        fake_redis.close = AsyncMock()

        monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: fake_redis)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        from app.main import lifespan
        import asyncio

        app = MagicMock()
        async def run_lifespan():
            async with lifespan(app):
                pass
        asyncio.run(run_lifespan())

        fake_redis.ping.assert_awaited_once()
        fake_redis.close.assert_awaited_once()

    def test_lifespan_redis_connection_failure(self, monkeypatch):
        import redis
        monkeypatch.setattr("app.main.get_client_credentials", lambda: ("https://test.supabase.co", "test-key"))
        monkeypatch.setattr("app.main.is_postgres_enabled", lambda: False)

        fake_redis = AsyncMock()
        fake_redis.ping = AsyncMock(side_effect=redis.RedisError("Connection refused"))
        fake_redis.close = AsyncMock()

        monkeypatch.setattr("redis.asyncio.from_url", lambda *a, **kw: fake_redis)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        from app.main import lifespan
        import asyncio

        app = MagicMock()
        async def run_lifespan():
            async with lifespan(app):
                pass
        asyncio.run(run_lifespan())

        fake_redis.ping.assert_awaited_once()
        fake_redis.close.assert_not_called()

    def test_lifespan_postgres_enabled(self, monkeypatch):
        monkeypatch.setattr("app.main.get_client_credentials", lambda: ("https://test.supabase.co", "test-key"))
        monkeypatch.setattr("app.main.is_postgres_enabled", lambda: True)
        monkeypatch.setenv("REDIS_URL", "")

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        
        async def mock_acquire():
            return mock_conn
            
        mock_pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock(return_value=None)))

        with patch("app.main.get_pool", return_value=mock_pool):
            from app.main import lifespan
            import asyncio

            app = MagicMock()
            async def run_lifespan():
                async with lifespan(app):
                    pass
            asyncio.run(run_lifespan())

        mock_pool.acquire.assert_called_once()
        mock_conn.execute.assert_awaited_once_with("SELECT 1")


class TestPublicInfoEndpoint:
    def test_public_info_returns_message(self, client: TestClient):
        response = client.get("/public/info")
        assert response.status_code == 200
        assert response.json() == {"message": "Welcome stranger! This info is public."}


class TestHomeEndpoint:
    def test_home_returns_info(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "FlyRank API"
        assert data["version"] == "0.3.0"

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

    def test_health_with_redis_connected(self, client: TestClient, monkeypatch):
        fake_redis = object()
        monkeypatch.setattr("app.main.get_redis", lambda: fake_redis)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["redis"] == "connected"

    def test_health_with_postgres_connected(self, client: TestClient, monkeypatch):
        monkeypatch.setattr("app.core.database.DATABASE_URL", "postgresql://test:test@localhost/test")
        monkeypatch.setattr("app.main.is_postgres_enabled", lambda: True)

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()

        mock_pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock(return_value=None)))

        async def mock_get_pool():
            return mock_pool

        monkeypatch.setattr("app.core.database.get_pool", mock_get_pool)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["postgres"] == "connected"
        assert data["status"] == "ok"

    def test_health_with_postgres_unavailable(self, client: TestClient, monkeypatch):
        monkeypatch.setattr("app.core.database.DATABASE_URL", "postgresql://test:test@localhost/test")
        monkeypatch.setattr("app.main.is_postgres_enabled", lambda: True)

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("Connection failed"))

        mock_pool.acquire = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock(return_value=None)))

        async def mock_get_pool():
            return mock_pool

        monkeypatch.setattr("app.core.database.get_pool", mock_get_pool)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["postgres"] == "unavailable"
        assert data["status"] == "degraded"

    def test_health_with_sqlite(self, client: TestClient, monkeypatch):
        monkeypatch.setattr("app.main.is_postgres_enabled", lambda: False)

        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["database"] == "sqlite"
        assert data["status"] == "ok"


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

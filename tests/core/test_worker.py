from unittest.mock import AsyncMock, MagicMock, patch
import sys

import pytest


class TestRunWorker:
    def test_run_worker_redis_connection_success(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        monkeypatch.setattr("redis.from_url", lambda *a, **kw: mock_redis)

        mock_worker_class = MagicMock()
        mock_worker = MagicMock()
        mock_worker_class.return_value = mock_worker
        monkeypatch.setattr("app.core.worker.SimpleWorker", mock_worker_class)

        from app.core.worker import run_worker

        with patch("sys.exit") as mock_exit:
            run_worker()
            mock_exit.assert_not_called()

        mock_worker.work.assert_called_once()

    def test_run_worker_redis_connection_failure(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        import redis
        monkeypatch.setattr("redis.from_url", lambda *a, **kw: (_ for _ in ()).throw(redis.RedisError("Connection refused")))

        from app.core.worker import run_worker

        with patch("sys.exit") as mock_exit:
            run_worker()
            mock_exit.assert_called_once_with(1)

    def test_run_worker_uses_simple_worker_on_windows(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        monkeypatch.setattr("redis.from_url", lambda *a, **kw: mock_redis)

        mock_simple_worker = MagicMock()
        mock_regular_worker = MagicMock()

        monkeypatch.setattr("app.core.worker.SimpleWorker", mock_simple_worker)
        monkeypatch.setattr("app.core.worker.Worker", mock_regular_worker)
        monkeypatch.setattr("os.name", "nt")

        from app.core.worker import run_worker

        with patch("sys.exit"):
            run_worker()

        mock_simple_worker.assert_called_once()
        mock_regular_worker.assert_not_called()

    def test_run_worker_uses_regular_worker_on_linux(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        monkeypatch.setattr("redis.from_url", lambda *a, **kw: mock_redis)

        mock_simple_worker = MagicMock()
        mock_regular_worker = MagicMock()

        monkeypatch.setattr("app.core.worker.SimpleWorker", mock_simple_worker)
        monkeypatch.setattr("app.core.worker.Worker", mock_regular_worker)
        monkeypatch.setattr("os.name", "posix")

        from app.core.worker import run_worker

        with patch("sys.exit"):
            run_worker()

        mock_regular_worker.assert_called_once()
        mock_simple_worker.assert_not_called()


class TestMainBlock:
    def test_run_worker_exists_and_callable(self):
        from app.core.worker import run_worker

        assert callable(run_worker)

    def test_imports_enrichment_queue_name(self):
        from app.core.worker import ENRICHMENT_QUEUE_NAME

        assert ENRICHMENT_QUEUE_NAME == "enrichment-jobs"
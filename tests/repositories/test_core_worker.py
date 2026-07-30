"""Tests for app.core.worker.

Lines 34-35 (Redis connection success) and 41-46 (worker creation +
worker.work) tested here with mocked redis and worker classes.

Line 50 (if __name__ == "__main__") is a standard guard — not tested.
"""

from unittest.mock import MagicMock

import pytest


class TestRunWorker:
    def test_redis_connection_success_and_worker_starts(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["worker.py"])

        fake_conn = MagicMock()
        fake_worker = MagicMock()
        monkeypatch.setattr("redis.from_url", lambda url, **kw: fake_conn)
        monkeypatch.setattr(
            "app.core.worker.SimpleWorker", lambda q, connection: fake_worker
        )

        from app.core.worker import run_worker

        run_worker()
        fake_conn.ping.assert_called_once()
        fake_worker.work.assert_called_once()

    def test_redis_connection_failure_exits(self, monkeypatch):
        import redis

        monkeypatch.setattr("sys.argv", ["worker.py"])

        fake_conn = MagicMock()
        fake_conn.ping.side_effect = redis.RedisError("Connection refused")
        monkeypatch.setattr("redis.from_url", lambda url, **kw: fake_conn)

        from app.core.worker import run_worker

        with pytest.raises(SystemExit) as exc:
            run_worker()
        assert exc.value.code == 1

"""Tests for app.core.queue.

The autouse _reset_queue fixture monkeypatches get_connection,
get_queue, get_report_queue, get_enrichment_queue to return fakes, so
update_report_job and list_jobs can be tested against the fake Redis.
Lazy-init singletons are tested via importlib.reload to undo the
fixture's patches.
"""

import importlib
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.conftest import _fake_redis


class TestUpdateReportJob:
    def test_update_report_job_sets_status(self):
        _fake_redis._data.clear()
        from app.core.queue import update_report_job

        update_report_job("rj-1", "finished")
        data = _fake_redis._data.get("report_job:rj-1", {})
        assert data["status"] == "finished"

    def test_update_report_job_with_extra(self):
        _fake_redis._data.clear()
        from app.core.queue import update_report_job

        update_report_job("rj-2", "failed", error="something broke")
        data = _fake_redis._data.get("report_job:rj-2", {})
        assert data["status"] == "failed"
        assert data["error"] == "something broke"


class TestListJobs:
    def test_list_jobs_returns_empty_when_no_jobs(self):
        _fake_redis._data.clear()
        from app.core.queue import list_jobs

        assert list_jobs() == []

    def test_list_jobs_returns_matching_jobs(self):
        _fake_redis._data.clear()
        now = datetime.now(timezone.utc).isoformat()
        _fake_redis.hset(
            "job:j1",
            mapping={
                "status": "queued",
                "created_at": now,
                "updated_at": now,
                "attempts": "0",
            },
        )
        from app.core.queue import list_jobs

        jobs = list_jobs()
        assert len(jobs) == 1
        assert jobs[0].job_id == "j1"

    def test_list_jobs_handles_bytes_keys(self, monkeypatch):
        _fake_redis._data.clear()
        now = datetime.now(timezone.utc).isoformat()
        _fake_redis.hset(
            "job:b1",
            mapping={
                "status": "queued",
                "created_at": now,
                "updated_at": now,
                "attempts": "0",
            },
        )
        original_scan = _fake_redis.scan

        def bytes_scan(cursor=0, match=None, count=10):
            _, keys = original_scan(cursor, match, count)
            return cursor, [k.encode() for k in keys]

        _fake_redis.scan = bytes_scan
        from app.core.queue import list_jobs

        jobs = list_jobs()
        assert len(jobs) == 1
        assert jobs[0].job_id == "b1"


class TestLazyInitSingletons:
    def test_get_connection_lazy_init(self, monkeypatch):
        import app.core.queue as qm

        importlib.reload(qm)

        fake_redis = MagicMock()
        with patch("redis.from_url", return_value=fake_redis):
            from app.core.queue import get_connection

            conn = get_connection()
            assert conn is fake_redis

    def test_get_queue_lazy_init(self, monkeypatch):
        import app.core.queue as qm

        importlib.reload(qm)

        fake_redis = MagicMock()
        fake_queue = MagicMock()
        with (
            patch("redis.from_url", return_value=fake_redis),
            patch("app.core.queue.Queue", return_value=fake_queue),
        ):
            from app.core.queue import get_queue

            q = get_queue()
            assert q is fake_queue

    def test_get_report_queue_lazy_init(self, monkeypatch):
        import app.core.queue as qm

        importlib.reload(qm)

        fake_redis = MagicMock()
        fake_queue = MagicMock()
        with (
            patch("redis.from_url", return_value=fake_redis),
            patch("app.core.queue.Queue", return_value=fake_queue),
        ):
            from app.core.queue import get_report_queue

            q = get_report_queue()
            assert q is fake_queue

    def test_get_enrichment_queue_lazy_init(self, monkeypatch):
        import app.core.queue as qm

        importlib.reload(qm)

        fake_redis = MagicMock()
        fake_queue = MagicMock()
        with (
            patch("redis.from_url", return_value=fake_redis),
            patch("app.core.queue.Queue", return_value=fake_queue),
        ):
            from app.core.queue import get_enrichment_queue

            q = get_enrichment_queue()
            assert q is fake_queue


class TestConnections:
    def test_reset_connection_closes_and_clears(self, monkeypatch):
        fake_conn = MagicMock()
        monkeypatch.setattr("app.core.queue._connection", fake_conn)
        monkeypatch.setattr("app.core.queue._queue", MagicMock())
        monkeypatch.setattr("app.core.queue._report_queue", MagicMock())
        monkeypatch.setattr("app.core.queue._enrichment_queue", MagicMock())

        from app.core.queue import reset_connection

        reset_connection()
        fake_conn.close.assert_called_once()

    def test_reset_connection_noop_when_none(self, monkeypatch):
        monkeypatch.setattr("app.core.queue._connection", None)

        from app.core.queue import reset_connection

        reset_connection()

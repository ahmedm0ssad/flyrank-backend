from unittest.mock import MagicMock, patch

from app.core import queue
from app.models.job import JobStatus


class TestCreateJob:
    def test_creates_job_with_idempotency_key(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.get.return_value = None
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        mock_queue = MagicMock()
        monkeypatch.setattr(queue, "get_queue", lambda: mock_queue)

        job_id, status = queue.create_job(
            {"prompt": "test"}, idempotency_key="idem-key"
        )

        assert job_id is not None
        assert status == JobStatus.QUEUED
        mock_conn.hset.assert_called_once()
        mock_conn.expire.assert_called_once()
        mock_queue.enqueue.assert_called_once()

    def test_returns_existing_job_for_idempotency_key(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.get.return_value = "existing-job-id"
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        job_id, status = queue.create_job(
            {"prompt": "test"}, idempotency_key="idem-key"
        )

        assert job_id == "existing-job-id"
        assert status == JobStatus.QUEUED
        mock_conn.hset.assert_not_called()
        mock_conn.expire.assert_not_called()

    def test_creates_job_without_idempotency_key(self, monkeypatch):
        mock_conn = MagicMock()
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        mock_queue = MagicMock()
        monkeypatch.setattr(queue, "get_queue", lambda: mock_queue)

        job_id, status = queue.create_job({"prompt": "test"})

        assert job_id is not None
        assert status == JobStatus.QUEUED


class TestGetJob:
    def test_returns_job_when_exists(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.hgetall.return_value = {
            "status": JobStatus.FINISHED.value,
            "result": "success",
            "error": None,
            "created_at": "2024-01-01T00:00:00",
            "started_at": "2024-01-01T00:00:01",
            "finished_at": "2024-01-01T00:00:02",
            "attempts": "1",
        }
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        job = queue.get_job("test-job-id")

        assert job is not None
        assert job.job_id == "test-job-id"
        assert job.status == JobStatus.FINISHED
        assert job.result == "success"

    def test_returns_none_when_not_exists(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.hgetall.return_value = {}
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        job = queue.get_job("nonexistent")

        assert job is None


class TestUpdateJob:
    def test_updates_job_status(self, monkeypatch):
        mock_conn = MagicMock()
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        queue.update_job("test-job-id", JobStatus.STARTED.value, result="done")

        mock_conn.hset.assert_called_once()
        mock_conn.expire.assert_called_once()


class TestListJobs:
    def test_lists_jobs(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.scan.side_effect = [
            (0, [b"job:job1", b"job:job2"]),
        ]
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        with patch("app.core.queue.get_job") as mock_get_job:
            mock_get_job.side_effect = [
                MagicMock(job_id="job1"),
                MagicMock(job_id="job2"),
            ]

            jobs = queue.list_jobs(limit=10, offset=0)

            assert len(jobs) == 2


class TestCreateReportJob:
    def test_creates_report_job(self, monkeypatch):
        mock_conn = MagicMock()
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        mock_queue = MagicMock()
        monkeypatch.setattr(queue, "get_report_queue", lambda: mock_queue)

        job_id, status = queue.create_report_job()

        assert job_id is not None
        assert status == JobStatus.QUEUED
        mock_conn.hset.assert_called_once()
        mock_conn.expire.assert_called_once()
        mock_queue.enqueue.assert_called_once()


class TestUpdateReportJob:
    def test_updates_report_job(self, monkeypatch):
        mock_conn = MagicMock()
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        queue.update_report_job(
            "report-job-id", JobStatus.FINISHED.value, result="report.pdf"
        )

        mock_conn.hset.assert_called_once()
        mock_conn.expire.assert_called_once()


class TestCreateEnrichmentJob:
    def test_creates_enrichment_job(self, monkeypatch):
        mock_conn = MagicMock()
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        mock_queue = MagicMock()
        monkeypatch.setattr(queue, "get_enrichment_queue", lambda: mock_queue)

        job_id = queue.create_enrichment_job("lead-123")

        assert job_id is not None
        mock_conn.hset.assert_called_once()
        mock_conn.expire.assert_called_once()
        mock_queue.enqueue.assert_called_once()


class TestGetEnrichmentJob:
    def test_returns_enrichment_job(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.hgetall.return_value = {
            "status": JobStatus.QUEUED.value,
            "result": None,
            "error": None,
            "created_at": "2024-01-01T00:00:00",
            "started_at": None,
            "finished_at": None,
            "attempts": "0",
        }
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        job = queue.get_enrichment_job("enrich-job-id")

        assert job is not None
        assert job.job_id == "enrich-job-id"
        assert job.status == JobStatus.QUEUED

    def test_returns_none_when_not_exists(self, monkeypatch):
        mock_conn = MagicMock()
        mock_conn.hgetall.return_value = {}
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        job = queue.get_enrichment_job("nonexistent")

        assert job is None


class TestUpdateEnrichmentJob:
    def test_updates_enrichment_job(self, monkeypatch):
        mock_conn = MagicMock()
        monkeypatch.setattr(queue, "get_connection", lambda: mock_conn)

        queue.update_enrichment_job(
            "enrich-job-id", JobStatus.FINISHED.value, result="enriched"
        )

        mock_conn.hset.assert_called_once()
        mock_conn.expire.assert_called_once()


class TestModuleImports:
    def test_constants_defined(self):
        assert queue.REDIS_URL is not None
        assert queue.IDEMPOTENCY_TTL == 86400
        assert queue.JOB_TTL == 86400
        assert queue.QUEUE_NAME == "ai-jobs"
        assert queue.REPORT_QUEUE_NAME == "report-jobs"
        assert queue.ENRICHMENT_QUEUE_NAME == "enrichment-jobs"

import asyncio
from unittest.mock import MagicMock

import pytest

from app.models.report import ReportStatus


class TestRunReportJob:
    def test_successful_execution(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-report-1"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr(
            "app.services.report_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_report_data_for_worker",
            lambda j: {
                "total": 10,
                "done": 5,
                "not_done": 5,
                "completion_pct": 50.0,
                "recent_tasks": [],
            },
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_scraped_books_stats", lambda: None
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_ai_jobs_stats", lambda: None
        )
        monkeypatch.setattr(
            "app.services.report_worker.generate_report",
            lambda j, s, b, a: f"/path/to/report_{j}.pdf",
        )
        monkeypatch.setattr("app.services.report_worker.update_report_job", MagicMock())
        monkeypatch.setattr(
            "app.services.report_worker.update_report_status",
            lambda *a, **kw: asyncio.sleep(0),
        )

        from app.services.report_worker import run_report_job

        result = run_report_job({"job_id": "test-report-1"})
        assert result == "/path/to/report_test-report-1.pdf"

    def test_job_started_status_set(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-report-2"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr(
            "app.services.report_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_report_data_for_worker",
            lambda j: {
                "total": 10,
                "done": 5,
                "not_done": 5,
                "completion_pct": 50.0,
                "recent_tasks": [],
            },
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_scraped_books_stats", lambda: None
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_ai_jobs_stats", lambda: None
        )
        monkeypatch.setattr(
            "app.services.report_worker.generate_report",
            lambda j, s, b, a: "/path/to/report.pdf",
        )

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status, **extra})

        monkeypatch.setattr("app.services.report_worker.update_report_job", fake_update)
        monkeypatch.setattr(
            "app.services.report_worker.update_report_status",
            lambda *a, **kw: asyncio.sleep(0),
        )

        from app.services.report_worker import run_report_job

        run_report_job({"job_id": "test-report-2"})
        assert any(u["status"] == ReportStatus.STARTED.value for u in updates)

    def test_job_completed_status_set(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-report-3"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr(
            "app.services.report_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_report_data_for_worker",
            lambda j: {
                "total": 10,
                "done": 5,
                "not_done": 5,
                "completion_pct": 50.0,
                "recent_tasks": [],
            },
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_scraped_books_stats", lambda: None
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_ai_jobs_stats", lambda: None
        )
        monkeypatch.setattr(
            "app.services.report_worker.generate_report",
            lambda j, s, b, a: "/path/to/report.pdf",
        )

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status, **extra})

        monkeypatch.setattr("app.services.report_worker.update_report_job", fake_update)
        monkeypatch.setattr(
            "app.services.report_worker.update_report_status",
            lambda *a, **kw: asyncio.sleep(0),
        )

        from app.services.report_worker import run_report_job

        run_report_job({"job_id": "test-report-3"})
        assert any(u["status"] == ReportStatus.FINISHED.value for u in updates)

    def test_job_failure_during_execution(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-report-4"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 1

        monkeypatch.setattr(
            "app.services.report_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_report_data_for_worker",
            lambda j: (_ for _ in ()).throw(ValueError("DB failure")),
        )
        monkeypatch.setattr("app.services.report_worker.update_report_job", MagicMock())
        monkeypatch.setattr(
            "app.services.report_worker.update_report_status",
            lambda *a, **kw: asyncio.sleep(0),
        )
        monkeypatch.setattr("app.services.report_worker.send_alert", MagicMock())
        monkeypatch.setattr("app.services.report_worker.logger", MagicMock())

        from app.services.report_worker import run_report_job

        with pytest.raises(ValueError, match="DB failure"):
            run_report_job({"job_id": "test-report-4"})

    def test_job_failure_sets_failed_status_after_retries_exhausted(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-report-5"
        mock_job.meta = {"max_retries": 3, "current_attempt": 3}
        mock_job.retries_left = 0
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr(
            "app.services.report_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_report_data_for_worker",
            lambda j: (_ for _ in ()).throw(RuntimeError("Final failure")),
        )

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status, **extra})

        monkeypatch.setattr("app.services.report_worker.update_report_job", fake_update)
        monkeypatch.setattr(
            "app.services.report_worker.update_report_status",
            lambda *a, **kw: asyncio.sleep(0),
        )
        monkeypatch.setattr("app.services.report_worker.send_alert", MagicMock())
        monkeypatch.setattr("app.services.report_worker.logger", MagicMock())

        from app.services.report_worker import run_report_job

        with pytest.raises(RuntimeError):
            run_report_job({"job_id": "test-report-5"})

        last_update = updates[-1]
        assert last_update["status"] == ReportStatus.FAILED.value
        assert "Final failure" in last_update.get("error", "")

    def test_job_failure_requeues_on_retry(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-report-6"
        mock_job.meta = {"max_retries": 3, "current_attempt": 1}
        mock_job.retries_left = 2
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr(
            "app.services.report_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_report_data_for_worker",
            lambda j: (_ for _ in ()).throw(ConnectionError("Timeout")),
        )

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status})

        monkeypatch.setattr("app.services.report_worker.update_report_job", fake_update)
        monkeypatch.setattr(
            "app.services.report_worker.update_report_status",
            lambda *a, **kw: asyncio.sleep(0),
        )
        monkeypatch.setattr("app.services.report_worker.send_alert", MagicMock())
        monkeypatch.setattr("app.services.report_worker.logger", MagicMock())

        from app.services.report_worker import run_report_job

        with pytest.raises(ConnectionError):
            run_report_job({"job_id": "test-report-6"})

        last_update = updates[-1]
        assert last_update.get("status") == ReportStatus.QUEUED.value

    def test_job_failure_sends_alert_on_permanent_failure(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-report-7"
        mock_job.meta = {"max_retries": 3, "current_attempt": 3}
        mock_job.retries_left = 0
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr(
            "app.services.report_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_report_data_for_worker",
            lambda j: (_ for _ in ()).throw(ValueError("Dead")),
        )
        monkeypatch.setattr("app.services.report_worker.update_report_job", MagicMock())
        monkeypatch.setattr(
            "app.services.report_worker.update_report_status",
            lambda *a, **kw: asyncio.sleep(0),
        )

        alerts = []

        def fake_alert(msg):
            alerts.append(msg)

        monkeypatch.setattr("app.services.report_worker.send_alert", fake_alert)
        monkeypatch.setattr("app.services.report_worker.logger", MagicMock())

        from app.services.report_worker import run_report_job

        with pytest.raises(ValueError):
            run_report_job({"job_id": "test-report-7"})

        assert len(alerts) == 1
        assert "test-report-7" in alerts[0]

    def test_worker_logs_useful_information(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-log-1"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr(
            "app.services.report_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_report_data_for_worker",
            lambda j: {
                "total": 10,
                "done": 5,
                "not_done": 5,
                "completion_pct": 50.0,
                "recent_tasks": [],
            },
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_scraped_books_stats", lambda: None
        )
        monkeypatch.setattr(
            "app.services.report_worker.get_ai_jobs_stats", lambda: None
        )
        monkeypatch.setattr(
            "app.services.report_worker.generate_report",
            lambda j, s, b, a: "/path/to/report.pdf",
        )

        log_messages = []

        class FakeLogger:
            def info(self, msg, *args, **kwargs):
                log_messages.append(("info", msg % args if args else msg))

            def warning(self, msg, *args, **kwargs):
                log_messages.append(("warning", msg % args if args else msg))

            def error(self, msg, *args, **kwargs):
                log_messages.append(("error", msg % args if args else msg))

        monkeypatch.setattr("app.services.report_worker.logger", FakeLogger())
        monkeypatch.setattr("app.services.report_worker.update_report_job", MagicMock())
        monkeypatch.setattr(
            "app.services.report_worker.update_report_status",
            lambda *a, **kw: asyncio.sleep(0),
        )

        from app.services.report_worker import run_report_job

        run_report_job({"job_id": "test-log-1"})
        logged = " ".join(m[1] for m in log_messages)
        assert "test-log-1" in logged
        assert "started" in logged or "completed" in logged

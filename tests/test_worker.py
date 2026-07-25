from unittest.mock import MagicMock

import pytest

from app.models.job import JobStatus


class TestRunAIJob:
    def test_successful_execution(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-job-1"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr("app.services.ai_worker.call_ai", lambda p: "AI result")
        monkeypatch.setattr("app.services.ai_worker.update_job", MagicMock())

        from app.services.ai_worker import run_ai_job

        result = run_ai_job({"prompt": "Hello"})
        assert result == "AI result"

    def test_job_started_status_set(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-job-2"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr("app.services.ai_worker.call_ai", lambda p: "result")

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status, **extra})

        monkeypatch.setattr("app.services.ai_worker.update_job", fake_update)

        from app.services.ai_worker import run_ai_job

        run_ai_job({"prompt": "Hello"})
        assert any(u["status"] == JobStatus.STARTED.value for u in updates)

    def test_job_completed_status_set(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-job-3"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr("app.services.ai_worker.call_ai", lambda p: "result")

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status, **extra})

        monkeypatch.setattr("app.services.ai_worker.update_job", fake_update)

        from app.services.ai_worker import run_ai_job

        run_ai_job({"prompt": "Hello"})
        assert any(u["status"] == JobStatus.FINISHED.value for u in updates)

    def test_job_success_returns_result_in_response(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-job-4"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr("app.services.ai_worker.update_job", MagicMock())

        expected = "Hello! I am an AI."
        monkeypatch.setattr("app.services.ai_worker.call_ai", lambda p: expected)

        from app.services.ai_worker import run_ai_job

        result = run_ai_job({"prompt": "Hi"})
        assert result == expected

    def test_job_failure_during_execution(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-job-5"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 1

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr(
            "app.services.ai_worker.call_ai",
            lambda p: (_ for _ in ()).throw(ValueError("API failure")),
        )
        monkeypatch.setattr("app.services.ai_worker.update_job", MagicMock())
        monkeypatch.setattr("app.services.ai_worker.send_alert", MagicMock())
        monkeypatch.setattr("app.services.ai_worker.logger", MagicMock())

        from app.services.ai_worker import run_ai_job

        with pytest.raises(ValueError, match="API failure"):
            run_ai_job({"prompt": "Hello"})

    def test_job_failure_sets_failed_status_after_retries_exhausted(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-job-6"
        mock_job.meta = {"max_retries": 3, "current_attempt": 3}
        mock_job.retries_left = 0
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr(
            "app.services.ai_worker.call_ai",
            lambda p: (_ for _ in ()).throw(RuntimeError("Final failure")),
        )

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status, **extra})

        monkeypatch.setattr("app.services.ai_worker.update_job", fake_update)
        monkeypatch.setattr("app.services.ai_worker.send_alert", MagicMock())
        monkeypatch.setattr("app.services.ai_worker.logger", MagicMock())

        from app.services.ai_worker import run_ai_job

        with pytest.raises(RuntimeError):
            run_ai_job({"prompt": "Hello"})

        last_update = updates[-1]
        assert last_update["status"] == JobStatus.FAILED.value
        assert "Final failure" in last_update.get("error", "")

    def test_job_failure_stores_error_message(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-job-7"
        mock_job.meta = {"max_retries": 3, "current_attempt": 2}
        mock_job.retries_left = 0
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr(
            "app.services.ai_worker.call_ai",
            lambda p: (_ for _ in ()).throw(TimeoutError("Request timed out")),
        )

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status, **extra})

        monkeypatch.setattr("app.services.ai_worker.update_job", fake_update)
        monkeypatch.setattr("app.services.ai_worker.send_alert", MagicMock())
        monkeypatch.setattr("app.services.ai_worker.logger", MagicMock())

        from app.services.ai_worker import run_ai_job

        with pytest.raises(TimeoutError):
            run_ai_job({"prompt": "Hello"})

        last_update = updates[-1]
        assert "Request timed out" in last_update.get("error", "")

    def test_job_failure_requeues_on_retry(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-job-8"
        mock_job.meta = {"max_retries": 3, "current_attempt": 1}
        mock_job.retries_left = 2
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr(
            "app.services.ai_worker.call_ai",
            lambda p: (_ for _ in ()).throw(ConnectionError("Timeout")),
        )

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status})

        monkeypatch.setattr("app.services.ai_worker.update_job", fake_update)
        monkeypatch.setattr("app.services.ai_worker.send_alert", MagicMock())
        monkeypatch.setattr("app.services.ai_worker.logger", MagicMock())

        from app.services.ai_worker import run_ai_job

        with pytest.raises(ConnectionError):
            run_ai_job({"prompt": "Hello"})

        last_update = updates[-1]
        assert last_update.get("status") == JobStatus.QUEUED.value

    def test_job_failure_sends_alert_on_permanent_failure(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-job-9"
        mock_job.meta = {"max_retries": 3, "current_attempt": 3}
        mock_job.retries_left = 0
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr(
            "app.services.ai_worker.call_ai",
            lambda p: (_ for _ in ()).throw(ValueError("Dead")),
        )
        monkeypatch.setattr("app.services.ai_worker.update_job", MagicMock())

        alerts = []

        def fake_alert(msg):
            alerts.append(msg)

        monkeypatch.setattr("app.services.ai_worker.send_alert", fake_alert)
        monkeypatch.setattr("app.services.ai_worker.logger", MagicMock())

        from app.services.ai_worker import run_ai_job

        with pytest.raises(ValueError):
            run_ai_job({"prompt": "Hello"})

        assert len(alerts) == 1
        assert "test-job-9" in alerts[0]

    def test_job_failure_increments_attempts_in_meta(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-job-10"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 1
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr(
            "app.services.ai_worker.call_ai",
            lambda p: (_ for _ in ()).throw(RuntimeError("Fail")),
        )
        monkeypatch.setattr("app.services.ai_worker.update_job", MagicMock())
        monkeypatch.setattr("app.services.ai_worker.send_alert", MagicMock())
        monkeypatch.setattr("app.services.ai_worker.logger", MagicMock())

        from app.services.ai_worker import run_ai_job

        with pytest.raises(RuntimeError):
            run_ai_job({"prompt": "Hello"})

        assert mock_job.meta["current_attempt"] == 1
        mock_job.save_meta.assert_called_once()


class TestAIWorkerIntegration:
    def test_worker_uses_service_layer_not_business_logic(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-integration-1"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr("app.services.ai_worker.update_job", MagicMock())

        call_count = 0

        def mock_call_ai(payload):
            nonlocal call_count
            call_count += 1
            return f"Business logic result for: {payload['prompt']}"

        monkeypatch.setattr("app.services.ai_worker.call_ai", mock_call_ai)

        from app.services.ai_worker import run_ai_job

        result = run_ai_job({"prompt": "test"})
        assert result == "Business logic result for: test"
        assert call_count == 1

    def test_worker_logs_useful_information(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-log-1"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr("app.services.ai_worker.call_ai", lambda p: "ok")

        log_messages = []

        class FakeLogger:
            def info(self, msg, *args, **kwargs):
                log_messages.append(("info", msg % args if args else msg))

            def warning(self, msg, *args, **kwargs):
                log_messages.append(("warning", msg % args if args else msg))

            def error(self, msg, *args, **kwargs):
                log_messages.append(("error", msg % args if args else msg))

        monkeypatch.setattr("app.services.ai_worker.logger", FakeLogger())
        monkeypatch.setattr("app.services.ai_worker.update_job", MagicMock())

        from app.services.ai_worker import run_ai_job

        run_ai_job({"prompt": "test"})
        logged = " ".join(m[1] for m in log_messages)
        assert "test-log-1" in logged
        assert "started" in logged or "completed" in logged


class TestWorkerEntryPoint:
    def test_run_worker_has_run_function(self):
        from app.worker import run_worker

        assert callable(run_worker)

    def test_run_worker_handles_redis_connection_failure(self, monkeypatch):
        import redis

        def mock_from_url(*args, **kwargs):
            raise redis.RedisError("Connection refused")

        monkeypatch.setattr("redis.from_url", mock_from_url)
        monkeypatch.setattr("sys.exit", lambda code: None)

        from app.worker import run_worker

        run_worker()

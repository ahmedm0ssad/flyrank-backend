from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest


class TestE2EHappyPath:
    def test_post_and_poll_completed(self, client, monkeypatch):
        resp = client.post(
            "/ai",
            json={"prompt": "Say 'hello world' in one word", "model": "llama3-8b-8192"},
        )
        assert resp.status_code == 202
        data = resp.json()
        job_id = data["job_id"]
        assert job_id
        assert data["status_url"] == f"/jobs/{job_id}"

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0
        mock_job.save_meta = MagicMock()
        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr("app.services.ai_worker.call_ai", lambda p: "hello world")

        from app.services.ai_worker import run_ai_job

        run_ai_job({"prompt": "Say 'hello world' in one word", "model": "llama3-8b-8192"})

        final = client.get(f"/jobs/{job_id}").json()
        assert final["status"] == "finished"
        assert "result" in final
        assert len(final["result"]) > 0

    def test_idempotency_key_returns_same_job(self, client):
        key = f"e2e-test-key-{datetime.now(timezone.utc).timestamp()}"

        resp1 = client.post(
            "/ai",
            json={"prompt": "Say hello", "model": "llama3-8b-8192"},
            headers={"Idempotency-Key": key},
        )
        assert resp1.status_code == 202
        job_id_1 = resp1.json()["job_id"]

        resp2 = client.post(
            "/ai",
            json={"prompt": "Say hello", "model": "llama3-8b-8192"},
            headers={"Idempotency-Key": key},
        )
        assert resp2.status_code == 202
        job_id_2 = resp2.json()["job_id"]

        assert job_id_1 == job_id_2


class TestE2EFailure:
    def test_job_eventually_fails_with_max_retries(self, client, monkeypatch):
        from tests.conftest import _fake_redis

        resp = client.post(
            "/ai",
            json={
                "prompt": "test",
                "model": "nonexistent-model-that-will-fail",
            },
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        mock_job = MagicMock()
        mock_job.id = job_id
        mock_job.meta = {"max_retries": 3}
        mock_job.retries_left = 2
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr("app.services.ai_worker.get_current_job", lambda: mock_job)
        monkeypatch.setattr("app.services.ai_worker.send_alert", MagicMock())

        def failing_call_ai(p):
            raise ValueError("Model nonexistent-model-that-will-fail not found")

        monkeypatch.setattr("app.services.ai_worker.call_ai", failing_call_ai)

        from app.services.ai_worker import run_ai_job

        payload = {"prompt": "test", "model": "nonexistent-model-that-will-fail"}

        for attempt in range(2):
            mock_job.meta["current_attempt"] = attempt
            with pytest.raises(ValueError):
                run_ai_job(payload)
            mock_job.retries_left -= 1

        mock_job.meta["current_attempt"] = 2
        mock_job.retries_left = 0
        with pytest.raises(ValueError):
            run_ai_job(payload)

        _fake_redis.hset(f"job:{job_id}", mapping={"attempts": "3"})

        final = client.get(f"/jobs/{job_id}").json()
        assert final["status"] == "failed"
        assert final["attempts"] == 3
        assert "error" in final

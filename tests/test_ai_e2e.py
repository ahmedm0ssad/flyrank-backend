import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import pytest
import requests

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def worker_process():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    proc = subprocess.Popen(
        [sys.executable, "-m", "rq", "worker", "ai-jobs", "--url", redis_url],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


def wait_for_job(job_id: str, timeout: float = 30.0, interval: float = 1.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = requests.get(f"{BASE_URL}/jobs/{job_id}")
        if resp.status_code == 404:
            time.sleep(interval)
            continue
        data = resp.json()
        if data["status"] in ("completed", "failed"):
            return data
        time.sleep(interval)
    raise TimeoutError(f"Job {job_id} did not reach terminal state within {timeout}s")


class TestE2EHappyPath:
    def test_post_and_poll_completed(self, worker_process):
        resp = requests.post(
            f"{BASE_URL}/ai",
            json={"prompt": "Say 'hello world' in one word", "model": "llama3-8b-8192"},
        )
        assert resp.status_code == 202
        data = resp.json()
        job_id = data["job_id"]
        assert job_id
        assert data["status_url"] == f"/jobs/{job_id}"

        final = wait_for_job(job_id, timeout=60)
        assert final["status"] == "completed"
        assert "result" in final
        assert len(final["result"]) > 0

    def test_idempotency_key_returns_same_job(self, worker_process):
        key = f"e2e-test-key-{datetime.now(timezone.utc).timestamp()}"

        resp1 = requests.post(
            f"{BASE_URL}/ai",
            json={"prompt": "Say hello", "model": "llama3-8b-8192"},
            headers={"Idempotency-Key": key},
        )
        assert resp1.status_code == 202
        job_id_1 = resp1.json()["job_id"]

        resp2 = requests.post(
            f"{BASE_URL}/ai",
            json={"prompt": "Say hello", "model": "llama3-8b-8192"},
            headers={"Idempotency-Key": key},
        )
        assert resp2.status_code == 202
        job_id_2 = resp2.json()["job_id"]

        assert job_id_1 == job_id_2


class TestE2EFailure:
    def test_job_eventually_fails_with_max_retries(self, worker_process):
        resp = requests.post(
            f"{BASE_URL}/ai",
            json={
                "prompt": "test",
                "model": "nonexistent-model-that-will-fail",
            },
        )
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        final = wait_for_job(job_id, timeout=120)
        assert final["status"] == "failed"
        assert final["attempts"] == 3
        assert "error" in final

from fastapi.testclient import TestClient


class TestCreateAIJob:
    def test_post_returns_202_with_job_id(self, client: TestClient):
        response = client.post(
            "/ai",
            json={"prompt": "Hello", "model": "llama3-8b-8192"},
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_post_without_model_uses_default(self, client: TestClient):
        response = client.post(
            "/ai",
            json={"prompt": "Hello"},
        )
        assert response.status_code == 202

    def test_post_missing_prompt_returns_422(self, client: TestClient):
        response = client.post(
            "/ai",
            json={"model": "llama3-8b-8192"},
        )
        assert response.status_code == 422

    def test_post_empty_prompt_returns_422(self, client: TestClient):
        response = client.post(
            "/ai",
            json={"prompt": "", "model": "llama3-8b-8192"},
        )
        assert response.status_code == 422

    def test_same_idempotency_key_returns_same_job_id(self, client: TestClient):
        response1 = client.post(
            "/ai",
            json={"prompt": "Hello"},
            headers={"Idempotency-Key": "key-123"},
        )
        assert response1.status_code == 202
        first_job_id = response1.json()["job_id"]

        response2 = client.post(
            "/ai",
            json={"prompt": "Hello"},
            headers={"Idempotency-Key": "key-123"},
        )
        assert response2.status_code == 202
        assert response2.json()["job_id"] == first_job_id

    def test_without_idempotency_key_returns_different_jobs(self, client: TestClient):
        response1 = client.post("/ai", json={"prompt": "Hello"})
        response2 = client.post("/ai", json={"prompt": "Hello"})
        assert response1.json()["job_id"] != response2.json()["job_id"]

    def test_multiple_requests_without_key_create_multiple_jobs(
        self, client: TestClient
    ):
        ids = set()
        for _ in range(3):
            resp = client.post("/ai", json={"prompt": "Hello"})
            ids.add(resp.json()["job_id"])
        assert len(ids) == 3


class TestGetJobStatus:
    def test_unknown_job_returns_404(self, client: TestClient):
        response = client.get("/jobs/unknown-id")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Job not found"

    def test_queued_status(self, client: TestClient, monkeypatch):
        _inject_job(monkeypatch, "test-job-1", {"status": "queued"})

        response = client.get("/jobs/test-job-1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "queued"
        assert data["job_id"] == "test-job-1"

    def test_started_status(self, client: TestClient, monkeypatch):
        _inject_job(
            monkeypatch,
            "test-job-2",
            {"status": "started", "started_at": "2025-01-01T00:00:00"},
        )

        response = client.get("/jobs/test-job-2")
        assert response.status_code == 200
        assert response.json()["status"] == "started"

    def test_finished_status(self, client: TestClient, monkeypatch):
        _inject_job(
            monkeypatch,
            "test-job-3",
            {"status": "finished", "result": "AI output here"},
        )

        response = client.get("/jobs/test-job-3")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "finished"
        assert data["result"] == "AI output here"

    def test_failed_status(self, client: TestClient, monkeypatch):
        _inject_job(
            monkeypatch,
            "test-job-4",
            {"status": "failed", "error": "API error", "attempts": "3"},
        )

        response = client.get("/jobs/test-job-4")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "API error"
        assert data["attempts"] == 3

    def test_job_with_timestamps(self, client: TestClient, monkeypatch):
        _inject_job(
            monkeypatch,
            "test-job-5",
            {
                "status": "finished",
                "created_at": "2025-01-01T00:00:00",
                "started_at": "2025-01-01T00:00:10",
                "finished_at": "2025-01-01T00:00:30",
            },
        )

        response = client.get("/jobs/test-job-5")
        data = response.json()
        assert data["created_at"] == "2025-01-01T00:00:00"
        assert data["started_at"] == "2025-01-01T00:00:10"
        assert data["finished_at"] == "2025-01-01T00:00:30"


class TestListJobs:
    def test_list_jobs_empty(self, client: TestClient):
        response = client.get("/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_list_jobs_with_data(self, client: TestClient, monkeypatch):
        _inject_job(monkeypatch, "job-a", {"status": "finished", "result": "A"})
        _inject_job(monkeypatch, "job-b", {"status": "failed", "error": "err"})

        response = client.get("/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_list_jobs_pagination(self, client: TestClient, monkeypatch):
        for i in range(5):
            _inject_job(monkeypatch, f"job-{i}", {"status": "queued"})

        response = client.get("/jobs?limit=2&offset=0")
        data = response.json()
        assert len(data["jobs"]) == 2
        assert data["total"] == 2

    def test_list_jobs_with_limit_and_offset(self, client: TestClient, monkeypatch):
        import string

        for letter in string.ascii_lowercase[:10]:
            _inject_job(monkeypatch, f"job-{letter}", {"status": "queued"})

        response = client.get("/jobs?limit=3&offset=2")
        data = response.json()
        assert len(data["jobs"]) == 3

    def test_list_jobs_invalid_limit_returns_422(self, client: TestClient):
        response = client.get("/jobs?limit=0")
        assert response.status_code == 422

    def test_list_jobs_limit_too_high_clamps(self, client: TestClient):
        response = client.get("/jobs?limit=200")
        assert response.status_code == 422


def _inject_job(monkeypatch, job_id: str, data: dict):
    from tests.conftest import _fake_redis

    _fake_redis.hset(f"job:{job_id}", mapping=data)


class TestErrorResponses:
    def test_404_returns_json_detail(self, client: TestClient):
        response = client.get("/jobs/nonexistent")
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_422_returns_json_detail(self, client: TestClient):
        response = client.post("/ai", json={"prompt": ""})
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_no_stack_trace_in_error(self, client: TestClient):
        response = client.get("/jobs/nonexistent")
        assert "traceback" not in response.text.lower()
        assert 'File "' not in response.text

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.models.job import JobStatus


class TestQueueModule:
    def test_get_connection_returns_singleton(self, monkeypatch):
        from app.core import queue as queue_module

        queue_module._connection = None
        queue_module._queue = None

        conn1 = queue_module.get_connection()
        conn2 = queue_module.get_connection()
        assert conn1 is conn2

        queue_module.reset_connection()

    def test_get_queue_returns_singleton(self, monkeypatch):
        from app.core import queue as queue_module

        queue_module._connection = None
        queue_module._queue = None

        q1 = queue_module.get_queue()
        q2 = queue_module.get_queue()
        assert q1 is q2

        queue_module.reset_connection()

    def test_reset_connection_clears_singletons(self, monkeypatch):
        from app.core import queue as queue_module

        queue_module._connection = MagicMock()
        queue_module._queue = MagicMock()

        queue_module.reset_connection()
        assert queue_module._connection is None
        assert queue_module._queue is None

    def test_create_job_returns_job_id_and_status(self, monkeypatch):
        from app.core import queue as queue_module

        job_id, status = queue_module.create_job({"prompt": "Hello"})
        assert job_id is not None
        assert status == JobStatus.QUEUED

    def test_create_job_stores_in_redis(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_redis

        job_id, _ = queue_module.create_job({"prompt": "Hello"})
        data = _fake_redis.hgetall(f"job:{job_id}")
        assert data["status"] == "queued"
        assert data["attempts"] == "0"

    def test_create_job_with_idempotency_key(self, monkeypatch):
        from app.core import queue as queue_module

        job_id_1, _ = queue_module.create_job(
            {"prompt": "Hello"}, idempotency_key="key-1"
        )
        job_id_2, _ = queue_module.create_job(
            {"prompt": "Hello"}, idempotency_key="key-1"
        )
        assert job_id_1 == job_id_2

    def test_create_job_without_idempotency_key_different(self, monkeypatch):
        from app.core import queue as queue_module

        job_id_1, _ = queue_module.create_job({"prompt": "Hello"})
        job_id_2, _ = queue_module.create_job({"prompt": "Hello"})
        assert job_id_1 != job_id_2

    def test_get_job_returns_none_for_missing(self, monkeypatch):
        from app.core import queue as queue_module

        result = queue_module.get_job("nonexistent")
        assert result is None

    def test_get_job_returns_job_response(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_redis

        _fake_redis.hset("job:test-1", mapping={"status": "finished", "result": "done"})

        job = queue_module.get_job("test-1")
        assert job is not None
        assert job.job_id == "test-1"
        assert job.status == JobStatus.FINISHED
        assert job.result == "done"

    def test_update_job_changes_status(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_redis

        _fake_redis.hset("job:test-2", mapping={"status": "queued"})

        queue_module.update_job("test-2", "started", started_at="2025-01-01T00:00:00")
        data = _fake_redis.hgetall("job:test-2")
        assert data["status"] == "started"
        assert data["started_at"] == "2025-01-01T00:00:00"

    def test_list_jobs_empty(self, monkeypatch):
        from app.core import queue as queue_module

        jobs = queue_module.list_jobs()
        assert jobs == []

    def test_list_jobs_with_entries(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_redis

        _fake_redis.hset("job:a", mapping={"status": "finished"})
        _fake_redis.hset("job:b", mapping={"status": "failed"})

        jobs = queue_module.list_jobs()
        assert len(jobs) == 2

    def test_list_jobs_pagination(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_redis

        for i in range(5):
            _fake_redis.hset(f"job:{i}", mapping={"status": "queued"})

        jobs = queue_module.list_jobs(limit=2, offset=0)
        assert len(jobs) == 2


class TestJobRetry:
    def test_retry_configured_with_correct_intervals(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_queue

        queue_module.create_job({"prompt": "Hello"})
        assert len(_fake_queue.enqueued_jobs) == 1
        kwargs = _fake_queue.enqueued_jobs[0]["kwargs"]
        assert "retry" in kwargs
        retry = kwargs["retry"]
        assert retry.max == 3
        assert retry.intervals == [10, 60, 300]

    def test_retry_does_not_lose_job_data_on_failure(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_redis

        job_id, _ = queue_module.create_job({"prompt": "Hello"})
        queue_module.update_job(
            job_id, "failed", error="Something broke", finished_at="now"
        )
        data = _fake_redis.hgetall(f"job:{job_id}")
        assert data["status"] == "failed"
        assert data["error"] == "Something broke"

    def test_job_data_persists_across_status_transitions(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_redis

        job_id, _ = queue_module.create_job({"prompt": "Hello"})
        queue_module.update_job(job_id, "started", started_at="t1")
        queue_module.update_job(job_id, "finished", result="done", finished_at="t2")

        data = _fake_redis.hgetall(f"job:{job_id}")
        assert data["status"] == "finished"
        assert data["result"] == "done"
        assert data["created_at"] is not None


class TestJobIdempotency:
    def test_same_idempotency_key_returns_same_job(self, client: TestClient):
        resp1 = client.post(
            "/ai",
            json={"prompt": "Hello"},
            headers={"Idempotency-Key": "idem-test-1"},
        )
        resp2 = client.post(
            "/ai",
            json={"prompt": "Hello"},
            headers={"Idempotency-Key": "idem-test-1"},
        )
        assert resp1.json()["job_id"] == resp2.json()["job_id"]

    def test_different_idempotency_keys_different_jobs(self, client: TestClient):
        resp1 = client.post(
            "/ai",
            json={"prompt": "Hello"},
            headers={"Idempotency-Key": "idem-a"},
        )
        resp2 = client.post(
            "/ai",
            json={"prompt": "Hello"},
            headers={"Idempotency-Key": "idem-b"},
        )
        assert resp1.json()["job_id"] != resp2.json()["job_id"]

    def test_idempotency_key_no_duplicate_enqueue(
        self, client: TestClient, monkeypatch
    ):
        from tests.conftest import _fake_queue

        client.post(
            "/ai",
            json={"prompt": "Hello"},
            headers={"Idempotency-Key": "idem-no-dupe"},
        )
        client.post(
            "/ai",
            json={"prompt": "Hello"},
            headers={"Idempotency-Key": "idem-no-dupe"},
        )

        assert len(_fake_queue.enqueued_jobs) == 1

    def test_idempotency_does_not_create_inconsistent_state(self, client: TestClient):
        resp1 = client.post(
            "/ai",
            json={"prompt": "Test state"},
            headers={"Idempotency-Key": "idem-state-test"},
        )
        resp2 = client.post(
            "/ai",
            json={"prompt": "Test state"},
            headers={"Idempotency-Key": "idem-state-test"},
        )
        assert resp1.json() == resp2.json()


class TestErrorHandling:
    def test_invalid_payload_returns_422(self, client: TestClient):
        response = client.post("/ai", json={})
        assert response.status_code == 422

    def test_missing_prompt_field_returns_422(self, client: TestClient):
        response = client.post("/ai", json={"model": "test"})
        assert response.status_code == 422

    def test_wrong_method_returns_405(self, client: TestClient):
        response = client.put("/ai", json={"prompt": "Hello"})
        assert response.status_code == 405

    def test_nonexistent_endpoint_returns_404(self, client: TestClient):
        response = client.get("/ai/nonexistent")
        assert response.status_code == 404

    def test_error_response_has_json_format(self, client: TestClient):
        response = client.get("/jobs/nonexistent")
        assert response.headers["content-type"] == "application/json"


class TestJobModels:
    def test_job_status_enum_values(self):
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.STARTED.value == "started"
        assert JobStatus.FINISHED.value == "finished"
        assert JobStatus.FAILED.value == "failed"

    def test_job_status_all_members(self):
        assert len(JobStatus) == 4

    def test_job_enqueue_response_serialization(self):
        from app.models.job import JobEnqueueResponse

        resp = JobEnqueueResponse(job_id="abc-123", status=JobStatus.QUEUED)
        data = resp.model_dump()
        assert data["job_id"] == "abc-123"
        assert data["status"] == "queued"

    def test_job_response_default_attempts(self):
        from app.models.job import JobResponse

        resp = JobResponse(job_id="abc", status=JobStatus.QUEUED)
        assert resp.attempts == 0

    def test_job_response_with_all_fields(self):
        from app.models.job import JobResponse

        resp = JobResponse(
            job_id="abc",
            status=JobStatus.FINISHED,
            result="output",
            created_at="t1",
            started_at="t2",
            finished_at="t3",
            attempts=3,
        )
        assert resp.result == "output"
        assert resp.attempts == 3

    def test_job_list_response_serialization(self):
        from app.models.job import JobListResponse, JobResponse

        jobs = [JobResponse(job_id="a", status=JobStatus.QUEUED)]
        resp = JobListResponse(jobs=jobs, total=1)
        data = resp.model_dump()
        assert len(data["jobs"]) == 1
        assert data["total"] == 1


class TestAiService:
    def test_call_ai_with_mock(self, monkeypatch):
        from app.services.ai_service import call_ai

        monkeypatch.setenv("GROQ_API_KEY", "")
        result = call_ai({"prompt": "Say hello", "model": "llama3-8b-8192"})
        assert "Mock response" in result
        assert "Say hello" in result

    def test_call_ai_without_groq_key_uses_mock(self, monkeypatch):
        from app.services.ai_service import call_ai

        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        result = call_ai({"prompt": "test", "model": "test-model"})
        assert result.startswith("Mock response")

    def test_call_ai_uses_provided_model_in_mock(self, monkeypatch):
        from app.services.ai_service import call_ai

        monkeypatch.setenv("GROQ_API_KEY", "")
        result = call_ai({"prompt": "Hi", "model": "llama3-70b-8192"})
        assert "Mock response" in result


class TestEnrichmentQueue:
    def test_create_enrichment_job_returns_job_id(self, monkeypatch):
        from app.core import queue as queue_module

        job_id = queue_module.create_enrichment_job("lead-abc")
        assert job_id is not None

    def test_create_enrichment_job_stores_in_redis(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_redis

        job_id = queue_module.create_enrichment_job("lead-abc")
        data = _fake_redis.hgetall(f"enrichment_job:{job_id}")
        assert data["status"] == "queued"
        assert data["attempts"] == "0"

    def test_create_enrichment_job_enqueues_to_correct_queue(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_queue

        queue_module.create_enrichment_job("lead-abc")
        assert len(_fake_queue.enqueued_jobs) == 1
        kwargs = _fake_queue.enqueued_jobs[0]["kwargs"]
        assert "retry" in kwargs
        retry = kwargs["retry"]
        assert retry.max == 3
        assert retry.intervals == [10, 60, 300]
        assert kwargs["job_timeout"] == 600

    def test_create_enrichment_job_calls_correct_worker(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_queue

        queue_module.create_enrichment_job("lead-abc")
        assert len(_fake_queue.enqueued_jobs) == 1
        assert (
            _fake_queue.enqueued_jobs[0]["func"]
            == "app.services.lead_worker.run_enrichment_job"
        )
        assert _fake_queue.enqueued_jobs[0]["args"] == ("lead-abc",)

    def test_get_enrichment_job_returns_none_for_missing(self, monkeypatch):
        from app.core import queue as queue_module

        result = queue_module.get_enrichment_job("nonexistent")
        assert result is None

    def test_get_enrichment_job_returns_job_response(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_redis

        _fake_redis.hset(
            "enrichment_job:test-1",
            mapping={"status": "finished", "result": "enriched"},
        )

        job = queue_module.get_enrichment_job("test-1")
        assert job is not None
        assert job.job_id == "test-1"
        assert job.status == JobStatus.FINISHED
        assert job.result == "enriched"

    def test_update_enrichment_job_changes_status(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_redis

        _fake_redis.hset("enrichment_job:test-2", mapping={"status": "queued"})

        queue_module.update_enrichment_job(
            "test-2", "started", started_at="2025-01-01T00:00:00"
        )
        data = _fake_redis.hgetall("enrichment_job:test-2")
        assert data["status"] == "started"
        assert data["started_at"] == "2025-01-01T00:00:00"

    def test_get_enrichment_queue_returns_singleton(self, monkeypatch):
        from app.core import queue as queue_module

        queue_module._enrichment_queue = None
        q1 = queue_module.get_enrichment_queue()
        q2 = queue_module.get_enrichment_queue()
        assert q1 is q2

        queue_module.reset_connection()

    def test_enrichment_retry_config_matches_report_jobs(self, monkeypatch):
        from app.core import queue as queue_module
        from tests.conftest import _fake_queue

        queue_module.create_enrichment_job("lead-abc")
        kwargs = _fake_queue.enqueued_jobs[0]["kwargs"]
        retry = kwargs["retry"]
        assert retry.max == 3
        assert retry.intervals == [10, 60, 300]
        assert retry.intervals == [10, 60, 300]


class TestFailureHandling:
    def test_job_failure_response_includes_status_and_error(
        self, client: TestClient, monkeypatch
    ):
        from tests.conftest import _fake_redis

        _fake_redis.hset(
            "job:failed-1",
            mapping={
                "status": "failed",
                "error": "Model not found",
                "attempts": "3",
                "finished_at": "2025-01-01T00:00:00",
            },
        )

        response = client.get("/jobs/failed-1")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Model not found"
        assert data["attempts"] == 3

    def test_no_stack_trace_on_404(self, client: TestClient):
        response = client.get("/jobs/ghost")
        assert response.status_code == 404
        assert "File" not in response.text

    def test_no_stack_trace_on_422(self, client: TestClient):
        response = client.post("/ai", json={"prompt": ""})
        assert response.status_code == 422
        assert "File" not in response.text

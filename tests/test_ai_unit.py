from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestCreateAIJob:
    def test_post_returns_202_with_job_id(self, client: TestClient, monkeypatch):
        mock_queue = MagicMock()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {}
        mock_redis.get.return_value = None

        with patch("app.routers.ai._get_queue", return_value=(mock_queue, mock_redis)):
            response = client.post(
                "/ai",
                json={"prompt": "Hello", "model": "llama3-8b-8192"},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert "status_url" in data
        assert data["status_url"] == f"/jobs/{data['job_id']}"

        mock_queue.enqueue.assert_called_once()

        mock_redis.hset.assert_called_once()

    def test_post_does_not_call_real_ai(self, client: TestClient, monkeypatch):
        mock_queue = MagicMock()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {}
        mock_redis.get.return_value = None

        with patch("app.routers.ai._get_queue", return_value=(mock_queue, mock_redis)):
            response = client.post(
                "/ai",
                json={"prompt": "Hello"},
            )

        assert response.status_code == 202

    def test_same_idempotency_key_returns_same_job_id(
        self, client: TestClient, monkeypatch
    ):
        mock_queue = MagicMock()
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        mock_redis.hgetall.side_effect = [{}, {"status": "queued", "result": ""}]

        with patch("app.routers.ai._get_queue", return_value=(mock_queue, mock_redis)):
            response1 = client.post(
                "/ai",
                json={"prompt": "Hello"},
                headers={"Idempotency-Key": "key-123"},
            )
            assert response1.status_code == 202
            first_job_id = response1.json()["job_id"]

            mock_redis.get.return_value = first_job_id

            response2 = client.post(
                "/ai",
                json={"prompt": "Hello"},
                headers={"Idempotency-Key": "key-123"},
            )

        assert response2.status_code == 202
        assert response2.json()["job_id"] == first_job_id

        assert mock_queue.enqueue.call_count == 1

    def test_without_idempotency_key_enqueues_new_each_time(
        self, client: TestClient, monkeypatch
    ):
        mock_queue = MagicMock()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {}
        mock_redis.get.return_value = None

        with patch("app.routers.ai._get_queue", return_value=(mock_queue, mock_redis)):
            client.post("/ai", json={"prompt": "Hello"})
            client.post("/ai", json={"prompt": "Hello"})

        assert mock_queue.enqueue.call_count == 2


class TestGetJobStatus:
    def test_unknown_job_returns_404(self, client: TestClient, monkeypatch):
        mock_queue = MagicMock()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {}
        mock_redis.get.return_value = None

        with patch("app.routers.ai._get_queue", return_value=(mock_queue, mock_redis)):
            response = client.get("/jobs/unknown-id")

        assert response.status_code == 404
        data = response.json()
        assert data["error"] == "Job not found"

    def test_queued_status(self, client: TestClient, monkeypatch):
        mock_queue = MagicMock()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {"status": "queued"}

        with patch("app.routers.ai._get_queue", return_value=(mock_queue, mock_redis)):
            response = client.get("/jobs/some-id")

        assert response.status_code == 200
        assert response.json() == {"status": "queued"}

    def test_processing_status(self, client: TestClient, monkeypatch):
        mock_queue = MagicMock()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {"status": "processing"}

        with patch("app.routers.ai._get_queue", return_value=(mock_queue, mock_redis)):
            response = client.get("/jobs/some-id")

        assert response.status_code == 200
        assert response.json() == {"status": "processing"}

    def test_completed_status(self, client: TestClient, monkeypatch):
        mock_queue = MagicMock()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            "status": "completed",
            "result": "AI output here",
        }

        with patch("app.routers.ai._get_queue", return_value=(mock_queue, mock_redis)):
            response = client.get("/jobs/some-id")

        assert response.status_code == 200
        assert response.json() == {"status": "completed", "result": "AI output here"}

    def test_failed_status(self, client: TestClient, monkeypatch):
        mock_queue = MagicMock()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            "status": "failed",
            "error": "API error",
            "attempts": "3",
        }

        with patch("app.routers.ai._get_queue", return_value=(mock_queue, mock_redis)):
            response = client.get("/jobs/some-id")

        assert response.status_code == 200
        assert response.json() == {
            "status": "failed",
            "error": "API error",
            "attempts": 3,
        }

import uuid

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.main import app

pytestmark = pytest.mark.usefixtures("mock_redis")


@pytest.fixture
def client():
    return TestClient(app)


class TestSubmitLead:
    def test_201_success(self, client, created_widget):
        widget_id = str(created_widget.id)
        resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={
                "form_data": {"name": "John", "email": "john@test.com"},
            },
            headers={"Origin": "https://myshop.com"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert "lead_id" in data

    def test_400_validation_error(self, client, created_widget):
        widget_id = str(created_widget.id)
        resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={"form_data": "not-an-object"},
            headers={"Origin": "https://myshop.com"},
        )
        assert resp.status_code == 400

    def test_403_origin_mismatch(self, client, created_widget):
        widget_id = str(created_widget.id)
        resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={"form_data": {"name": "John"}},
            headers={"Origin": "https://evil.com"},
        )
        assert resp.status_code == 403

    def test_404_widget_not_found(self, client):
        resp = client.post(
            "/public/widget/00000000-0000-0000-0000-000000000000/submit",
            json={"form_data": {"name": "John"}},
            headers={"Origin": "https://myshop.com"},
        )
        assert resp.status_code == 404

    def test_413_payload_too_large(self, client, created_widget):
        widget_id = str(created_widget.id)
        big_data = {"form_data": {"x": "a" * 60_000}}
        resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json=big_data,
            headers={"Origin": "https://myshop.com"},
        )
        assert resp.status_code == 413

    def test_429_rate_limited(self, client, created_widget, fake_redis, monkeypatch):
        from app.dependencies.leads import check_rate_limits

        async def mock_over_limit(ip, widget_id):
            return 60

        monkeypatch.setattr(
            "app.services.lead_service.check_rate_limits", mock_over_limit
        )

        widget_id = str(created_widget.id)
        resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={"form_data": {"name": "John"}},
            headers={"Origin": "https://myshop.com"},
        )
        assert resp.status_code == 429

    def test_honeypot_returns_fake_success(self, client, created_widget):
        from app.services import widget_service
        import asyncio

        widget_id = str(created_widget.id)
        raw = asyncio.run(widget_service._get_repo().get_by_id_raw(widget_id))
        honeypot_field = raw["config"].get("honeypot_field", "_hp_a3f9")

        resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={
                "form_data": {
                    "name": "Bot",
                    "email": "bot@spam.com",
                    honeypot_field: "bot value",
                },
            },
            headers={"Origin": "https://myshop.com"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True

    def test_dedup_returns_same_lead_id(self, client, created_widget):
        widget_id = str(created_widget.id)
        payload = {
            "form_data": {"name": "John", "email": "john@test.com"},
        }
        headers = {"Origin": "https://myshop.com"}

        resp1 = client.post(
            f"/public/widget/{widget_id}/submit", json=payload, headers=headers
        )
        assert resp1.status_code == 201
        lead_id1 = resp1.json()["lead_id"]

        resp2 = client.post(
            f"/public/widget/{widget_id}/submit", json=payload, headers=headers
        )
        assert resp2.status_code == 201
        lead_id2 = resp2.json()["lead_id"]

        assert lead_id1 == lead_id2


class TestReEnrichLead:
    @pytest.fixture(autouse=True)
    def _mock_auth(self):
        mock_user = {
            "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
            "email": "test@example.com",
            "access_token": "fake-token",
        }
        app.dependency_overrides[get_current_user] = lambda: mock_user
        yield
        app.dependency_overrides.pop(get_current_user, None)

    def test_202_re_enqueues_failed_lead(self, client, created_widget):
        from app.services import lead_service

        repo = lead_service._get_or_create_repo()
        lead_id = str(uuid.uuid4())
        repo._leads[lead_id] = {
            "id": lead_id,
            "widget_id": str(created_widget.id),
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "form_data": {"name": "John"},
            "ip_address": "8.8.8.8",
            "fingerprint": "abc",
            "status": "failed",
            "honeypot_triggered": False,
            "spam_score": 0.0,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        from tests.conftest import _fake_queue

        _fake_queue.enqueued_jobs.clear()

        resp = client.post(
            f"/widgets/{created_widget.id}/leads/{lead_id}/re-enrich",
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "re-enqueued"
        assert data["lead_id"] == lead_id

    def test_409_if_already_enriched(self, client, created_widget):
        from app.services import lead_service

        repo = lead_service._get_or_create_repo()
        lead_id = str(uuid.uuid4())
        repo._leads[lead_id] = {
            "id": lead_id,
            "widget_id": str(created_widget.id),
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "form_data": {"name": "John"},
            "ip_address": "8.8.8.8",
            "fingerprint": "abc",
            "status": "enriched",
            "honeypot_triggered": False,
            "spam_score": 0.0,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        resp = client.post(
            f"/widgets/{created_widget.id}/leads/{lead_id}/re-enrich",
        )
        assert resp.status_code == 409

    def test_409_if_in_flight_pending(self, client, created_widget):
        from app.services import lead_service

        repo = lead_service._get_or_create_repo()
        lead_id = str(uuid.uuid4())
        repo._leads[lead_id] = {
            "id": lead_id,
            "widget_id": str(created_widget.id),
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "form_data": {"name": "John"},
            "ip_address": "8.8.8.8",
            "fingerprint": "abc",
            "status": "pending",
            "honeypot_triggered": False,
            "spam_score": 0.0,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:00:00",
        }

        resp = client.post(
            f"/widgets/{created_widget.id}/leads/{lead_id}/re-enrich",
        )
        assert resp.status_code == 409

    def test_404_lead_not_found(self, client, created_widget):
        resp = client.post(
            f"/widgets/{created_widget.id}/leads/"
            f"00000000-0000-0000-0000-000000000000/re-enrich",
        )
        assert resp.status_code == 404

    def test_404_widget_not_found(self, client):
        resp = client.post(
            "/widgets/00000000-0000-0000-0000-000000000000/leads/"
            "00000000-0000-0000-0000-000000000000/re-enrich",
        )
        assert resp.status_code == 404

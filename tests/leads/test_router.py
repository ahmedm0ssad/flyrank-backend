import pytest
from fastapi.testclient import TestClient

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

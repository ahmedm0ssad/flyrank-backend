import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.main import app
from app.models.widget import WidgetCreate
from app.services import widget_service

pytestmark = pytest.mark.usefixtures("mock_redis")

MOCK_USER = {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "test@example.com",
    "access_token": "fake-token",
}


@pytest.fixture(autouse=True)
def _mock_auth():
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _reset_widget_repo():
    from app.services.widget_service import _get_repo
    repo = _get_repo()
    repo._widgets.clear()


@pytest.fixture(autouse=True)
def _reset_lead_repo():
    from app.services.lead_service import _get_or_create_repo
    repo = _get_or_create_repo()
    repo._leads.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def widget():
    data = WidgetCreate(
        name="E2E Widget",
        domain="https://myshop.com",
        config={
            "brand_color": "#2563eb",
            "button_text": "Get a Quote",
            "fields": ["name", "email", "phone"],
            "success_message": "Thanks!",
        },
    )
    w = asyncio.run(widget_service.create_widget(data, "11111111-1111-1111-1111-111111111111"))
    return w


class TestE2EWidget:
    def test_full_happy_path(self, client, widget):
        widget_id = str(widget.id)

        config_resp = client.get(f"/public/widget/{widget_id}/config")
        assert config_resp.status_code == 200
        config = config_resp.json()
        assert config["widget_id"] == widget_id
        assert "honeypot_field" in config

        submit_resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={"form_data": {"name": "John", "email": "john@test.com", "phone": "+1234567890"}},
            headers={"Origin": "https://myshop.com"},
        )
        assert submit_resp.status_code == 201
        submit_data = submit_resp.json()
        assert submit_data["success"] is True
        lead_id = submit_data["lead_id"]

        from app.services.lead_service import _get_or_create_repo
        repo = _get_or_create_repo()
        lead = asyncio.run(repo.get_by_id(lead_id))
        assert lead is not None
        assert lead.status == "pending"
        assert lead.honeypot_triggered is False

    def test_honeypot_flow(self, client, widget):
        widget_id = str(widget.id)

        config_resp = client.get(f"/public/widget/{widget_id}/config")
        config = config_resp.json()
        honeypot_field = config["honeypot_field"]

        submit_resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={
                "form_data": {
                    "name": "Bot",
                    "email": "bot@spam.com",
                    honeypot_field: "filled by bot",
                },
            },
            headers={"Origin": "https://myshop.com"},
        )
        assert submit_resp.status_code == 201
        submit_data = submit_resp.json()
        assert submit_data["success"] is True
        lead_id = submit_data["lead_id"]

        from app.services.lead_service import _get_or_create_repo
        repo = _get_or_create_repo()
        lead = asyncio.run(repo.get_by_id(lead_id))
        assert lead is not None
        assert lead.honeypot_triggered is True
        assert lead.spam_score == 1.0
        assert lead.spam_reasons == ["honeypot"]

    def test_duplicate_submission_dedup(self, client, widget):
        widget_id = str(widget.id)
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

    def test_widget_config_caching(self, client, widget):
        widget_id = str(widget.id)
        resp = client.get(f"/public/widget/{widget_id}/config")
        assert resp.status_code == 200
        data1 = resp.json()

        resp2 = client.get(f"/public/widget/{widget_id}/config")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data1 == data2

    def test_widget_js_served(self, client, widget):
        widget_id = str(widget.id)
        resp = client.get(f"/public/widget/{widget_id}/widget.js?v=1")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/javascript"
        assert str(widget_id) in resp.text

    def test_rate_limited_submission(self, client, widget, monkeypatch):
        async def mock_over_limit(ip, widget_id):
            return 60

        monkeypatch.setattr(
            "app.services.lead_service.check_rate_limits", mock_over_limit
        )

        widget_id = str(widget.id)
        resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={"form_data": {"name": "John"}},
            headers={"Origin": "https://myshop.com"},
        )
        assert resp.status_code == 429

    def test_enrichment_pipeline_end_to_end(self, client, widget, monkeypatch):
        from app.services import lead_service

        widget_id = str(widget.id)
        submit_resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={"form_data": {"name": "Alice", "email": "alice@test.com"}},
            headers={"Origin": "https://myshop.com"},
        )
        assert submit_resp.status_code == 201
        lead_id = submit_resp.json()["lead_id"]

        from app.services.lead_worker import run_enrichment_job
        import app.services.lead_worker as lw

        shared_repo = lead_service._get_or_create_repo()

        class _PatchedRepo:
            def __init__(self):
                self._leads = shared_repo._leads

            async def get_by_id(self, lead_id):
                return await shared_repo.get_by_id(lead_id)

            async def update_status(self, lead_id, status, **kw):
                return await shared_repo.update_status(lead_id, status, **kw)

        monkeypatch.setattr(lw, "LeadRepository", _PatchedRepo)

        lead = asyncio.run(shared_repo.get_by_id(lead_id))
        assert lead is not None, "Lead must exist in shared repo"
        assert lead.status == "pending"

        mock_job = MagicMock()
        mock_job.id = "e2e-enrich-job"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr(lw, "get_current_job", lambda: mock_job)
        monkeypatch.setattr(lw, "update_enrichment_job", MagicMock())
        monkeypatch.setattr(
            lw, "geo_enrich",
            lambda ip: {
                "country": "United States",
                "city": "Mountain View",
                "region": "California",
                "isp": "Google LLC",
                "provider": "ipapi",
            },
        )

        result = run_enrichment_job(lead_id)
        assert result == "enriched"

        lead = asyncio.run(shared_repo.get_by_id(lead_id))
        assert lead is not None
        assert lead.geo_country == "United States"
        assert lead.geo_city == "Mountain View"

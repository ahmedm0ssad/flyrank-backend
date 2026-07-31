from unittest.mock import AsyncMock

import pytest

from app.main import app


@pytest.fixture(autouse=True)
def _reset_widget_repo():
    from app.services.widget_service import _get_repo

    repo = _get_repo()
    repo._widgets.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
async def webhook_widget():
    from app.models.widget import WidgetCreate
    from app.services import widget_service

    data = WidgetCreate(
        name="Router Webhook Widget",
        domain="https://webhook-submit.com",
        config={
            "brand_color": "#2563eb",
            "button_text": "Get a Quote",
            "fields": ["name", "email"],
            "success_message": "Thanks!",
            "webhook_url": "https://hooks.example.com/lead",
        },
    )
    return await widget_service.create_widget(
        data, "11111111-1111-1111-1111-111111111111"
    )


class TestSubmitReturns201DespiteWebhook:
    def test_webhook_failure_still_201(self, client, webhook_widget, monkeypatch):
        dispatch = AsyncMock(return_value=False)
        monkeypatch.setattr("app.services.lead_service.dispatch_webhook", dispatch)

        resp = client.post(
            f"/public/widget/{webhook_widget.id}/submit",
            json={"form_data": {"name": "John", "email": "john@test.com"}},
            headers={"Origin": "https://webhook-submit.com"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["lead_id"]

    def test_webhook_success_still_201(self, client, webhook_widget, monkeypatch):
        dispatch = AsyncMock(return_value=True)
        monkeypatch.setattr("app.services.lead_service.dispatch_webhook", dispatch)

        resp = client.post(
            f"/public/widget/{webhook_widget.id}/submit",
            json={"form_data": {"name": "Jane", "email": "jane@test.com"}},
            headers={"Origin": "https://webhook-submit.com"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["success"] is True
        assert body["lead_id"]

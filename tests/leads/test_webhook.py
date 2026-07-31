import asyncio
from unittest.mock import AsyncMock

import pytest

from app.models.lead import LeadSubmit
from app.services import lead_service

pytestmark = pytest.mark.usefixtures("mock_redis")

WEBHOOK_URL = "https://hooks.example.com/lead"


class FakeRequest:
    def __init__(
        self, ip="127.0.0.1", origin="https://myshop.com", ua="test-agent", referer=""
    ):
        self.client = type("obj", (object,), {"host": ip})()
        self.headers = {
            "origin": origin,
            "user-agent": ua,
            "referer": referer,
        }


@pytest.fixture
async def webhook_widget():
    from app.models.widget import WidgetCreate
    from app.services import widget_service

    data = WidgetCreate(
        name="Webhook Widget",
        domain="https://myshop.com",
        config={
            "brand_color": "#2563eb",
            "button_text": "Get a Quote",
            "fields": ["name", "email"],
            "success_message": "Thanks!",
            "webhook_url": WEBHOOK_URL,
        },
    )
    return await widget_service.create_widget(
        data, "11111111-1111-1111-1111-111111111111"
    )


class TestWebhookDispatch:
    @pytest.mark.asyncio
    async def test_success_dispatches_with_payload(self, webhook_widget, monkeypatch):
        dispatch = AsyncMock(return_value=True)
        monkeypatch.setattr("app.services.lead_service.dispatch_webhook", dispatch)

        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        request = FakeRequest()

        lead, was_dedup = await lead_service.submit_lead(
            str(webhook_widget.id), body, request
        )
        assert lead is not None
        assert was_dedup is False

        await asyncio.sleep(0)
        dispatch.assert_awaited_once()
        url, payload = dispatch.await_args.args
        assert url == WEBHOOK_URL
        assert set(payload) == {"lead_id", "widget_id", "form_data", "created_at"}
        assert payload["lead_id"] == str(lead.id)
        assert payload["widget_id"] == str(webhook_widget.id)
        assert payload["form_data"] == {"name": "John", "email": "john@test.com"}
        assert isinstance(payload["created_at"], str)

    @pytest.mark.asyncio
    async def test_webhook_failure_still_returns_lead(
        self, webhook_widget, monkeypatch
    ):
        dispatch = AsyncMock(return_value=False)
        monkeypatch.setattr("app.services.lead_service.dispatch_webhook", dispatch)

        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        request = FakeRequest()

        lead, _was_dedup = await lead_service.submit_lead(
            str(webhook_widget.id), body, request
        )
        assert lead is not None

        await asyncio.sleep(0)
        assert dispatch.await_count == 1

    @pytest.mark.asyncio
    async def test_no_webhook_url_no_dispatch(self, created_widget, monkeypatch):
        dispatch = AsyncMock(return_value=True)
        monkeypatch.setattr("app.services.lead_service.dispatch_webhook", dispatch)

        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        request = FakeRequest()

        lead, _was_dedup = await lead_service.submit_lead(
            str(created_widget.id), body, request
        )
        assert lead is not None

        await asyncio.sleep(0)
        dispatch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_webhook_url_disables_dispatch(self, monkeypatch):
        from app.models.widget import WidgetCreate
        from app.services import widget_service

        data = WidgetCreate(
            name="No Webhook",
            domain="https://myshop.com",
            config={
                "brand_color": "#2563eb",
                "button_text": "Get a Quote",
                "fields": ["name"],
                "webhook_url": "",
            },
        )
        widget = await widget_service.create_widget(
            data, "11111111-1111-1111-1111-111111111111"
        )

        dispatch = AsyncMock(return_value=True)
        monkeypatch.setattr("app.services.lead_service.dispatch_webhook", dispatch)

        body = LeadSubmit(form_data={"name": "John"})
        request = FakeRequest()

        lead, _was_dedup = await lead_service.submit_lead(str(widget.id), body, request)
        assert lead is not None

        await asyncio.sleep(0)
        dispatch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_honeypot_skips_dispatch(self, webhook_widget, monkeypatch):
        from app.services import widget_service

        dispatch = AsyncMock(return_value=True)
        monkeypatch.setattr("app.services.lead_service.dispatch_webhook", dispatch)

        raw = await widget_service._get_repo().get_by_id_raw(str(webhook_widget.id))
        honeypot_field = raw["config"].get("honeypot_field", "_hp_a3f9")

        body = LeadSubmit(
            form_data={
                "name": "Bot",
                "email": "bot@spam.com",
                honeypot_field: "filled by bot",
            }
        )
        request = FakeRequest()

        lead, _was_dedup = await lead_service.submit_lead(
            str(webhook_widget.id), body, request
        )
        assert lead is not None
        assert lead.honeypot_triggered is True

        await asyncio.sleep(0)
        dispatch.assert_not_awaited()

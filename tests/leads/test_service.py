import pytest
from fastapi import HTTPException

from app.models.lead import LeadSubmit
from app.services import lead_service

pytestmark = pytest.mark.usefixtures("mock_redis")


class FakeRequest:
    def __init__(self, ip="127.0.0.1", origin="https://myshop.com", ua="test-agent", referer=""):
        self.client = type("obj", (object,), {"host": ip})()
        self.headers = {
            "origin": origin,
            "user-agent": ua,
            "referer": referer,
        }


class TestSubmitLead:
    @pytest.mark.asyncio
    async def test_happy_path(self, created_widget):
        widget_id = str(created_widget.id)
        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        request = FakeRequest()

        lead, was_dedup = await lead_service.submit_lead(widget_id, body, request)
        assert lead is not None
        assert lead.status == "pending"
        assert lead.honeypot_triggered is False
        assert was_dedup is False

    @pytest.mark.asyncio
    async def test_honeypot_branch(self, created_widget):
        from app.services import widget_service
        from app.repositories.widget_repo import WidgetRepository

        widget_id = str(created_widget.id)

        raw = await widget_service._get_repo().get_by_id_raw(widget_id)
        honeypot_field = raw["config"].get("honeypot_field", "_hp_a3f9")

        body = LeadSubmit(form_data={
            "name": "Bot",
            "email": "bot@spam.com",
            honeypot_field: "filled by bot",
        })
        request = FakeRequest()

        lead, was_dedup = await lead_service.submit_lead(widget_id, body, request)
        assert lead is not None
        assert lead.honeypot_triggered is True
        assert lead.spam_score == 1.0
        assert lead.spam_reasons == ["honeypot"]
        assert was_dedup is False

    @pytest.mark.asyncio
    async def test_spam_high_branch(self, created_widget):
        widget_id = str(created_widget.id)
        body = LeadSubmit(form_data={
            "name": "John",
            "email": "john@mailinator.com",
            "message": "https://spam.com/buy-now",
        })
        request = FakeRequest()

        lead, was_dedup = await lead_service.submit_lead(widget_id, body, request)
        assert lead is not None
        assert lead.honeypot_triggered is False
        assert lead.spam_score >= 0.5
        assert len(lead.spam_reasons or []) > 0

    @pytest.mark.asyncio
    async def test_dedup_branch(self, created_widget):
        widget_id = str(created_widget.id)
        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        request = FakeRequest()

        lead1, was_dedup1 = await lead_service.submit_lead(widget_id, body, request)
        assert was_dedup1 is False

        lead2, was_dedup2 = await lead_service.submit_lead(widget_id, body, request)
        assert was_dedup2 is True
        assert str(lead2.id) == str(lead1.id)

    @pytest.mark.asyncio
    async def test_widget_not_found(self):
        body = LeadSubmit(form_data={"name": "John"})
        request = FakeRequest()

        with pytest.raises(HTTPException) as exc:
            await lead_service.submit_lead(
                "00000000-0000-0000-0000-000000000000", body, request
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_origin_mismatch(self, created_widget):
        widget_id = str(created_widget.id)
        body = LeadSubmit(form_data={"name": "John"})
        request = FakeRequest(origin="https://evil.com")

        with pytest.raises(HTTPException) as exc:
            await lead_service.submit_lead(widget_id, body, request)
        assert exc.value.status_code == 403

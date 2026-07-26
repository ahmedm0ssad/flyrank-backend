import io
import json
import logging
import re

import pytest

from app.models.lead import LeadSubmit

pytestmark = pytest.mark.usefixtures("mock_redis")


class FakeRequest:
    def __init__(self, ip="127.0.0.1", origin="https://myshop.com", ua="test-agent", referer=""):
        self.client = type("obj", (object,), {"host": ip})()
        self.headers = {
            "origin": origin,
            "user-agent": ua,
            "referer": referer,
        }


@pytest.fixture
def audit_capture():
    logger = logging.getLogger("app.audit.submission")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    old_handlers = logger.handlers[:]
    old_level = logger.level
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    yield stream
    logger.handlers.clear()
    for h in old_handlers:
        logger.addHandler(h)
    logger.setLevel(old_level)


def _parse_log_entries(stream: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in stream.getvalue().strip().splitlines() if line.strip()]


class TestAuditLogging:
    @pytest.mark.asyncio
    async def test_success_outcome_logged(self, created_widget, audit_capture):
        from app.services.lead_service import submit_lead

        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        request = FakeRequest()
        lead, _ = await submit_lead(str(created_widget.id), body, request)

        entries = _parse_log_entries(audit_capture)
        success_entries = [e for e in entries if e["outcome"] == "success"]
        assert len(success_entries) >= 1
        entry = success_entries[-1]
        assert entry["widget_id"] == str(created_widget.id)
        assert entry["ip"] == "127.0.0.1"
        assert "fingerprint" in entry
        assert entry["lead_id"] == str(lead.id)

    @pytest.mark.asyncio
    async def test_honeypot_outcome_logged(self, created_widget, audit_capture):
        from app.services.lead_service import submit_lead

        widget_id = str(created_widget.id)
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(widget_id)
        honeypot_field = raw["config"].get("honeypot_field", "_hp_a3f9")

        body = LeadSubmit(form_data={
            "name": "Bot",
            "email": "bot@spam.com",
            honeypot_field: "filled by bot",
        })
        request = FakeRequest()
        lead, _ = await submit_lead(widget_id, body, request)

        entries = _parse_log_entries(audit_capture)
        hp_entries = [e for e in entries if e["outcome"] == "honeypot"]
        assert len(hp_entries) >= 1
        entry = hp_entries[-1]
        assert entry["lead_id"] == str(lead.id)

    @pytest.mark.asyncio
    async def test_fingerprint_dedup_outcome_logged(self, created_widget, audit_capture):
        from app.services.lead_service import submit_lead

        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        request = FakeRequest()

        lead1, _ = await submit_lead(str(created_widget.id), body, request)
        lead2, was_dedup = await submit_lead(str(created_widget.id), body, request)
        assert was_dedup is True

        entries = _parse_log_entries(audit_capture)
        dedup_entries = [e for e in entries if e["outcome"] == "fingerprint_dedup"]
        assert len(dedup_entries) >= 1
        entry = dedup_entries[-1]
        assert entry["existing_lead_id"] == str(lead1.id)

    @pytest.mark.asyncio
    async def test_rate_limited_outcome_logged(self, created_widget, audit_capture, monkeypatch):
        from app.services.lead_service import submit_lead
        from fastapi import HTTPException

        async def always_blocked(*args, **kwargs):
            return 60

        monkeypatch.setattr("app.services.lead_service.check_rate_limits", always_blocked)

        body = LeadSubmit(form_data={"name": "John"})
        request = FakeRequest()

        with pytest.raises(HTTPException) as exc:
            await submit_lead(str(created_widget.id), body, request)
        assert exc.value.status_code == 429

        entries = _parse_log_entries(audit_capture)
        rl_entries = [e for e in entries if e["outcome"] == "rate_limited"]
        assert len(rl_entries) >= 1
        assert rl_entries[-1]["retry_after"] == 60

    @pytest.mark.asyncio
    async def test_origin_rejected_outcome_logged(self, created_widget, audit_capture):
        from app.services.lead_service import submit_lead
        from fastapi import HTTPException

        body = LeadSubmit(form_data={"name": "John"})
        request = FakeRequest(origin="https://evil.com")

        with pytest.raises(HTTPException) as exc:
            await submit_lead(str(created_widget.id), body, request)
        assert exc.value.status_code == 403

        entries = _parse_log_entries(audit_capture)
        origin_entries = [e for e in entries if e["outcome"] == "origin_rejected"]
        assert len(origin_entries) >= 1
        assert origin_entries[-1]["widget_id"] == str(created_widget.id)

    @pytest.mark.asyncio
    async def test_spam_flagged_outcome_logged(self, created_widget, audit_capture):
        from app.services.lead_service import submit_lead

        body = LeadSubmit(form_data={
            "name": "John",
            "email": "john@mailinator.com",
            "message": "https://spam.com/buy-now",
        })
        request = FakeRequest()
        lead, _ = await submit_lead(str(created_widget.id), body, request)

        entries = _parse_log_entries(audit_capture)
        spam_entries = [e for e in entries if e["outcome"] == "spam_flagged"]
        assert len(spam_entries) >= 1
        entry = spam_entries[-1]
        assert entry["lead_id"] == str(lead.id)
        assert entry["spam_score"] >= 0.5

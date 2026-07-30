from datetime import date

import pytest
from fastapi import HTTPException

from app.models.lead import LeadSubmit
from app.services import lead_service

pytestmark = pytest.mark.usefixtures("mock_redis")


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

        widget_id = str(created_widget.id)

        raw = await widget_service._get_repo().get_by_id_raw(widget_id)
        honeypot_field = raw["config"].get("honeypot_field", "_hp_a3f9")

        body = LeadSubmit(
            form_data={
                "name": "Bot",
                "email": "bot@spam.com",
                honeypot_field: "filled by bot",
            }
        )
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
        body = LeadSubmit(
            form_data={
                "name": "John",
                "email": "john@mailinator.com",
                "message": "https://spam.com/buy-now",
            }
        )
        request = FakeRequest()

        lead, _was_dedup = await lead_service.submit_lead(widget_id, body, request)
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
    async def test_enqueue_failure_logs_warning(self, created_widget, monkeypatch):
        from unittest.mock import MagicMock

        fake_logger = MagicMock()
        monkeypatch.setattr("app.services.lead_service.logger", fake_logger)
        monkeypatch.setattr(
            "app.core.queue.create_enrichment_job",
            MagicMock(side_effect=Exception("enqueue failed")),
        )

        widget_id = str(created_widget.id)
        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        request = FakeRequest()

        lead, _was_dedup = await lead_service.submit_lead(widget_id, body, request)
        assert lead is not None
        fake_logger.warning.assert_called_once()
        exc_arg = fake_logger.warning.call_args[0][2]
        assert "enqueue failed" in str(exc_arg)

    @pytest.mark.asyncio
    async def test_honeypot_skips_heuristic_scoring(self, created_widget, monkeypatch):
        from app.services import widget_service

        def failing_score(form_data):
            raise RuntimeError(
                "score_submission should not be called when honeypot triggered"
            )

        monkeypatch.setattr("app.services.lead_service.score_submission", failing_score)

        widget_id = str(created_widget.id)
        raw = await widget_service._get_repo().get_by_id_raw(widget_id)
        honeypot_field = raw["config"].get("honeypot_field", "_hp_a3f9")

        body = LeadSubmit(
            form_data={
                "name": "Bot",
                "email": "bot@spam.com",
                honeypot_field: "filled by bot",
            }
        )
        request = FakeRequest()

        lead, was_dedup = await lead_service.submit_lead(widget_id, body, request)
        assert lead is not None
        assert lead.honeypot_triggered is True
        assert lead.spam_score == 1.0
        assert lead.spam_reasons == ["honeypot"]
        assert was_dedup is False

    @pytest.mark.asyncio
    async def test_origin_mismatch(self, created_widget):
        widget_id = str(created_widget.id)
        body = LeadSubmit(form_data={"name": "John"})
        request = FakeRequest(origin="https://evil.com")

        with pytest.raises(HTTPException) as exc:
            await lead_service.submit_lead(widget_id, body, request)
        assert exc.value.status_code == 403


class TestDashboardService:
    @pytest.mark.asyncio
    async def test_get_leads(self, created_widget):
        widget_id = str(created_widget.id)
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(widget_id)
        tenant_id = str(raw["tenant_id"])

        _items, total = await lead_service.get_leads(
            widget_id=widget_id,
            tenant_id=tenant_id,
        )
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_all_leads(self, created_widget):
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(str(created_widget.id))
        tenant_id = str(raw["tenant_id"])

        _items, total = await lead_service.get_all_leads(tenant_id=tenant_id)
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_lead_detail_not_found(self, created_widget):
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(str(created_widget.id))
        tenant_id = str(raw["tenant_id"])

        result = await lead_service.get_lead_detail(
            lead_id="00000000-0000-0000-0000-000000000000",
            widget_id=str(created_widget.id),
            tenant_id=tenant_id,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_widget_stats_honeypot_excluded(self, created_widget):
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(str(created_widget.id))
        tenant_id = str(raw["tenant_id"])
        widget_id = str(created_widget.id)

        lead_service._get_or_create_repo()
        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        request = FakeRequest()
        await lead_service.submit_lead(widget_id, body, request)

        hp_body = LeadSubmit(
            form_data={
                "name": "Bot",
                "email": "bot@spam.com",
                raw["config"]["honeypot_field"]: "value",
            }
        )
        await lead_service.submit_lead(widget_id, hp_body, request)

        stats = await lead_service.get_widget_stats(
            widget_id, tenant_id, skip_cache=True
        )
        assert stats["total_leads"] == 1
        assert stats["honeypot_blocked"] == 1

    @pytest.mark.asyncio
    async def test_get_tenant_stats_cross_widget(self, created_widget):
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(str(created_widget.id))
        tenant_id = str(raw["tenant_id"])

        stats = await lead_service.get_tenant_stats(tenant_id, skip_cache=True)
        assert stats["total_leads"] == 0

    @pytest.mark.asyncio
    async def test_export_csv(self, created_widget):
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(str(created_widget.id))
        tenant_id = str(raw["tenant_id"])
        widget_id = str(created_widget.id)

        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        request = FakeRequest()
        await lead_service.submit_lead(widget_id, body, request)

        csv_content, truncated = await lead_service.export_csv(
            widget_id=widget_id,
            tenant_id=tenant_id,
        )
        assert "John" in csv_content
        assert "john@test.com" in csv_content
        assert csv_content.startswith("id,")
        assert not truncated

    @pytest.mark.asyncio
    async def test_export_csv_with_date_filter(self, created_widget):
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(str(created_widget.id))
        tenant_id = str(raw["tenant_id"])
        widget_id = str(created_widget.id)

        body = LeadSubmit(form_data={"name": "John"})
        request = FakeRequest()
        await lead_service.submit_lead(widget_id, body, request)

        csv_content, truncated = await lead_service.export_csv(
            widget_id=widget_id,
            tenant_id=tenant_id,
            date_from=date(2099, 1, 1),
        )
        assert len(csv_content.splitlines()) == 1
        assert not truncated

    @pytest.mark.asyncio
    async def test_delete_lead(self, created_widget):
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(str(created_widget.id))
        tenant_id = str(raw["tenant_id"])
        widget_id = str(created_widget.id)

        body = LeadSubmit(form_data={"name": "John"})
        request = FakeRequest()
        lead, _ = await lead_service.submit_lead(widget_id, body, request)

        result = await lead_service.delete_lead(str(lead.id), widget_id, tenant_id)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_lead_not_found(self, created_widget):
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(str(created_widget.id))
        tenant_id = str(raw["tenant_id"])

        result = await lead_service.delete_lead(
            "00000000-0000-0000-0000-000000000000",
            str(created_widget.id),
            tenant_id,
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_batch_delete_leads(self, created_widget):
        from app.services import widget_service

        raw = await widget_service._get_repo().get_by_id_raw(str(created_widget.id))
        tenant_id = str(raw["tenant_id"])
        widget_id = str(created_widget.id)

        ids = []
        repo = lead_service._get_or_create_repo()
        for i in range(3):
            lead = await repo.create(
                widget_id=widget_id,
                tenant_id=tenant_id,
                form_data={"name": f"User {i}"},
                ip_address="1.1.1.1",
                fingerprint=f"fp-batch-{i}",
            )
            ids.append(str(lead.id))

        count = await lead_service.batch_delete_leads(ids, widget_id, tenant_id)
        assert count == 3

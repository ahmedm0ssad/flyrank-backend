import pytest
from pydantic import ValidationError

from app.models.lead import BatchDeleteRequest, LeadResponse, LeadSubmit


class TestLeadSubmit:
    def test_valid_submission(self):
        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        assert body.form_data["name"] == "John"

    def test_empty_form_data_rejected(self):
        with pytest.raises(ValidationError):
            LeadSubmit(form_data={})

    def test_non_dict_form_data_rejected(self):
        with pytest.raises(ValidationError):
            LeadSubmit(form_data="not-a-dict")

    def test_field_length_exceeds_limit(self):
        with pytest.raises(ValidationError):
            LeadSubmit(form_data={"name": "x" * 2001})

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            LeadSubmit(form_data={"name": "John", "email": "not-an-email"})

    def test_valid_email_accepted(self):
        body = LeadSubmit(form_data={"name": "John", "email": "john@example.com"})
        assert body.form_data["email"] == "john@example.com"

    def test_invalid_phone_rejected(self):
        with pytest.raises(ValidationError):
            LeadSubmit(form_data={"name": "John", "phone": "abc"})

    def test_valid_phone_accepted(self):
        body = LeadSubmit(form_data={"name": "John", "phone": "+1234567890"})
        assert body.form_data["phone"] == "+1234567890"


class TestLeadResponse:
    def test_response_fields(self):
        import uuid
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        lead = LeadResponse(
            id=uuid.uuid4(),
            widget_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            form_data={"name": "John"},
            ip_address="192.168.1.1",
            fingerprint="abc123",
            status="pending",
            created_at=now,
            updated_at=now,
        )
        data = lead.model_dump()
        assert data["status"] == "pending"
        assert data["honeypot_triggered"] is False
        assert data["spam_score"] == 0.0


class TestBatchDeleteRequest:
    def test_valid_ids(self):
        import uuid

        req = BatchDeleteRequest(lead_ids=[uuid.uuid4(), uuid.uuid4()])
        assert len(req.lead_ids) == 2

    def test_empty_ids_allowed_by_model(self):

        req = BatchDeleteRequest(lead_ids=[])
        assert len(req.lead_ids) == 0


class TestLeadSubmitEdgeCases:
    def test_referer_exceeds_limit(self):
        with pytest.raises(ValidationError):
            LeadSubmit(form_data={"name": "John"}, referer="x" * 501)

    def test_nested_dict_in_form_data_rejected(self):
        with pytest.raises(ValidationError):
            LeadSubmit(form_data={"name": {"first": "John"}})

    def test_injection_in_form_data_key(self):
        body = LeadSubmit(form_data={"<script>alert(1)</script>": "value"})
        assert "<script>alert(1)</script>" in body.form_data

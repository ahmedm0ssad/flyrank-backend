import pytest
from pydantic import ValidationError

from app.models.widget import WidgetCreate, WidgetResponse, WidgetUpdate


class TestWidgetCreate:
    def test_valid_minimal(self):
        w = WidgetCreate(name="Test", domain="https://example.com")
        assert w.name == "Test"
        assert w.domain == "https://example.com"
        assert w.config["brand_color"] == "#2563eb"

    def test_valid_with_config(self):
        w = WidgetCreate(
            name="My Form",
            domain="https://myshop.com",
            config={
                "brand_color": "#ff0000",
                "button_text": "Submit",
                "fields": ["name", "email"],
                "success_message": "Thanks!",
            },
        )
        assert w.config["brand_color"] == "#ff0000"
        assert w.config["button_text"] == "Submit"

    def test_wildcard_domain_accepted(self):
        w = WidgetCreate(name="Test", domain="https://*.myshop.com")
        assert w.domain == "https://*.myshop.com"

    def test_invalid_domain_no_protocol(self):
        with pytest.raises(ValidationError):
            WidgetCreate(name="Test", domain="myshop.com")

    def test_invalid_domain_empty(self):
        with pytest.raises(ValidationError):
            WidgetCreate(name="Test", domain="")

    def test_invalid_brand_color(self):
        with pytest.raises(ValidationError):
            WidgetCreate(
                name="Test",
                domain="https://example.com",
                config={"brand_color": "not-a-color"},
            )

    def test_invalid_button_text_too_long(self):
        with pytest.raises(ValidationError, match="button_text must not exceed"):
            WidgetCreate(
                name="Test",
                domain="https://example.com",
                config={"brand_color": "#2563eb", "button_text": "x" * 101},
            )

    def test_invalid_fields_empty(self):
        with pytest.raises(ValidationError, match="fields must be a non-empty list"):
            WidgetCreate(
                name="Test",
                domain="https://example.com",
                config={"brand_color": "#2563eb", "fields": []},
            )

    def test_fields_not_a_list_rejected(self):
        with pytest.raises(ValidationError, match="fields must be a non-empty list"):
            WidgetCreate(
                name="Test",
                domain="https://example.com",
                config={"brand_color": "#2563eb", "fields": "not_a_list"},
            )

    def test_fields_none_rejected(self):
        with pytest.raises(ValidationError, match="fields must be a non-empty list"):
            WidgetCreate(
                name="Test",
                domain="https://example.com",
                config={"brand_color": "#2563eb", "fields": None},
            )

    def test_valid_https_webhook_url(self):
        w = WidgetCreate(
            name="Test",
            domain="https://example.com",
            config={
                "brand_color": "#2563eb",
                "fields": ["name"],
                "webhook_url": "https://hooks.example.com/lead",
            },
        )
        assert w.config["webhook_url"] == "https://hooks.example.com/lead"

    def test_empty_webhook_url_disables_feature(self):
        w = WidgetCreate(
            name="Test",
            domain="https://example.com",
            config={"brand_color": "#2563eb", "fields": ["name"], "webhook_url": ""},
        )
        assert w.config["webhook_url"] == ""

    def test_non_https_webhook_url_rejected(self):
        with pytest.raises(ValidationError, match="webhook_url must be an HTTPS"):
            WidgetCreate(
                name="Test",
                domain="https://example.com",
                config={
                    "brand_color": "#2563eb",
                    "fields": ["name"],
                    "webhook_url": "http://hooks.example.com/lead",
                },
            )

    def test_malformed_webhook_url_rejected(self):
        with pytest.raises(ValidationError, match="webhook_url must be an HTTPS"):
            WidgetCreate(
                name="Test",
                domain="https://example.com",
                config={
                    "brand_color": "#2563eb",
                    "fields": ["name"],
                    "webhook_url": "hooks.example.com/lead",
                },
            )

    def test_webhook_url_without_host_rejected(self):
        with pytest.raises(ValidationError, match="webhook_url must include a host"):
            WidgetCreate(
                name="Test",
                domain="https://example.com",
                config={
                    "brand_color": "#2563eb",
                    "fields": ["name"],
                    "webhook_url": "https://",
                },
            )


class TestWidgetUpdate:
    def test_valid_partial_update(self):
        u = WidgetUpdate(name="Updated")
        assert u.name == "Updated"
        assert u.domain is None


class TestWidgetResponse:
    def test_serialization(self):
        import uuid
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        w = WidgetResponse(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            name="Test",
            domain="https://example.com",
            config={"brand_color": "#000"},
            js_version=1,
            active=True,
            created_at=now,
            updated_at=now,
        )
        data = w.model_dump()
        assert data["name"] == "Test"
        assert data["js_version"] == 1
        assert data["active"] is True

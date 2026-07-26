import re
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _validate_config(config: dict) -> dict:
    brand_color = config.get("brand_color", "#2563eb")
    if not _HEX_COLOR_RE.match(str(brand_color)):
        raise ValueError("brand_color must be a valid hex color (e.g. #2563eb)")

    button_text = config.get("button_text", "Get a Quote")
    if not isinstance(button_text, str) or not (1 <= len(button_text) <= 100):
        raise ValueError("button_text must be 1–100 characters")

    fields = config.get("fields", ["name", "email"])
    if not isinstance(fields, list) or not (1 <= len(fields) <= 20):
        raise ValueError("fields must be an array of 1–20 items")
    for f in fields:
        if not isinstance(f, str) or not (2 <= len(f) <= 50):
            raise ValueError("each field name must be 2–50 characters")

    success_message = config.get("success_message", "Thanks!")
    if not isinstance(success_message, str) or not (1 <= len(success_message) <= 500):
        raise ValueError("success_message must be 1–500 characters")

    filtered = {
        "brand_color": brand_color,
        "button_text": button_text,
        "fields": fields,
        "success_message": success_message,
    }
    if "honeypot_field" in config:
        filtered["honeypot_field"] = config["honeypot_field"]

    return filtered


def _validate_domain(domain: str) -> str:
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("domain is required")

    if not (domain.startswith("http://") or domain.startswith("https://")):
        raise ValueError("domain must include protocol (http:// or https://)")

    from urllib.parse import urlparse

    parsed = urlparse(domain)
    host = parsed.hostname
    if not host:
        raise ValueError("domain must be a valid URL")

    if host.startswith("*."):
        base = host[2:]
        if not base or "." not in base:
            raise ValueError("invalid wildcard domain pattern")
    else:
        if "." not in host:
            raise ValueError("domain must contain a valid hostname")

    if len(domain) > 500:
        raise ValueError("domain must not exceed 500 characters")

    return domain


class WidgetConfig(BaseModel):
    brand_color: str = "#2563eb"
    button_text: str = "Get a Quote"
    fields: list[str] = ["name", "email"]
    success_message: str = "Thanks!"
    honeypot_field: str | None = None


class WidgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    domain: str = Field(...)
    config: dict[str, Any] = Field(default_factory=lambda: {
        "brand_color": "#2563eb",
        "button_text": "Get a Quote",
        "fields": ["name", "email"],
        "success_message": "Thanks!",
    })

    @model_validator(mode="after")
    def _validate(self):
        self.config = _validate_config(self.config)
        self.domain = _validate_domain(self.domain)
        return self


class WidgetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    domain: str | None = None
    config: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate(self):
        if self.config is not None:
            self.config = _validate_config(self.config)
        if self.domain is not None:
            self.domain = _validate_domain(self.domain)
        return self


class WidgetResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    domain: str
    config: dict[str, Any]
    js_version: int
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list[WidgetResponse]
    total: int
    page: int
    page_size: int
    pages: int

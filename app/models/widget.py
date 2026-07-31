import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class WidgetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    domain: str = Field(..., min_length=1)
    config: dict[str, Any] = Field(
        default_factory=lambda: {
            "brand_color": "#2563eb",
            "button_text": "Get a Quote",
            "fields": ["name", "email"],
            "success_message": "Thanks!",
        }
    )

    @field_validator("domain")
    @classmethod
    def domain_must_have_protocol(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("domain must start with http:// or https://")
        return v

    @model_validator(mode="after")
    def validate_config(self) -> "WidgetCreate":
        config = self.config
        brand_color = config.get("brand_color", "")
        if not re.match(r"^#[0-9a-fA-F]{6}$", brand_color):
            raise ValueError("brand_color must be a valid hex color (e.g. #2563eb)")

        button_text = config.get("button_text", "")
        if len(button_text) > 100:
            raise ValueError("button_text must not exceed 100 characters")

        fields = config.get("fields", [])
        if not isinstance(fields, list) or len(fields) == 0:
            raise ValueError("fields must be a non-empty list")

        webhook_url = config.get("webhook_url")
        if webhook_url:
            if not isinstance(webhook_url, str) or not webhook_url.startswith(
                "https://"
            ):
                raise ValueError(
                    "webhook_url must be an HTTPS URL starting with https://"
                )
            if not urlparse(webhook_url).netloc:
                raise ValueError("webhook_url must include a host")

        return self


class WidgetUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    domain: str | None = None
    config: dict[str, Any] | None = None


class WidgetResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    domain: str
    config: dict[str, Any]
    js_version: int
    active: bool
    created_at: datetime


class PaginatedResponse(BaseModel):
    items: list[WidgetResponse]
    total: int
    page: int
    page_size: int
    pages: int

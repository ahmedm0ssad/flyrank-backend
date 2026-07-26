import html
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[1-9]\d{6,14}$")


def _sanitize(value: str) -> str:
    return html.escape(value.strip(), quote=True)


class LeadSubmit(BaseModel):
    form_data: dict[str, Any]
    referer: str | None = Field(None, max_length=500)

    @model_validator(mode="after")
    def _validate(self):
        fd = self.form_data
        if not isinstance(fd, dict) or not fd:
            raise ValueError("form_data must be a non-empty object")

        for k, v in fd.items():
            if not isinstance(v, str):
                raise ValueError(f"form_data field '{k}' must be a string")
            if len(v) > 2000:
                raise ValueError(f"form_data field '{k}' exceeds 2000 characters")
            fd[k] = _sanitize(v)

        email = fd.get("email")
        if email and not _EMAIL_RE.match(email):
            raise ValueError("invalid email format")

        phone = fd.get("phone")
        if phone and not _PHONE_RE.match(phone):
            raise ValueError("invalid phone format")

        return self


class LeadResponse(BaseModel):
    id: UUID
    widget_id: UUID
    tenant_id: UUID
    form_data: dict[str, Any]
    ip_address: str
    user_agent: str | None = None
    referer: str | None = None
    fingerprint: str
    geo_country: str | None = None
    geo_city: str | None = None
    geo_region: str | None = None
    geo_isp: str | None = None
    geo_provider: str | None = None
    spam_score: float = 0.0
    spam_reasons: list[str] | None = None
    honeypot_triggered: bool = False
    status: str = "pending"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

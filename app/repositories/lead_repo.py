import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.lead import LeadResponse


class LeadRepository:
    def __init__(self):
        self._leads: dict[str, dict] = {}

    async def create(
        self,
        widget_id: str,
        tenant_id: str,
        form_data: dict[str, Any],
        ip_address: str,
        fingerprint: str,
        user_agent: str | None = None,
        referer: str | None = None,
        spam_score: float = 0.0,
        spam_reasons: list[str] | None = None,
        honeypot_triggered: bool = False,
        status: str = "pending",
    ) -> LeadResponse:
        now = datetime.now(timezone.utc)
        lead_id = str(uuid.uuid4())
        record = {
            "id": lead_id,
            "widget_id": widget_id,
            "tenant_id": tenant_id,
            "form_data": copy.deepcopy(form_data),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "referer": referer,
            "fingerprint": fingerprint,
            "geo_country": None,
            "geo_city": None,
            "geo_region": None,
            "geo_isp": None,
            "geo_provider": None,
            "spam_score": spam_score,
            "spam_reasons": spam_reasons,
            "honeypot_triggered": honeypot_triggered,
            "status": status,
            "created_at": now,
            "updated_at": now,
        }
        self._leads[lead_id] = record
        return self._row_to_response(record)

    async def get_by_id(self, lead_id: str) -> LeadResponse | None:
        record = self._leads.get(lead_id)
        if record is None:
            return None
        return self._row_to_response(record)

    async def list_by_widget(
        self,
        widget_id: str,
        tenant_id: str,
        include_honeypot: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[LeadResponse], int]:
        records = [
            r
            for r in self._leads.values()
            if r["widget_id"] == widget_id and r["tenant_id"] == tenant_id
        ]
        if not include_honeypot:
            records = [r for r in records if not r["honeypot_triggered"]]

        records.sort(key=lambda r: r["created_at"], reverse=True)
        total = len(records)

        start = (page - 1) * page_size
        end = start + page_size
        page_records = records[start:end]

        items = [self._row_to_response(r) for r in page_records]
        return items, total

    async def list_by_tenant(
        self,
        tenant_id: str,
        include_honeypot: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[LeadResponse], int]:
        records = [r for r in self._leads.values() if r["tenant_id"] == tenant_id]
        if not include_honeypot:
            records = [r for r in records if not r["honeypot_triggered"]]

        records.sort(key=lambda r: r["created_at"], reverse=True)
        total = len(records)

        start = (page - 1) * page_size
        end = start + page_size
        page_records = records[start:end]

        items = [self._row_to_response(r) for r in page_records]
        return items, total

    async def update_status(
        self, lead_id: str, status: str, **extra
    ) -> LeadResponse | None:
        record = self._leads.get(lead_id)
        if record is None:
            return None
        record["status"] = status
        record["updated_at"] = datetime.now(timezone.utc)
        for k, v in extra.items():
            if v is not None:
                record[k] = v
        return self._row_to_response(record)

    async def delete(self, lead_id: str, widget_id: str, tenant_id: str) -> bool:
        record = self._leads.get(lead_id)
        if (
            record is None
            or record["widget_id"] != widget_id
            or record["tenant_id"] != tenant_id
        ):
            return False
        del self._leads[lead_id]
        return True

    async def batch_delete(
        self, lead_ids: list[str], widget_id: str, tenant_id: str
    ) -> int:
        count = 0
        for lid in lead_ids:
            if await self.delete(lid, widget_id, tenant_id):
                count += 1
        return count

    def _row_to_response(self, record: dict) -> LeadResponse:
        return LeadResponse(
            id=record["id"],
            widget_id=record["widget_id"],
            tenant_id=record["tenant_id"],
            form_data=copy.deepcopy(record["form_data"]),
            ip_address=record["ip_address"],
            user_agent=record.get("user_agent"),
            referer=record.get("referer"),
            fingerprint=record["fingerprint"],
            geo_country=record.get("geo_country"),
            geo_city=record.get("geo_city"),
            geo_region=record.get("geo_region"),
            geo_isp=record.get("geo_isp"),
            geo_provider=record.get("geo_provider"),
            spam_score=record.get("spam_score", 0.0),
            spam_reasons=record.get("spam_reasons"),
            honeypot_triggered=record.get("honeypot_triggered", False),
            status=record.get("status", "pending"),
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

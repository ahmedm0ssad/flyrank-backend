import copy
import uuid
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.models.lead import LeadResponse

_SEARCH_FIELDS = ["name", "email", "phone", "message", "company"]


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
        search: str | None = None,
        status: str | None = None,
        spam_min: float | None = None,
        spam_max: float | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[LeadResponse], int]:
        records = [
            r
            for r in self._leads.values()
            if r["widget_id"] == widget_id and r["tenant_id"] == tenant_id
        ]
        return self._apply_filters_and_paginate(
            records, include_honeypot, page, page_size,
            search, status, spam_min, spam_max,
            date_from, date_to, sort_by, sort_order,
        )

    async def list_by_tenant(
        self,
        tenant_id: str,
        include_honeypot: bool = False,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        status: str | None = None,
        spam_min: float | None = None,
        spam_max: float | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[LeadResponse], int]:
        records = [r for r in self._leads.values() if r["tenant_id"] == tenant_id]
        return self._apply_filters_and_paginate(
            records, include_honeypot, page, page_size,
            search, status, spam_min, spam_max,
            date_from, date_to, sort_by, sort_order,
        )

    async def get_stats(
        self, widget_id: str, tenant_id: str
    ) -> dict[str, Any]:
        records = [
            r for r in self._leads.values()
            if r["widget_id"] == widget_id and r["tenant_id"] == tenant_id
        ]
        return self._compute_stats(records)

    async def get_tenant_stats(
        self, tenant_id: str
    ) -> dict[str, Any]:
        records = [
            r for r in self._leads.values()
            if r["tenant_id"] == tenant_id
        ]
        return self._compute_stats(records)

    async def get_export_data(
        self,
        widget_id: str,
        tenant_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        records = [
            r for r in self._leads.values()
            if r["widget_id"] == widget_id and r["tenant_id"] == tenant_id
        ]
        if date_from:
            dt = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
            records = [r for r in records if r["created_at"] >= dt]
        if date_to:
            dt = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc)
            records = [r for r in records if r["created_at"] <= dt]
        records.sort(key=lambda r: r["created_at"], reverse=True)
        return [self._row_to_response(r).model_dump() for r in records]

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

    def _apply_filters_and_paginate(
        self,
        records: list[dict],
        include_honeypot: bool,
        page: int,
        page_size: int,
        search: str | None,
        status: str | None,
        spam_min: float | None,
        spam_max: float | None,
        date_from: date | None,
        date_to: date | None,
        sort_by: str,
        sort_order: str,
    ) -> tuple[list[LeadResponse], int]:
        if not include_honeypot:
            records = [r for r in records if not r["honeypot_triggered"]]

        if search:
            q = search.lower()
            records = [
                r for r in records
                if any(
                    q in str(r["form_data"].get(f, "")).lower()
                    for f in _SEARCH_FIELDS
                )
            ]

        if status:
            records = [r for r in records if r["status"] == status]

        if spam_min is not None:
            records = [r for r in records if r["spam_score"] >= spam_min]
        if spam_max is not None:
            records = [r for r in records if r["spam_score"] <= spam_max]

        if date_from:
            dt = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
            records = [r for r in records if r["created_at"] >= dt]
        if date_to:
            dt = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc)
            records = [r for r in records if r["created_at"] <= dt]

        reverse = sort_order.lower() != "asc"
        records.sort(key=lambda r: r.get(sort_by, r["created_at"]), reverse=reverse)

        total = len(records)
        start = (page - 1) * page_size
        end = start + page_size
        page_records = records[start:end]
        items = [self._row_to_response(r) for r in page_records]
        return items, total

    def _compute_stats(self, records: list[dict]) -> dict[str, Any]:
        all_records = records
        non_honeypot = [r for r in records if not r["honeypot_triggered"]]

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_leads = len(non_honeypot)
        today = sum(1 for r in non_honeypot if r["created_at"] >= today_start)
        week_start = today_start - timedelta(days=today_start.weekday())
        this_week = sum(1 for r in non_honeypot if r["created_at"] >= week_start)
        month_start = today_start.replace(day=1)
        this_month = sum(1 for r in non_honeypot if r["created_at"] >= month_start)

        spam_scores = [r["spam_score"] for r in non_honeypot]
        avg_spam_score = (
            sum(spam_scores) / len(spam_scores) if spam_scores else 0.0
        )

        honeypot_blocked = sum(1 for r in all_records if r["honeypot_triggered"])

        country_counts: Counter = Counter()
        for r in all_records:
            c = r.get("geo_country")
            if c:
                country_counts[c] += 1
        top_countries = [
            {"country": c, "count": n}
            for c, n in country_counts.most_common(10)
        ]

        thirty_days_ago = now - timedelta(days=30)
        daily_counts: Counter = Counter()
        for r in non_honeypot:
            if r["created_at"] >= thirty_days_ago:
                day_key = r["created_at"].strftime("%Y-%m-%d")
                daily_counts[day_key] += 1
        leads_over_time = [
            {"date": d, "count": n}
            for d, n in sorted(daily_counts.items())
        ]

        return {
            "total_leads": total_leads,
            "today": today,
            "this_week": this_week,
            "this_month": this_month,
            "avg_spam_score": round(avg_spam_score, 4),
            "honeypot_blocked": honeypot_blocked,
            "top_countries": top_countries,
            "leads_over_time": leads_over_time,
        }

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

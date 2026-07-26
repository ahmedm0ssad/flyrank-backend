import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.widget import WidgetResponse


class WidgetRepository:
    def __init__(self):
        self._widgets: dict[str, dict] = {}
        self._seed()

    def _seed(self):
        pass

    async def create(
        self,
        name: str,
        domain: str,
        config: dict[str, Any],
        tenant_id: str,
    ) -> WidgetResponse:
        now = datetime.now(timezone.utc)
        widget_id = str(uuid.uuid4())
        record = {
            "id": widget_id,
            "tenant_id": tenant_id,
            "name": name,
            "domain": domain,
            "config": copy.deepcopy(config),
            "js_version": 1,
            "active": True,
            "created_at": now,
            "updated_at": now,
        }
        self._widgets[widget_id] = record
        return self._row_to_response(record)

    async def get_by_id(self, widget_id: str, tenant_id: str) -> WidgetResponse | None:
        record = self._widgets.get(widget_id)
        if record is None or record["tenant_id"] != tenant_id:
            return None
        return self._row_to_response(record)

    async def get_by_id_raw(
        self, widget_id: str
    ) -> dict | None:
        record = self._widgets.get(widget_id)
        if record is None:
            return None
        return copy.deepcopy(record)

    async def list_by_tenant(
        self,
        tenant_id: str,
        search: str | None = None,
        active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WidgetResponse], int]:
        records = [
            r
            for r in self._widgets.values()
            if r["tenant_id"] == tenant_id
        ]
        if search is not None:
            search_lower = search.lower()
            records = [r for r in records if search_lower in r["name"].lower()]
        if active is not None:
            records = [r for r in records if r["active"] == active]

        records.sort(key=lambda r: r["created_at"], reverse=True)
        total = len(records)

        start = (page - 1) * page_size
        end = start + page_size
        page_records = records[start:end]

        items = [self._row_to_response(r) for r in page_records]
        return items, total

    async def update(
        self,
        widget_id: str,
        tenant_id: str,
        name: str | None = None,
        domain: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> WidgetResponse | None:
        record = self._widgets.get(widget_id)
        if record is None or record["tenant_id"] != tenant_id:
            return None

        if name is not None:
            record["name"] = name
        if domain is not None:
            record["domain"] = domain
        if config is not None:
            merged = copy.deepcopy(record["config"])
            merged.update(config)
            record["config"] = merged

        record["js_version"] += 1
        record["updated_at"] = datetime.now(timezone.utc)
        return self._row_to_response(record)

    async def soft_delete(self, widget_id: str, tenant_id: str) -> bool:
        record = self._widgets.get(widget_id)
        if record is None or record["tenant_id"] != tenant_id:
            return False
        record["active"] = False
        record["updated_at"] = datetime.now(timezone.utc)
        return True

    async def check_domain_exists(
        self, domain: str, tenant_id: str, exclude_id: str | None = None
    ) -> bool:
        for record in self._widgets.values():
            if record["tenant_id"] == tenant_id and record["domain"] == domain:
                if exclude_id is not None and record["id"] == exclude_id:
                    continue
                return True
        return False

    def _row_to_response(self, record: dict) -> WidgetResponse:
        return WidgetResponse(
            id=record["id"],
            tenant_id=record["tenant_id"],
            name=record["name"],
            domain=record["domain"],
            config=copy.deepcopy(record["config"]),
            js_version=record["js_version"],
            active=record["active"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

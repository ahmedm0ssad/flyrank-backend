from datetime import date
from typing import Any, Protocol

from app.models.lead import LeadResponse
from app.models.task import TaskCreate, TaskResponse, TaskUpdate
from app.models.widget import WidgetResponse


class TaskRepository(Protocol):
    async def create_task(self, task_data: TaskCreate) -> TaskResponse: ...

    async def get_all_tasks(
        self,
        search: str | None = None,
        done: bool | None = None,
    ) -> list[TaskResponse]: ...

    async def get_task(self, task_id: int) -> TaskResponse | None: ...

    async def update_task(
        self, task_id: int, task_data: TaskUpdate
    ) -> TaskResponse | None: ...

    async def delete_task(self, task_id: int) -> bool: ...

    async def get_stats(self) -> dict: ...


class LeadRepository(Protocol):
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
    ) -> LeadResponse: ...

    async def get_by_id(self, lead_id: str) -> LeadResponse | None: ...

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
    ) -> tuple[list[LeadResponse], int]: ...

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
    ) -> tuple[list[LeadResponse], int]: ...

    async def get_stats(self, widget_id: str, tenant_id: str) -> dict[str, Any]: ...

    async def get_tenant_stats(self, tenant_id: str) -> dict[str, Any]: ...

    async def get_export_data(
        self,
        widget_id: str,
        tenant_id: str,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]: ...

    async def update_status(
        self, lead_id: str, status: str, **extra: Any
    ) -> LeadResponse | None: ...

    async def delete(self, lead_id: str, widget_id: str, tenant_id: str) -> bool: ...

    async def batch_delete(
        self, lead_ids: list[str], widget_id: str, tenant_id: str
    ) -> int: ...


class WidgetRepository(Protocol):
    async def create(
        self,
        name: str,
        domain: str,
        config: dict[str, Any],
        tenant_id: str,
    ) -> WidgetResponse: ...

    async def get_by_id(
        self, widget_id: str, tenant_id: str
    ) -> WidgetResponse | None: ...

    async def get_by_id_raw(self, widget_id: str) -> dict | None: ...

    async def list_by_tenant(
        self,
        tenant_id: str,
        search: str | None = None,
        active: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[WidgetResponse], int]: ...

    async def update(
        self,
        widget_id: str,
        tenant_id: str,
        name: str | None = None,
        domain: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> WidgetResponse | None: ...

    async def soft_delete(self, widget_id: str, tenant_id: str) -> bool: ...

    async def check_domain_exists(
        self, domain: str, tenant_id: str, exclude_id: str | None = None
    ) -> bool: ...

import random
import string
from typing import Any

from app.database import is_postgres_enabled

from .models import WidgetCreate, WidgetResponse, WidgetUpdate

if is_postgres_enabled():

    class PostgresWidgetRepository:
        async def create(self, name, domain, config, tenant_id):
            raise NotImplementedError

        async def get_by_id(self, widget_id, tenant_id):
            raise NotImplementedError

        async def list_by_tenant(self, tenant_id, search, active, page, page_size):
            raise NotImplementedError

        async def update(self, widget_id, tenant_id, name, domain, config):
            raise NotImplementedError

        async def soft_delete(self, widget_id, tenant_id):
            raise NotImplementedError

        async def check_domain_exists(self, domain, tenant_id, exclude_id=None):
            raise NotImplementedError

    _repo = PostgresWidgetRepository()
else:
    from .repository import WidgetRepository

    _repo = WidgetRepository()


_redis_client = None


def _set_redis(client):
    global _redis_client
    _redis_client = client


async def _invalidate_cache(widget_id: str):
    global _redis_client
    if _redis_client is None:
        try:
            from app.main import get_redis

            _redis_client = get_redis()
        except (ImportError, RuntimeError):
            pass
    if _redis_client:
        try:
            await _redis_client.delete(f"widget:config:{widget_id}")
        except Exception:
            pass


def _generate_honeypot_field() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"_hp_{suffix}"


async def create_widget(data: WidgetCreate, tenant_id: str) -> WidgetResponse:
    domain_exists = await _repo.check_domain_exists(data.domain, tenant_id)
    if domain_exists:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A widget with this domain already exists",
        )

    config = dict(data.config)
    config["honeypot_field"] = _generate_honeypot_field()

    widget = await _repo.create(
        name=data.name,
        domain=data.domain,
        config=config,
        tenant_id=tenant_id,
    )
    return widget


async def get_widget(widget_id: str, tenant_id: str) -> WidgetResponse | None:
    return await _repo.get_by_id(widget_id, tenant_id)


async def get_widgets(
    tenant_id: str,
    search: str | None = None,
    active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[WidgetResponse], int]:
    return await _repo.list_by_tenant(
        tenant_id=tenant_id,
        search=search,
        active=active,
        page=page,
        page_size=page_size,
    )


async def update_widget(
    widget_id: str, tenant_id: str, data: WidgetUpdate
) -> WidgetResponse | None:
    existing = await _repo.get_by_id(widget_id, tenant_id)
    if existing is None:
        return None

    if data.domain is not None and data.domain != existing.domain:
        domain_exists = await _repo.check_domain_exists(
            data.domain, tenant_id, exclude_id=widget_id
        )
        if domain_exists:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A widget with this domain already exists",
            )

    updated = await _repo.update(
        widget_id=widget_id,
        tenant_id=tenant_id,
        name=data.name if data.name is not None else existing.name,
        domain=data.domain if data.domain is not None else existing.domain,
        config=data.config,
    )

    if updated is not None:
        await _invalidate_cache(widget_id)

    return updated


async def delete_widget(widget_id: str, tenant_id: str) -> bool:
    return await _repo.soft_delete(widget_id, tenant_id)


def _get_repo():
    return _repo

import random
import string

from app.dependencies.services import get_redis as _get_redis_provider
from app.dependencies.services import get_widget_repo as _get_widget_repo
from app.models.widget import WidgetCreate, WidgetResponse, WidgetUpdate
from app.repositories.protocol import WidgetRepositoryProtocol


async def _invalidate_cache(widget_id: str, redis=None):
    client = redis if redis is not None else await _get_redis_provider()
    if client:
        try:
            await client.delete(f"widget:config:{widget_id}")
        except Exception:
            pass


def _generate_honeypot_field() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"_hp_{suffix}"


def _get_repo() -> WidgetRepositoryProtocol:
    return _get_widget_repo()


async def create_widget(
    data: WidgetCreate, tenant_id: str, repo: WidgetRepositoryProtocol | None = None
) -> WidgetResponse:
    if repo is None:
        repo = _get_widget_repo()
    domain_exists = await repo.check_domain_exists(data.domain, tenant_id)
    if domain_exists:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A widget with this domain already exists",
        )

    config = dict(data.config)
    config["honeypot_field"] = _generate_honeypot_field()

    widget = await repo.create(
        name=data.name,
        domain=data.domain,
        config=config,
        tenant_id=tenant_id,
    )
    return widget


async def get_widget(
    widget_id: str, tenant_id: str, repo: WidgetRepositoryProtocol | None = None
) -> WidgetResponse | None:
    if repo is None:
        repo = _get_widget_repo()
    return await repo.get_by_id(widget_id, tenant_id)


async def get_widgets(
    tenant_id: str,
    search: str | None = None,
    active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
    repo: WidgetRepositoryProtocol | None = None,
) -> tuple[list[WidgetResponse], int]:
    if repo is None:
        repo = _get_widget_repo()
    return await repo.list_by_tenant(
        tenant_id=tenant_id,
        search=search,
        active=active,
        page=page,
        page_size=page_size,
    )


async def update_widget(
    widget_id: str,
    tenant_id: str,
    data: WidgetUpdate,
    repo: WidgetRepositoryProtocol | None = None,
    redis=None,
) -> WidgetResponse | None:
    if repo is None:
        repo = _get_widget_repo()
    existing = await repo.get_by_id(widget_id, tenant_id)
    if existing is None:
        return None

    if data.domain is not None and data.domain != existing.domain:
        domain_exists = await repo.check_domain_exists(
            data.domain, tenant_id, exclude_id=widget_id
        )
        if domain_exists:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A widget with this domain already exists",
            )

    updated = await repo.update(
        widget_id=widget_id,
        tenant_id=tenant_id,
        name=data.name if data.name is not None else existing.name,
        domain=data.domain if data.domain is not None else existing.domain,
        config=data.config,
    )

    if updated is not None:
        await _invalidate_cache(widget_id, redis=redis)

    return updated


async def delete_widget(
    widget_id: str, tenant_id: str, repo: WidgetRepositoryProtocol | None = None
) -> bool:
    if repo is None:
        repo = _get_widget_repo()
    return await repo.soft_delete(widget_id, tenant_id)

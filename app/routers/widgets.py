from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_widget_repo
from app.models.widget import (
    PaginatedResponse,
    WidgetCreate,
    WidgetResponse,
    WidgetUpdate,
)
from app.repositories.protocol import WidgetRepositoryProtocol
from app.services import widget_service

router = APIRouter(prefix="/widgets", tags=["widgets"])


@router.get("/", response_model=PaginatedResponse)
async def list_widgets(
    search: str | None = Query(None),
    active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    repo: WidgetRepositoryProtocol = Depends(get_widget_repo),
):
    tenant_id = str(user["id"])
    items, total = await widget_service.get_widgets(
        tenant_id=tenant_id,
        search=search,
        active=active,
        page=page,
        page_size=page_size,
        repo=repo,
    )
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/", response_model=WidgetResponse, status_code=status.HTTP_201_CREATED)
async def create_widget(
    data: WidgetCreate,
    user: dict = Depends(get_current_user),
    repo: WidgetRepositoryProtocol = Depends(get_widget_repo),
):
    tenant_id = str(user["id"])
    return await widget_service.create_widget(data, tenant_id, repo=repo)


@router.get("/{widget_id}", response_model=WidgetResponse)
async def get_widget(
    widget_id: UUID,
    user: dict = Depends(get_current_user),
    repo: WidgetRepositoryProtocol = Depends(get_widget_repo),
):
    tenant_id = str(user["id"])
    widget = await widget_service.get_widget(str(widget_id), tenant_id, repo=repo)
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )
    return widget


@router.put("/{widget_id}", response_model=WidgetResponse)
async def update_widget(
    widget_id: UUID,
    data: WidgetUpdate,
    user: dict = Depends(get_current_user),
    repo: WidgetRepositoryProtocol = Depends(get_widget_repo),
):
    tenant_id = str(user["id"])
    widget = await widget_service.update_widget(
        str(widget_id), tenant_id, data, repo=repo
    )
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )
    return widget


@router.delete("/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_widget(
    widget_id: UUID,
    user: dict = Depends(get_current_user),
    repo: WidgetRepositoryProtocol = Depends(get_widget_repo),
):
    tenant_id = str(user["id"])
    deleted = await widget_service.delete_widget(str(widget_id), tenant_id, repo=repo)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

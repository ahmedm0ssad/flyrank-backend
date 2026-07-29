from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse

from app.dependencies.auth import get_current_user
from app.models.lead import (
    BatchDeleteRequest,
    LeadResponse,
    LeadSubmit,
    PaginatedLeadResponse,
)
from app.services import lead_service, widget_service

router = APIRouter(prefix="/public/widget", tags=["public-leads"])
dashboard_router = APIRouter(prefix="/widgets", tags=["leads"])
cross_router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("/{widget_id}/submit", status_code=status.HTTP_201_CREATED)
async def submit_lead(widget_id: UUID, body: LeadSubmit, request: Request):
    lead, _ = await lead_service.submit_lead(str(widget_id), body, request)

    return {
        "success": True,
        "message": "Thank you for your submission",
        "lead_id": str(lead.id),
    }


def _compute_pages(total: int, page_size: int) -> int:
    return (total + page_size - 1) // page_size if total > 0 else 0


def _paginated_response(items, total: int, page: int, page_size: int):
    return PaginatedLeadResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=_compute_pages(total, page_size),
    )


# ── Per-widget lead list ──────────────────────────────────────────


@dashboard_router.get(
    "/{widget_id}/leads",
    response_model=PaginatedLeadResponse,
)
async def list_widget_leads(
    widget_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    lead_status: str | None = Query(None, alias="status"),
    spam_min: float | None = Query(None),
    spam_max: float | None = Query(None),
    include_honeypot: bool = Query(False),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    user: dict = Depends(get_current_user),
):
    tenant_id = str(user["id"])

    widget = await widget_service.get_widget(str(widget_id), tenant_id)
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    items, total = await lead_service.get_leads(
        widget_id=str(widget_id),
        tenant_id=tenant_id,
        include_honeypot=include_honeypot,
        page=page,
        page_size=page_size,
        search=search,
        status=lead_status,
        spam_min=spam_min,
        spam_max=spam_max,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return _paginated_response(items, total, page, page_size)


# ── Cross-widget lead list ────────────────────────────────────────


@cross_router.get(
    "",
    response_model=PaginatedLeadResponse,
)
async def list_all_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    lead_status: str | None = Query(None, alias="status"),
    spam_min: float | None = Query(None),
    spam_max: float | None = Query(None),
    include_honeypot: bool = Query(False),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    user: dict = Depends(get_current_user),
):
    tenant_id = str(user["id"])
    items, total = await lead_service.get_all_leads(
        tenant_id=tenant_id,
        include_honeypot=include_honeypot,
        page=page,
        page_size=page_size,
        search=search,
        status=lead_status,
        spam_min=spam_min,
        spam_max=spam_max,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return _paginated_response(items, total, page, page_size)


# ── Lead detail ───────────────────────────────────────────────────


@dashboard_router.get(
    "/{widget_id}/leads/{lead_id}",
    response_model=LeadResponse,
)
async def get_lead_detail(
    widget_id: UUID,
    lead_id: UUID,
    user: dict = Depends(get_current_user),
):
    tenant_id = str(user["id"])
    lead = await lead_service.get_lead_detail(
        lead_id=str(lead_id),
        widget_id=str(widget_id),
        tenant_id=tenant_id,
    )
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    return lead


# ── Per-widget stats ──────────────────────────────────────────────


@dashboard_router.get("/{widget_id}/stats")
async def get_widget_stats(
    widget_id: UUID,
    user: dict = Depends(get_current_user),
):
    tenant_id = str(user["id"])

    widget = await widget_service.get_widget(str(widget_id), tenant_id)
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    stats = await lead_service.get_widget_stats(
        widget_id=str(widget_id),
        tenant_id=tenant_id,
    )
    return stats


# ── Cross-widget stats ────────────────────────────────────────────


@cross_router.get("/stats")
async def get_global_stats(
    user: dict = Depends(get_current_user),
):
    tenant_id = str(user["id"])
    stats = await lead_service.get_tenant_stats(tenant_id=tenant_id)
    return stats


# ── CSV export ────────────────────────────────────────────────────


@dashboard_router.get("/{widget_id}/export")
async def export_leads_csv(
    widget_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    user: dict = Depends(get_current_user),
):
    tenant_id = str(user["id"])

    widget = await widget_service.get_widget(str(widget_id), tenant_id)
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    csv_content, truncated = await lead_service.export_csv(
        widget_id=str(widget_id),
        tenant_id=tenant_id,
        date_from=date_from,
        date_to=date_to,
    )

    headers = {
        "Content-Disposition": f'attachment; filename="widget_{widget_id}_leads.csv"',
    }
    if truncated:
        headers["X-Export-Truncated"] = "true"

    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers=headers,
    )


# ── Delete single lead ────────────────────────────────────────────


@dashboard_router.delete(
    "/{widget_id}/leads/{lead_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_lead(
    widget_id: UUID,
    lead_id: UUID,
    user: dict = Depends(get_current_user),
):
    tenant_id = str(user["id"])
    deleted = await lead_service.delete_lead(
        lead_id=str(lead_id),
        widget_id=str(widget_id),
        tenant_id=tenant_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )


# ── Batch delete ──────────────────────────────────────────────────


@dashboard_router.post(
    "/{widget_id}/leads/batch-delete",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def batch_delete_leads(
    widget_id: UUID,
    body: BatchDeleteRequest,
    user: dict = Depends(get_current_user),
):
    tenant_id = str(user["id"])
    lead_ids = [str(lid) for lid in body.lead_ids]
    await lead_service.batch_delete_leads(
        lead_ids=lead_ids,
        widget_id=str(widget_id),
        tenant_id=tenant_id,
    )


# ── Re-enrich (existing) ──────────────────────────────────────────


@dashboard_router.post(
    "/{widget_id}/leads/{lead_id}/re-enrich",
    status_code=status.HTTP_202_ACCEPTED,
)
async def re_enrich_lead(
    widget_id: UUID,
    lead_id: UUID,
    user: dict = Depends(get_current_user),
):
    tenant_id = str(user["id"])

    widget = await widget_service.get_widget(str(widget_id), tenant_id)
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    return await lead_service.re_enrich_lead(
        lead_id=str(lead_id),
        widget_id=str(widget_id),
        tenant_id=tenant_id,
    )

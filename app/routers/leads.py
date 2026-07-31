import inspect
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from fastapi.routing import APIRoute

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_lead_repo, get_widget_repo
from app.models.lead import (
    BatchDeleteRequest,
    LeadResponse,
    LeadSubmit,
    PaginatedLeadResponse,
)
from app.repositories.lead_repo import LeadRepository
from app.repositories.protocol import WidgetRepositoryProtocol
from app.services import lead_service, widget_service

router = APIRouter(prefix="/public/widget", tags=["public-leads"])
dashboard_router = APIRouter(prefix="/widgets", tags=["leads"])
cross_router = APIRouter(prefix="/leads", tags=["leads"])

_STRICT_CONTENT_TYPE_KWARGS = (
    {"strict_content_type": False}
    if "strict_content_type" in inspect.signature(APIRoute.__init__).parameters
    else {}
)


@router.post(
    "/{widget_id}/submit",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a lead",
    description="Accepts a public widget form submission. Validates origin, rate limits, honeypot, fingerprint dedup, and spam score before storing the lead, then enqueues enrichment and dispatches any configured webhook asynchronously. Returns 201 with the new lead_id.",
    **_STRICT_CONTENT_TYPE_KWARGS,
)
async def submit_lead(
    widget_id: UUID,
    body: LeadSubmit,
    request: Request,
    repo: LeadRepository = Depends(get_lead_repo),
):
    lead, _ = await lead_service.submit_lead(str(widget_id), body, request, repo=repo)

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
    summary="List widget leads",
    description="Lists leads for a widget owned by the authenticated user, with filtering by search, status, spam score range, and date range, plus pagination and sorting.",
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
    repo: LeadRepository = Depends(get_lead_repo),
    widget_repo: WidgetRepositoryProtocol = Depends(get_widget_repo),
):
    tenant_id = str(user["id"])

    widget = await widget_service.get_widget(
        str(widget_id), tenant_id, repo=widget_repo
    )
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
        repo=repo,
    )
    return _paginated_response(items, total, page, page_size)


# ── Cross-widget lead list ────────────────────────────────────────


@cross_router.get(
    "",
    response_model=PaginatedLeadResponse,
    summary="List all leads",
    description="Lists the authenticated user's leads across all widgets, with the same filters and pagination as the per-widget list.",
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
    repo: LeadRepository = Depends(get_lead_repo),
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
        repo=repo,
    )
    return _paginated_response(items, total, page, page_size)


# ── Lead detail ───────────────────────────────────────────────────


@dashboard_router.get(
    "/{widget_id}/leads/{lead_id}",
    response_model=LeadResponse,
    summary="Get a lead",
    description="Returns a single lead owned by the authenticated user. Returns 404 if it does not exist.",
)
async def get_lead_detail(
    widget_id: UUID,
    lead_id: UUID,
    user: dict = Depends(get_current_user),
    repo: LeadRepository = Depends(get_lead_repo),
):
    tenant_id = str(user["id"])
    lead = await lead_service.get_lead_detail(
        lead_id=str(lead_id),
        widget_id=str(widget_id),
        tenant_id=tenant_id,
        repo=repo,
    )
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    return lead


# ── Per-widget stats ──────────────────────────────────────────────


@dashboard_router.get(
    "/{widget_id}/stats",
    summary="Get widget lead stats",
    description="Returns aggregate lead statistics for a widget owned by the authenticated user.",
)
async def get_widget_stats(
    widget_id: UUID,
    user: dict = Depends(get_current_user),
    repo: LeadRepository = Depends(get_lead_repo),
    widget_repo: WidgetRepositoryProtocol = Depends(get_widget_repo),
):
    tenant_id = str(user["id"])

    widget = await widget_service.get_widget(
        str(widget_id), tenant_id, repo=widget_repo
    )
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    stats = await lead_service.get_widget_stats(
        widget_id=str(widget_id),
        tenant_id=tenant_id,
        repo=repo,
    )
    return stats


# ── Cross-widget stats ────────────────────────────────────────────


@cross_router.get(
    "/stats",
    summary="Get global lead stats",
    description="Returns aggregate lead statistics across all of the authenticated user's widgets.",
)
async def get_global_stats(
    user: dict = Depends(get_current_user),
    repo: LeadRepository = Depends(get_lead_repo),
):
    tenant_id = str(user["id"])
    stats = await lead_service.get_tenant_stats(tenant_id=tenant_id, repo=repo)
    return stats


# ── CSV export ────────────────────────────────────────────────────


@dashboard_router.get(
    "/{widget_id}/export",
    summary="Export widget leads to CSV",
    description="Exports a widget's leads as a CSV attachment, optionally filtered by date range. Sets the X-Export-Truncated header when the export is truncated at the row limit.",
)
async def export_leads_csv(
    widget_id: UUID,
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    user: dict = Depends(get_current_user),
    repo: LeadRepository = Depends(get_lead_repo),
    widget_repo: WidgetRepositoryProtocol = Depends(get_widget_repo),
):
    tenant_id = str(user["id"])

    widget = await widget_service.get_widget(
        str(widget_id), tenant_id, repo=widget_repo
    )
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
        repo=repo,
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
    summary="Delete a lead",
    description="Deletes a single lead owned by the authenticated user. Returns 204 on success and 404 if it does not exist.",
)
async def delete_lead(
    widget_id: UUID,
    lead_id: UUID,
    user: dict = Depends(get_current_user),
    repo: LeadRepository = Depends(get_lead_repo),
):
    tenant_id = str(user["id"])
    deleted = await lead_service.delete_lead(
        lead_id=str(lead_id),
        widget_id=str(widget_id),
        tenant_id=tenant_id,
        repo=repo,
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
    summary="Batch delete leads",
    description="Deletes multiple leads owned by the authenticated user in one request. Returns 204.",
)
async def batch_delete_leads(
    widget_id: UUID,
    body: BatchDeleteRequest,
    user: dict = Depends(get_current_user),
    repo: LeadRepository = Depends(get_lead_repo),
):
    tenant_id = str(user["id"])
    lead_ids = [str(lid) for lid in body.lead_ids]
    await lead_service.batch_delete_leads(
        lead_ids=lead_ids,
        widget_id=str(widget_id),
        tenant_id=tenant_id,
        repo=repo,
    )


# ── Re-enrich (existing) ──────────────────────────────────────────


@dashboard_router.post(
    "/{widget_id}/leads/{lead_id}/re-enrich",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-enrich a lead",
    description="Re-queues enrichment (IP geolocation) for an existing lead owned by the authenticated user. Returns 202 Accepted with the job status.",
)
async def re_enrich_lead(
    widget_id: UUID,
    lead_id: UUID,
    user: dict = Depends(get_current_user),
    repo: LeadRepository = Depends(get_lead_repo),
    widget_repo: WidgetRepositoryProtocol = Depends(get_widget_repo),
):
    tenant_id = str(user["id"])

    widget = await widget_service.get_widget(
        str(widget_id), tenant_id, repo=widget_repo
    )
    if widget is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    return await lead_service.re_enrich_lead(
        lead_id=str(lead_id),
        widget_id=str(widget_id),
        tenant_id=tenant_id,
        repo=repo,
    )

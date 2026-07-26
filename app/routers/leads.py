from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.dependencies.auth import get_current_user
from app.models.lead import LeadSubmit
from app.services import lead_service, widget_service

router = APIRouter(prefix="/public/widget", tags=["public-leads"])
dashboard_router = APIRouter(prefix="/widgets", tags=["leads"])


@router.post("/{widget_id}/submit", status_code=status.HTTP_201_CREATED)
async def submit_lead(widget_id: UUID, body: LeadSubmit, request: Request):
    lead, _ = await lead_service.submit_lead(
        str(widget_id), body, request
    )

    return {
        "success": True,
        "message": "Thank you for your submission",
        "lead_id": str(lead.id),
    }


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

    repo = lead_service._get_or_create_repo()
    lead = await repo.get_by_id(str(lead_id))
    if lead is None or lead.widget_id != widget_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    if lead.status in ("enriched", "pending"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lead status is '{lead.status}', can only re-enrich 'failed' leads",
        )

    from app.core.queue import create_enrichment_job

    create_enrichment_job(str(lead_id))

    return {"status": "re-enqueued", "lead_id": str(lead_id)}

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.models.lead import LeadSubmit
from app.services import lead_service

router = APIRouter(prefix="/public/widget", tags=["public-leads"])


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

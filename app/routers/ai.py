import logging

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.models.job import (
    JobCreate,
    JobEnqueueResponse,
    JobListResponse,
)
from app.queue import create_job, get_job, list_jobs

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai"])


@router.post("/ai", status_code=status.HTTP_202_ACCEPTED)
async def create_ai_job(
    payload: JobCreate,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    job_id, status_val = create_job(payload.model_dump(), idempotency_key)
    logger.info("Job %s created with status %s", job_id, status_val.value)
    return JobEnqueueResponse(job_id=job_id, status=status_val)


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job


@router.get("/jobs")
async def list_all_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    jobs = list_jobs(limit=limit, offset=offset)
    return JobListResponse(jobs=jobs, total=len(jobs))

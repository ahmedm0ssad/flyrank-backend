import logging
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel
from rq import Queue, Retry

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

router = APIRouter(tags=["ai"])


class AIPayload(BaseModel):
    prompt: str
    model: str = "llama3-8b-8192"


class JobResponse(BaseModel):
    job_id: str
    status_url: str


IDEMPOTENCY_TTL = 86400


def _get_queue():
    from redis import Redis

    conn = Redis.from_url(_REDIS_URL, decode_responses=True, protocol=2)
    return Queue("ai-jobs", connection=conn), conn


@router.post("/ai", status_code=status.HTTP_202_ACCEPTED)
async def create_ai_job(
    payload: AIPayload,
    request: Request,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
):
    queue, redis_conn = _get_queue()

    if idempotency_key:
        existing_job_id = redis_conn.get(f"idempotency:{idempotency_key}")
        if existing_job_id:
            return JobResponse(
                job_id=existing_job_id,
                status_url=f"/jobs/{existing_job_id}",
            )

    job_id = str(uuid.uuid4())

    job_key = f"job:{job_id}"
    redis_conn.hset(
        job_key,
        mapping={
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "attempts": "0",
        },
    )
    redis_conn.expire(job_key, IDEMPOTENCY_TTL)

    from app.services.ai_worker import run_ai_job

    retry = Retry(max=3, interval=[10, 60, 300])
    queue.enqueue(
        run_ai_job,
        payload.model_dump(),
        job_id=job_id,
        retry=retry,
        job_timeout=600,
        meta={"max_retries": 3},
    )

    if idempotency_key:
        redis_conn.setex(f"idempotency:{idempotency_key}", IDEMPOTENCY_TTL, job_id)

    return JobResponse(
        job_id=job_id,
        status_url=f"/jobs/{job_id}",
    )


@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    _, redis_conn = _get_queue()

    job_key = f"job:{job_id}"
    job_data = redis_conn.hgetall(job_key)

    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    status_val = job_data.get("status", "unknown")

    if status_val == "queued":
        return {"status": "queued"}
    elif status_val == "processing":
        return {"status": "processing"}
    elif status_val == "completed":
        return {
            "status": "completed",
            "result": job_data.get("result"),
        }
    elif status_val == "failed":
        return {
            "status": "failed",
            "error": job_data.get("error", "Unknown error"),
            "attempts": int(job_data.get("attempts", 0)),
        }

    return {"status": status_val}

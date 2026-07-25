import logging
from datetime import datetime, timezone

from rq import get_current_job

from app.models.job import JobStatus
from app.queue import update_job
from app.services.ai_service import call_ai
from app.services.alert import send_alert

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_ai_job(payload: dict) -> str:
    job = get_current_job()
    job_id = job.id

    logger.info("Job %s started", job_id)
    update_job(job_id, JobStatus.STARTED.value, started_at=_now())

    try:
        result = call_ai(payload)

        logger.info("Job %s completed successfully", job_id)
        update_job(
            job_id,
            JobStatus.FINISHED.value,
            result=result,
            finished_at=_now(),
        )

        return result

    except Exception as exc:
        attempts = int(job.meta.get("current_attempt", 0)) + 1
        job.meta["current_attempt"] = attempts
        job.save_meta()

        logger.warning(
            "Job %s failed (attempt %d/%d): %s",
            job_id,
            attempts,
            job.meta.get("max_retries", 3) + 1,
            exc,
        )

        if job.retries_left is not None and job.retries_left > 0:
            update_job(job_id, JobStatus.QUEUED.value)
            logger.info("Job %s requeued for retry (attempt %d)", job_id, attempts)
        else:
            update_job(
                job_id,
                JobStatus.FAILED.value,
                error=str(exc),
                finished_at=_now(),
            )
            logger.error("Job %s failed after all retries: %s", job_id, exc)
            send_alert(f"AI job {job_id} failed permanently: {exc}")

        raise

import asyncio
import logging
from datetime import datetime, timezone

from rq import get_current_job

from app.models.report import ReportStatus
from app.queue import update_report_job
from app.services.alert import send_alert
from app.services.pdf_generator import generate_report
from app.services.report_service import (
    get_ai_jobs_stats,
    get_report_data_for_worker,
    get_scraped_books_stats,
    update_report_status,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_report_job(job_id: str) -> str:
    job = get_current_job()
    job_id = job.id

    logger.info("Report job %s started", job_id)
    update_report_job(job_id, ReportStatus.STARTED.value, started_at=_now())

    try:
        asyncio.run(update_report_status(job_id, ReportStatus.STARTED))

        stats = get_report_data_for_worker(job_id)
        books_stats = get_scraped_books_stats()
        ai_stats = get_ai_jobs_stats()

        filepath = generate_report(job_id, stats, books_stats, ai_stats)

        asyncio.run(
            update_report_status(job_id, ReportStatus.FINISHED, file_path=filepath)
        )

        logger.info("Report job %s completed: %s", job_id, filepath)
        update_report_job(
            job_id, ReportStatus.FINISHED.value, result=filepath, finished_at=_now()
        )

        return filepath

    except Exception as exc:
        attempts = int(job.meta.get("current_attempt", 0)) + 1
        job.meta["current_attempt"] = attempts
        job.save_meta()

        logger.warning(
            "Report job %s failed (attempt %d/%d): %s",
            job_id,
            attempts,
            job.meta.get("max_retries", 3) + 1,
            exc,
        )

        if job.retries_left is not None and job.retries_left > 0:
            update_report_job(job_id, ReportStatus.QUEUED.value)
            logger.info(
                "Report job %s requeued for retry (attempt %d)", job_id, attempts
            )
        else:
            error_msg = str(exc)
            asyncio.run(
                update_report_status(job_id, ReportStatus.FAILED, error=error_msg)
            )
            update_report_job(
                job_id,
                ReportStatus.FAILED.value,
                error=error_msg,
                finished_at=_now(),
            )
            logger.error("Report job %s failed after all retries: %s", job_id, exc)
            send_alert(f"Report job {job_id} failed permanently: {exc}")

        raise

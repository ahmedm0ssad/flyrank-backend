import asyncio
import logging
from datetime import datetime, timezone

from rq import get_current_job

from app.core.queue import (
    clear_enrichment_active,
    update_enrichment_job,
)
from app.models.job import JobStatus
from app.repositories.lead_repo import LeadRepository
from app.services.alert import send_alert
from app.services.geo_service import geo_enrich

logger = logging.getLogger(__name__)


def _get_worker_repo():
    from app.core.database import is_postgres_enabled

    if is_postgres_enabled():
        from app.repositories.postgres_lead_repo import PostgresLeadRepository

        return PostgresLeadRepository()
    return LeadRepository()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_enrichment_job(lead_id: str) -> str:
    job = get_current_job()
    job_id = job.id

    logger.info("Enrichment job %s started for lead %s", job_id, lead_id)
    update_enrichment_job(job_id, JobStatus.STARTED.value, started_at=_now())

    try:
        repo = _get_worker_repo()
        lead = asyncio.run(repo.get_by_id(lead_id))
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found")

        if lead.status == "enriched":
            logger.info("Lead %s already enriched, skipping", lead_id)
            clear_enrichment_active(lead_id)
            update_enrichment_job(
                job_id,
                JobStatus.FINISHED.value,
                result="already_enriched",
                finished_at=_now(),
            )
            return "already_enriched"

        geo_data = geo_enrich(lead.ip_address)
        if geo_data:
            updated = asyncio.run(
                repo.update_status(
                    lead_id,
                    "enriched",
                    geo_country=geo_data.get("country"),
                    geo_city=geo_data.get("city"),
                    geo_region=geo_data.get("region"),
                    geo_isp=geo_data.get("isp"),
                    geo_provider=geo_data.get("provider"),
                )
            )
            if updated is None:
                raise ValueError(f"Failed to update lead {lead_id}")

            logger.info(
                "Lead %s enriched with provider %s",
                lead_id,
                geo_data.get("provider"),
            )
            clear_enrichment_active(lead_id)
            update_enrichment_job(
                job_id,
                JobStatus.FINISHED.value,
                result="enriched",
                finished_at=_now(),
            )
            return "enriched"
        else:
            raise RuntimeError(
                f"All geo providers exhausted for lead {lead_id} "
                f"(IP: {lead.ip_address})"
            )

    except Exception as exc:
        attempts = int(job.meta.get("current_attempt", 0)) + 1
        job.meta["current_attempt"] = attempts
        job.save_meta()

        logger.warning(
            "Enrichment job %s failed (attempt %d/%d): %s",
            job_id,
            attempts,
            job.meta.get("max_retries", 3) + 1,
            exc,
        )

        if job.retries_left is not None and job.retries_left > 0:
            update_enrichment_job(job_id, JobStatus.QUEUED.value)
            logger.info(
                "Enrichment job %s requeued for retry (attempt %d)",
                job_id,
                attempts,
            )
        else:
            try:
                repo = _get_worker_repo()
                asyncio.run(repo.update_status(lead_id, "failed"))
            except Exception:
                pass
            clear_enrichment_active(lead_id)
            update_enrichment_job(
                job_id,
                JobStatus.FAILED.value,
                error=str(exc),
                finished_at=_now(),
            )
            logger.error("Enrichment job %s failed after all retries: %s", job_id, exc)
            send_alert(f"Geo enrichment failed for lead {lead_id}: {exc}")

        raise

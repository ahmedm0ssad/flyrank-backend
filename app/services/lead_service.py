from uuid import UUID

from fastapi import HTTPException, Request, status

from app.dependencies.leads import check_origin, check_rate_limits
from app.models.lead import LeadResponse, LeadSubmit
from app.repositories.lead_repo import LeadRepository
from app.services import embed_service
from app.services.fingerprint_service import (
    check_dedup,
    compute_fingerprint,
    mark_seen,
)
from app.services.spam_service import score_submission


def _get_repo():
    return LeadRepository()


_repo: LeadRepository | None = None


def _get_or_create_repo():
    global _repo
    if _repo is None:
        _repo = _get_repo()
    return _repo


async def submit_lead(
    widget_id: str,
    body: LeadSubmit,
    request: Request,
) -> tuple[LeadResponse, bool]:
    repo = _get_or_create_repo()

    # Step 4: Widget exists & active check
    config = await embed_service.get_widget_config(widget_id)
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Widget not found",
        )

    # Step 5: Origin validation (reuses app/dependencies/embed.py)
    await check_origin(request, UUID(widget_id))

    # Step 6: Rate limit check - all 3 tiers
    ip = request.client.host if request.client else "unknown"
    retry_after = await check_rate_limits(ip, widget_id)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    # Step 7: Honeypot check
    honeypot_field = config.get("honeypot_field", "")
    honeypot_triggered = False
    spam_score = 0.0
    spam_reasons: list[str] | None = None
    skip_enrich = False

    if honeypot_field and honeypot_field in body.form_data:
        hp_value = body.form_data.pop(honeypot_field, "")
        if hp_value:
            honeypot_triggered = True
            spam_score = 1.0
            spam_reasons = ["honeypot"]
            skip_enrich = True

    # Step 8: Fingerprint computation & dedup
    user_agent = request.headers.get("user-agent", "")
    referer = body.referer or request.headers.get("referer", "")

    fingerprint = compute_fingerprint(widget_id, ip, body.form_data)
    existing_lead_id = await check_dedup(fingerprint)
    if existing_lead_id is not None:
        existing = await repo.get_by_id(existing_lead_id)
        if existing is not None:
            return existing, True

    # Step 9: Spam pre-check (skipped if honeypot already set)
    if not honeypot_triggered:
        spam_score, spam_reasons = score_submission(body.form_data)

    # Step 10: Insert lead
    raw = await embed_service.get_raw_widget(widget_id)
    tenant_id = raw["tenant_id"] if raw else "unknown"

    lead = await repo.create(
        widget_id=widget_id,
        tenant_id=tenant_id,
        form_data=body.form_data,
        ip_address=ip,
        fingerprint=fingerprint,
        user_agent=user_agent,
        referer=referer,
        spam_score=spam_score,
        spam_reasons=spam_reasons,
        honeypot_triggered=honeypot_triggered,
    )

    # Mark fingerprint as seen
    await mark_seen(fingerprint, str(lead.id))

    # Step 11: Enqueue enrichment job (skipped for honeypot)
    if not skip_enrich:
        try:
            from app.core.queue import create_enrichment_job

            create_enrichment_job(str(lead.id))
        except Exception:
            pass

    return lead, False

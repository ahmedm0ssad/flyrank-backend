import logging
import os
from datetime import datetime, timezone

import redis
from rq import get_current_job

from app.services.ai_service import call_ai
from app.services.alert import send_alert

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _get_redis():
    return redis.from_url(_REDIS_URL, decode_responses=True, protocol=2)


def run_ai_job(payload: dict) -> str:
    job = get_current_job()
    job_id = job.id
    r = _get_redis()

    key = f"job:{job_id}"
    r.hset(key, mapping={"status": "processing", "updated_at": _now()})

    try:
        result = call_ai(payload)

        r.hset(
            key,
            mapping={
                "status": "completed",
                "result": result,
                "updated_at": _now(),
            },
        )
        r.expire(key, 86400)
        return result

    except Exception as exc:
        attempts = r.hincrby(key, "attempts", 1)
        r.hset(key, "last_error", str(exc))
        r.hset(key, "updated_at", _now())

        if job and job.retries_left is not None and job.retries_left > 0:
            r.hset(key, "status", "queued")
            logger.warning(
                "Job %s failed (attempt %d/%d): %s. Retrying.",
                job_id,
                attempts,
                job.meta.get("max_retries", 3) + 1,
                exc,
            )
        else:
            r.hset(key, "status", "failed")
            r.hset(key, "error", str(exc))
            r.expire(key, 86400)

            payload_summary = {k: v for k, v in payload.items() if k != "prompt"}
            if "prompt" in payload:
                prompt = payload["prompt"]
                payload_summary["prompt_preview"] = (
                    prompt[:80] + "..." if len(prompt) > 80 else prompt
                )

            logger.error(
                "Job %s failed after all retries. Payload: %s. Error: %s",
                job_id,
                payload_summary,
                exc,
            )
            send_alert(
                f"AI job {job_id} failed permanently. "
                f"Payload: {payload_summary}. Error: {exc}"
            )

        raise


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

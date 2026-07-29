import hashlib
import json

FINGERPRINT_TTL = 300


def compute_fingerprint(widget_id: str, ip: str, form_data: dict) -> str:
    normalized = json.dumps(form_data, sort_keys=True)
    raw = f"{widget_id}:{ip}:{normalized}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _get_redis():
    try:
        from app.main import get_redis

        return get_redis()
    except (ImportError, RuntimeError):
        return None


async def check_dedup(fingerprint: str) -> str | None:
    redis = _get_redis()
    if redis is None:
        return None
    cache_key = f"submission:fp:{fingerprint}"
    try:
        existing = await redis.get(cache_key)
        return existing if existing else None
    except Exception:
        return None


async def mark_seen(fingerprint: str, lead_id: str) -> None:
    redis = _get_redis()
    if redis is None:
        return
    cache_key = f"submission:fp:{fingerprint}"
    try:
        await redis.setex(cache_key, FINGERPRINT_TTL, lead_id)
    except Exception:
        pass

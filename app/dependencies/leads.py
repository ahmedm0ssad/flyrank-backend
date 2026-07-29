import logging
import time
from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException, Request, status

from app.dependencies.embed import validate_origin

logger = logging.getLogger(__name__)

RATE_LIMIT_TIERS: list[tuple[str, int]] = [
    ("global_ip:{ip}:submit", 100),
    ("widget_ip:{widget_id}:{ip}:submit", 30),
    ("widget_global:{widget_id}:submit", 1000),
]

RATE_LIMIT_WINDOW = 60


def _get_redis():
    try:
        from app.main import get_redis

        return get_redis()
    except (ImportError, RuntimeError):
        return None


_in_process_limits: dict[str, list[float]] = defaultdict(list)


def _check_in_process(ip: str, widget_id: str) -> int | None:
    now = time.time()
    window = RATE_LIMIT_WINDOW
    keys_and_limits = [
        (f"ratelimit:global_ip:{ip}:submit", 100),
        (f"ratelimit:widget_ip:{widget_id}:{ip}:submit", 30),
        (f"ratelimit:widget_global:{widget_id}:submit", 1000),
    ]

    for key, limit in keys_and_limits:
        _in_process_limits[key] = [
            t for t in _in_process_limits[key] if now - t < window
        ]
        if len(_in_process_limits[key]) >= limit:
            return window
        _in_process_limits[key].append(now)

    return None


async def check_origin(request: Request, widget_id: UUID) -> None:
    valid = await validate_origin(request, widget_id)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin not allowed",
        )


async def check_rate_limits(ip: str, widget_id: str) -> int | None:
    redis = _get_redis()
    if redis is None:
        return _check_in_process(ip, widget_id)

    keys_and_limits = [
        (f"ratelimit:{key_template.format(ip=ip, widget_id=widget_id)}", limit)
        for key_template, limit in RATE_LIMIT_TIERS
    ]

    try:
        pipe = redis.pipeline()
        for key, _ in keys_and_limits:
            pipe.incr(key)
        counts = await pipe.execute()

        for (key, _), count in zip(keys_and_limits, counts):
            if count == 1:
                await redis.expire(key, RATE_LIMIT_WINDOW)

        for (key, limit), count in zip(keys_and_limits, counts):
            if count > limit:
                return RATE_LIMIT_WINDOW

        return None
    except Exception:
        return _check_in_process(ip, widget_id)

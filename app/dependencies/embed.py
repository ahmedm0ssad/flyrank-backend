import logging
from urllib.parse import urlparse
from uuid import UUID

from fastapi import Request

from app.services.embed_service import get_raw_widget

logger = logging.getLogger(__name__)


def _normalize_host(hostname: str) -> str:
    if not hostname:
        return ""
    try:
        return hostname.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return hostname


def _parse_origin_host(origin_header: str) -> str:
    if not origin_header:
        return ""
    parsed = urlparse(origin_header)
    raw_host = parsed.hostname or ""
    return _normalize_host(raw_host)


async def validate_origin(request: Request, widget_id: UUID) -> bool:
    origin_header = request.headers.get("origin") or request.headers.get("referer", "")
    if not origin_header:
        logger.debug("Origin validation failed: empty Origin header")
        return False

    raw = await get_raw_widget(str(widget_id))
    if raw is None or not raw.get("active", False):
        return False

    request_host = _parse_origin_host(origin_header)
    if not request_host:
        logger.debug("Origin validation failed: could not parse host from %r", origin_header)
        return False

    allowed = _parse_origin_host(raw["domain"])
    if not allowed:
        logger.debug("Origin validation failed: could not parse allowed domain %r", raw["domain"])
        return False

    if allowed.startswith("*."):
        base = allowed[2:]
        result = request_host == base or request_host.endswith("." + base)
        if not result:
            logger.debug("Origin validation failed: wildcard %r does not match %r", allowed, request_host)
        return result

    result = request_host == allowed
    if not result:
        logger.debug("Origin validation failed: %r != %r", request_host, allowed)
    return result

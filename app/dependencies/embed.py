from urllib.parse import urlparse
from uuid import UUID

from fastapi import Request

from app.services.embed_service import get_raw_widget


async def validate_origin(request: Request, widget_id: UUID) -> bool:
    origin_header = request.headers.get("origin") or request.headers.get("referer", "")
    if not origin_header:
        return False

    raw = await get_raw_widget(str(widget_id))
    if raw is None or not raw.get("active", False):
        return False

    request_host = urlparse(origin_header).hostname or ""
    allowed = urlparse(raw["domain"]).hostname or ""

    if allowed.startswith("*."):
        base = allowed[2:]
        return request_host == base or request_host.endswith("." + base)

    return request_host == allowed

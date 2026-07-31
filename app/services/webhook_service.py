import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = 3.0


async def dispatch_webhook(url: str, lead_summary: dict) -> bool:
    """POST lead_summary to url, fail-open.

    Never raises: every failure mode (timeout, DNS failure, connection
    refused, non-2xx response, unexpected exception) is caught, logged,
    and reported as False so the caller's response path is unaffected.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await asyncio.wait_for(
                client.post(url, json=lead_summary), timeout=WEBHOOK_TIMEOUT
            )
    except asyncio.TimeoutError:
        logger.warning("webhook timeout for %s (>%.1fs)", url, WEBHOOK_TIMEOUT)
        return False
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        logger.warning("webhook request error for %s: %s", url, exc)
        return False
    except Exception as exc:
        logger.warning("webhook dispatch failed for %s: %s", url, exc)
        return False

    if 200 <= resp.status_code < 300:
        return True

    logger.warning("webhook %s returned %d", url, resp.status_code)
    return False

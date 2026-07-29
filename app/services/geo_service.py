import asyncio
import json
import logging
import os
from typing import Any

import httpx

from app.core.queue import get_connection

GEO_CACHE_TTL = 86400
GEO_CACHE_PREFIX = "geo:ip:"

logger = logging.getLogger(__name__)

IPAPI_CO_URL = "https://ipapi.co/{ip}/json/"
IPINFO_URL = "https://ipinfo.io/{ip}?token={token}"
IPAPI_COM_URL = "https://ip-api.com/json/{ip}"

PROVIDER_TIMEOUT = 3.0


def _get_cache_key(ip: str) -> str:
    return f"{GEO_CACHE_PREFIX}{ip}"


def get_cached_geo(ip: str) -> dict[str, Any] | None:
    conn = get_connection()
    data = conn.get(_get_cache_key(ip))
    if data:
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def set_cached_geo(ip: str, data: dict[str, Any]) -> None:
    conn = get_connection()
    conn.setex(_get_cache_key(ip), GEO_CACHE_TTL, json.dumps(data))


async def _call_ipapi(ip: str) -> dict[str, Any] | None:
    url = IPAPI_CO_URL.format(ip=ip)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("error"):
                    logger.warning(
                        "ipapi.co error for %s: %s", ip, data.get("reason", "unknown")
                    )
                    return None
                return {
                    "country": data.get("country_name"),
                    "city": data.get("city"),
                    "region": data.get("region"),
                    "isp": data.get("org"),
                    "provider": "ipapi",
                }
            logger.warning("ipapi.co returned %d for %s", resp.status_code, ip)
            return None
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.warning("ipapi.co timeout/error for %s: %s", ip, e)
        return None


async def _call_ipinfo(ip: str) -> dict[str, Any] | None:
    token = os.getenv("IPINFO_TOKEN", "")
    if not token:
        logger.warning("IPINFO_TOKEN not set, skipping ipinfo.io")
        return None
    url = IPINFO_URL.format(ip=ip, token=token)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "country": data.get("country"),
                    "city": data.get("city"),
                    "region": data.get("region"),
                    "isp": data.get("org"),
                    "provider": "ipinfo",
                }
            logger.warning("ipinfo.io returned %d for %s", resp.status_code, ip)
            return None
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.warning("ipinfo.io timeout/error for %s: %s", ip, e)
        return None


async def _call_ipapi_com(ip: str) -> dict[str, Any] | None:
    url = IPAPI_COM_URL.format(ip=ip)
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return {
                        "country": data.get("country"),
                        "city": data.get("city"),
                        "region": data.get("regionName"),
                        "isp": data.get("isp"),
                        "provider": "ip-api",
                    }
                logger.warning(
                    "ip-api.com error for %s: %s",
                    ip,
                    data.get("message", "unknown"),
                )
                return None
            logger.warning("ip-api.com returned %d for %s", resp.status_code, ip)
            return None
    except (httpx.TimeoutException, httpx.RequestError) as e:
        logger.warning("ip-api.com timeout/error for %s: %s", ip, e)
        return None


async def _call_with_timeout(coro, ip: str, provider_name: str) -> dict | None:
    try:
        return await asyncio.wait_for(coro, timeout=PROVIDER_TIMEOUT)
    except asyncio.TimeoutError:
        logger.warning("%s timeout for %s (>%ds)", provider_name, ip, PROVIDER_TIMEOUT)
        return None


def geo_enrich(ip: str) -> dict[str, Any] | None:
    if not ip or ip in ("unknown", "127.0.0.1", "::1", "localhost"):
        return None

    cached = get_cached_geo(ip)
    if cached:
        logger.info("Geo cache hit for %s", ip)
        return cached

    async def _chain():
        result = await _call_with_timeout(_call_ipapi(ip), ip, "ipapi.co")
        if result:
            return result
        result = await _call_with_timeout(_call_ipinfo(ip), ip, "ipinfo.io")
        if result:
            return result
        result = await _call_with_timeout(_call_ipapi_com(ip), ip, "ip-api.com")
        if result:
            return result
        return None

    result = asyncio.run(_chain())
    if result:
        set_cached_geo(ip, result)
    return result

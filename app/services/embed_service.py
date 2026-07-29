import json

CONFIG_CACHE_TTL = 300


def _get_redis():
    try:
        from app.main import get_redis

        return get_redis()
    except (ImportError, RuntimeError):
        return None


async def get_raw_widget(widget_id: str) -> dict | None:
    from app.services.widget_service import _get_repo

    repo = _get_repo()
    return await repo.get_by_id_raw(widget_id)


async def get_widget_config(widget_id: str) -> dict | None:
    redis = _get_redis()
    cache_key = f"widget:config:{widget_id}"

    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    raw = await get_raw_widget(widget_id)
    if raw is None or not raw.get("active", False):
        return None

    config = raw.get("config", {})
    result = {
        "widget_id": widget_id,
        "brand_color": config.get("brand_color", "#2563eb"),
        "button_text": config.get("button_text", "Get a Quote"),
        "fields": config.get("fields", ["name", "email"]),
        "success_message": config.get("success_message", "Thanks!"),
        "honeypot_field": config.get("honeypot_field", "_hp_a3f9"),
    }

    if redis:
        try:
            await redis.setex(cache_key, CONFIG_CACHE_TTL, json.dumps(result))
        except Exception:
            pass

    return result

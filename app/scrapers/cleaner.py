import logging
import re
from typing import Any

from app.models.scraped_book import ScrapedBookCreate

logger = logging.getLogger(__name__)

RATING_MAP = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


def _clean_price(raw: str) -> float | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", raw)
    try:
        return round(float(cleaned), 2)
    except (ValueError, TypeError):
        return None


def _clean_rating(raw: str) -> int | None:
    if not raw:
        return None
    return RATING_MAP.get(raw.strip().lower())


def _clean_availability(raw: str) -> str | None:
    if not raw:
        return None
    cleaned = re.sub(r"\s+", " ", raw).strip()
    if cleaned.lower().startswith("in stock"):
        return "In Stock"
    if cleaned:
        return cleaned
    return None


def clean_book(raw: dict[str, Any]) -> ScrapedBookCreate | None:
    url = raw.get("url", "").strip()
    title = raw.get("title", "").strip()

    if not url or not title:
        logger.warning("Skipping book with missing url or title: %s", raw)
        return None

    price = _clean_price(raw.get("price_raw", ""))
    rating = _clean_rating(raw.get("rating_raw", ""))
    availability = _clean_availability(raw.get("availability_raw", ""))
    description = raw.get("description")
    category = raw.get("category")
    upc = raw.get("upc")
    image_url = raw.get("image_url")

    if description:
        description = description.strip() or None
    if category:
        category = category.strip() or None
    if upc:
        upc = upc.strip() or None
    if image_url:
        image_url = image_url.strip() or None

    return ScrapedBookCreate(
        url=url,
        title=title,
        price=price,
        availability=availability,
        rating=rating,
        description=description,
        category=category,
        upc=upc,
        image_url=image_url,
    )


def merge_listing_and_detail(listing_data: dict, detail_data: dict) -> dict:
    merged = dict(listing_data)
    for key, value in detail_data.items():
        if value is not None:
            merged[key] = value
    return merged

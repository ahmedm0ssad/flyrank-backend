import logging

from app.scrapers.cleaner import clean_book, merge_listing_and_detail
from app.scrapers.parser import (
    extract_next_page_url,
    parse_detail_page,
    parse_listing_page,
)
from app.scrapers.session import ScrapeSession

logger = logging.getLogger(__name__)

BASE_URL = "http://books.toscrape.com"
START_URL = f"{BASE_URL}/catalogue/page-1.html"


def run(
    max_pages: int = 5,
    base_url: str = BASE_URL,
    start_url: str = START_URL,
    session: ScrapeSession | None = None,
) -> tuple[list[dict], list[str]]:
    own_session = session is None
    if session is None:
        session = ScrapeSession(base_url)

    books: list[dict] = []
    errors: list[str] = []
    current_url: str | None = start_url
    page_count = 0

    try:
        while current_url and page_count < max_pages:
            page_count += 1
            logger.info("Fetching listing page %d: %s", page_count, current_url)

            html = session.fetch(current_url)
            if html is None:
                errors.append(f"Failed to fetch listing page: {current_url}")
                break

            listing_books = parse_listing_page(html, current_url)
            logger.info("Found %d books on page %d", len(listing_books), page_count)

            for listing_item in listing_books:
                detail_url = listing_item["url"]
                logger.debug("Fetching detail: %s", detail_url)

                detail_html = session.fetch(detail_url)
                if detail_html is None:
                    errors.append(f"Failed to fetch detail: {detail_url}")
                    continue

                detail_data = parse_detail_page(detail_html, detail_url)
                merged = merge_listing_and_detail(listing_item, detail_data)
                cleaned = clean_book(merged)

                if cleaned is not None:
                    books.append(cleaned.model_dump())
                else:
                    errors.append(f"Failed to clean book: {detail_url}")

            current_url = extract_next_page_url(html, current_url)

    finally:
        if own_session:
            session.close()

    logger.info(
        "Scrape complete: %d pages, %d books, %d errors",
        page_count,
        len(books),
        len(errors),
    )
    return books, errors

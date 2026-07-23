import asyncio
import logging
import time

from app.database import is_postgres_enabled
from app.models.scraped_book import ScrapedBookCreate

if is_postgres_enabled():
    from app.repositories.scraped_book_repo import ScrapedBookRepository
    from app.scrapers import pipeline

    _repo = ScrapedBookRepository()

    async def start_scrape(max_pages: int = 5) -> dict:
        start = time.monotonic()

        books_data, errors = await asyncio.to_thread(pipeline.run, max_pages)

        books = [ScrapedBookCreate(**b) for b in books_data]
        saved = []
        if books:
            saved = await _repo.bulk_upsert(books)

        duration = round(time.monotonic() - start, 2)

        logging.getLogger(__name__).info(
            "Scrape finished: %d scraped, %d saved, %d errors in %.2fs",
            len(books),
            len(saved),
            len(errors),
            duration,
        )

        return {
            "books_scraped": len(books),
            "books_saved": len(saved),
            "errors": errors,
            "duration_seconds": duration,
        }
else:
    async def start_scrape(max_pages: int = 5) -> dict:
        return {
            "books_scraped": 0,
            "books_saved": 0,
            "errors": ["Postgres is not configured — cannot store scraped data"],
            "duration_seconds": 0,
        }

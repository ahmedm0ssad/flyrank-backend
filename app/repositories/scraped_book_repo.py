from datetime import datetime, timezone
from typing import Optional

from app.database import get_pool
from app.models.scraped_book import ScrapedBookCreate, ScrapedBookResponse


class ScrapedBookRepository:
    @staticmethod
    async def create_book(data: ScrapedBookCreate) -> ScrapedBookResponse:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO scraped_books
                    (url, title, price, availability, rating, description, category, upc, image_url, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                RETURNING id, url, title, price, availability, rating, description, category, upc, image_url, created_at, updated_at
                """,
                data.url,
                data.title,
                data.price,
                data.availability,
                data.rating,
                data.description,
                data.category,
                data.upc,
                data.image_url,
                now,
                now,
            )
        return ScrapedBookResponse(**dict(row))

    @staticmethod
    async def bulk_upsert(
        books: list[ScrapedBookCreate],
    ) -> list[ScrapedBookResponse]:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        results: list[ScrapedBookResponse] = []

        async with pool.acquire() as conn:
            for book in books:
                row = await conn.fetchrow(
                    """
                    INSERT INTO scraped_books
                        (url, title, price, availability, rating, description, category, upc, image_url, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (url)
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        price = EXCLUDED.price,
                        availability = EXCLUDED.availability,
                        rating = EXCLUDED.rating,
                        description = EXCLUDED.description,
                        category = EXCLUDED.category,
                        upc = EXCLUDED.upc,
                        image_url = EXCLUDED.image_url,
                        updated_at = EXCLUDED.updated_at
                    RETURNING id, url, title, price, availability, rating, description, category, upc, image_url, created_at, updated_at
                    """,
                    book.url,
                    book.title,
                    book.price,
                    book.availability,
                    book.rating,
                    book.description,
                    book.category,
                    book.upc,
                    book.image_url,
                    now,
                    now,
                )
                results.append(ScrapedBookResponse(**dict(row)))

        return results

    @staticmethod
    async def get_all_books() -> list[ScrapedBookResponse]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, url, title, price, availability, rating, description, category, upc, image_url, created_at, updated_at FROM scraped_books ORDER BY id"
            )
        return [ScrapedBookResponse(**dict(r)) for r in rows]

    @staticmethod
    async def get_book_by_id(book_id: int) -> Optional[ScrapedBookResponse]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, url, title, price, availability, rating, description, category, upc, image_url, created_at, updated_at FROM scraped_books WHERE id = $1",
                book_id,
            )
        if row is None:
            return None
        return ScrapedBookResponse(**dict(row))

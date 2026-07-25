import pytest

from app.models.scraped_book import ScrapedBookCreate
from app.scrapers.cleaner import clean_book
from app.services import scraped_book_service


class TestScrapedBookService:
    @pytest.mark.asyncio
    async def test_start_scrape_postgres_disabled_returns_error(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.scraped_book_service.is_postgres_enabled", lambda: False
        )

        result = await scraped_book_service.start_scrape(max_pages=5)

        assert result["books_scraped"] == 0
        assert result["books_saved"] == 0
        assert len(result["errors"]) == 1
        assert "Postgres is not configured" in result["errors"][0]
        assert result["duration_seconds"] == 0

    @pytest.mark.asyncio
    async def test_start_scrape_default_max_pages(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.scraped_book_service.is_postgres_enabled", lambda: False
        )

        result = await scraped_book_service.start_scrape()

        assert result["books_scraped"] == 0
        assert result["books_saved"] == 0
        assert result["duration_seconds"] == 0

    def test_scraped_book_create_from_pipeline_data(self):
        data = {
            "url": "http://example.com/book1",
            "title": "Book 1",
            "price_raw": "£10.00",
            "rating_raw": "three",
            "availability_raw": "In stock",
        }
        result = clean_book(data)
        assert result is not None
        assert isinstance(result, ScrapedBookCreate)
        assert result.url == data["url"]
        assert result.title == data["title"]
        assert result.price == 10.0
        assert result.rating == 3
        assert result.availability == "In Stock"

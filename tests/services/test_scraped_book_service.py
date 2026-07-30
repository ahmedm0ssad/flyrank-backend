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

    @pytest.mark.asyncio
    async def test_start_scrape_postgres_enabled_path(self, monkeypatch):
        import importlib
        from unittest.mock import AsyncMock, MagicMock

        monkeypatch.setattr("app.core.database.is_postgres_enabled", lambda: True)
        import app.services.scraped_book_service as sbs

        importlib.reload(sbs)

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = (
            [{"url": "http://example.com/b1", "title": "Book 1"}],
            [],
        )
        monkeypatch.setattr("app.services.scraped_book_service.pipeline", mock_pipeline)

        mock_repo = AsyncMock()
        mock_repo.bulk_upsert = AsyncMock(return_value=[{"url": "http://example.com/b1"}])
        monkeypatch.setattr("app.services.scraped_book_service._repo", mock_repo)

        result = await sbs.start_scrape(max_pages=5)
        assert result["books_scraped"] == 1
        assert result["books_saved"] == 1
        assert result["errors"] == []

        monkeypatch.setattr("app.core.database.is_postgres_enabled", lambda: False)
        importlib.reload(sbs)

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

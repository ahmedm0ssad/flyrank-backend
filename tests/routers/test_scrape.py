import types

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def mock_scrape_service(monkeypatch):
    async def start_scrape(max_pages: int = 5):
        return {
            "books_scraped": 10,
            "books_saved": 10,
            "errors": [],
            "duration_seconds": 3.45,
        }

    mock_module = types.ModuleType("scraped_book_service")
    mock_module.start_scrape = start_scrape
    monkeypatch.setattr("app.routers.scrape.scraped_book_service", mock_module)
    return mock_module


class TestTriggerScrape:
    def test_scrape_success(self, client: TestClient):
        response = client.post("/scrape/")

        assert response.status_code == 200
        data = response.json()
        assert data["books_scraped"] == 10
        assert data["books_saved"] == 10
        assert data["errors"] == []
        assert "duration_seconds" in data

    def test_scrape_with_custom_max_pages(self, client: TestClient):
        response = client.post("/scrape/?max_pages=3")

        assert response.status_code == 200
        data = response.json()
        assert data["books_scraped"] == 10

    def test_scrape_default_max_pages(self, client: TestClient, monkeypatch):
        captured = {}

        async def capture(max_pages: int = 5):
            captured["max_pages"] = max_pages
            return {
                "books_scraped": 0,
                "books_saved": 0,
                "errors": [],
                "duration_seconds": 0,
            }

        mock_module = types.ModuleType("scraped_book_service")
        mock_module.start_scrape = capture
        monkeypatch.setattr("app.routers.scrape.scraped_book_service", mock_module)

        client.post("/scrape/")
        assert captured["max_pages"] == 5

    def test_scrape_passes_max_pages(self, client: TestClient, monkeypatch):
        captured = {}

        async def capture(max_pages: int = 5):
            captured["max_pages"] = max_pages
            return {
                "books_scraped": 0,
                "books_saved": 0,
                "errors": [],
                "duration_seconds": 0,
            }

        mock_module = types.ModuleType("scraped_book_service")
        mock_module.start_scrape = capture
        monkeypatch.setattr("app.routers.scrape.scraped_book_service", mock_module)

        client.post("/scrape/?max_pages=3")
        assert captured["max_pages"] == 3

import os

os.environ["DATABASE_URL"] = ""
os.environ["REDIS_URL"] = ""
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_KEY"] = "test-anon-key"


import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def _no_postgres(monkeypatch):
    monkeypatch.setattr("app.main.is_postgres_enabled", lambda: False)
    monkeypatch.setattr("app.database.is_postgres_enabled", lambda: False)
    monkeypatch.setattr("app.services.task_service.is_postgres_enabled", lambda: False)
    monkeypatch.setattr(
        "app.services.scraped_book_service.is_postgres_enabled", lambda: False
    )


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_book_data() -> dict:
    return {
        "url": "http://books.toscrape.com/catalogue/test_1000/index.html",
        "title": "Test Book",
        "price": 51.77,
        "availability": "In Stock",
        "rating": 3,
        "description": "A test book description",
        "category": "Fiction",
        "upc": "abc123def456",
        "image_url": "http://books.toscrape.com/media/cache/test.jpg",
    }


@pytest.fixture
def sample_task_data() -> dict:
    return {"title": "Test Task", "done": False}

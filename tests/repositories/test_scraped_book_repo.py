from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.scraped_book import ScrapedBookCreate
from app.repositories.scraped_book_repo import ScrapedBookRepository


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    return conn


@pytest.fixture
def mock_pool_and_conn(mock_conn):
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__.return_value = mock_conn
    cm.__aexit__.return_value = None
    pool.acquire.return_value = cm
    return pool, mock_conn


@pytest.fixture(autouse=True)
def patch_get_pool(mock_pool_and_conn):
    pool, _ = mock_pool_and_conn
    with patch(
        "app.repositories.scraped_book_repo.get_pool", new=AsyncMock(return_value=pool)
    ):
        yield


from collections.abc import Mapping


class _MockRecord(Mapping):
    def __init__(self, values: dict):
        self._values = values
    def __getitem__(self, key):
        return self._values[key]
    def __iter__(self):
        return iter(self._values.keys())
    def __len__(self):
        return len(self._values)


def _make_record(values: dict):
    return _MockRecord(values)


@pytest.mark.asyncio
class TestScrapedBookRepository:
    async def test_create_book(self, mock_conn, sample_book_data):
        now = datetime.now(timezone.utc)
        values = {"id": 1, **sample_book_data, "created_at": now, "updated_at": now}
        mock_conn.fetchrow.return_value = _make_record(values)

        result = await ScrapedBookRepository.create_book(
            ScrapedBookCreate(**sample_book_data)
        )

        assert result.id == 1
        assert result.title == sample_book_data["title"]
        assert result.price == sample_book_data["price"]
        mock_conn.fetchrow.assert_awaited_once()

    async def test_get_all_books(self, mock_conn, sample_book_data):
        now = datetime.now(timezone.utc)
        values = {"id": 1, **sample_book_data, "created_at": now, "updated_at": now}
        mock_conn.fetch.return_value = [_make_record(values)]

        results = await ScrapedBookRepository.get_all_books()
        assert len(results) == 1
        assert results[0].title == sample_book_data["title"]

    async def test_get_book_by_id_found(self, mock_conn, sample_book_data):
        now = datetime.now(timezone.utc)
        values = {"id": 1, **sample_book_data, "created_at": now, "updated_at": now}
        mock_conn.fetchrow.return_value = _make_record(values)

        result = await ScrapedBookRepository.get_book_by_id(1)
        assert result is not None
        assert result.id == 1
        assert result.url == sample_book_data["url"]

    async def test_get_book_by_id_not_found(self, mock_conn):
        mock_conn.fetchrow.return_value = None

        result = await ScrapedBookRepository.get_book_by_id(999)
        assert result is None

    async def test_bulk_upsert(self, mock_conn, sample_book_data):
        now = datetime.now(timezone.utc)
        values = {"id": 1, **sample_book_data, "created_at": now, "updated_at": now}
        mock_conn.fetchrow.return_value = _make_record(values)

        books = [ScrapedBookCreate(**sample_book_data)]
        results = await ScrapedBookRepository.bulk_upsert(books)

        assert len(results) == 1
        assert results[0].title == sample_book_data["title"]
        mock_conn.fetchrow.assert_awaited_once()

    async def test_bulk_upsert_empty_list(self, mock_conn):
        results = await ScrapedBookRepository.bulk_upsert([])
        assert results == []
        mock_conn.fetchrow.assert_not_awaited()

    async def test_bulk_upsert_multiple_books(self, mock_conn):
        now = datetime.now(timezone.utc)
        values1 = {
            "id": 1,
            "url": "http://example.com/book1",
            "title": "Book 1",
            "price": 10.0,
            "availability": None,
            "rating": None,
            "description": None,
            "category": None,
            "upc": None,
            "image_url": None,
            "created_at": now,
            "updated_at": now,
        }
        values2 = {
            "id": 2,
            "url": "http://example.com/book2",
            "title": "Book 2",
            "price": 20.0,
            "availability": None,
            "rating": None,
            "description": None,
            "category": None,
            "upc": None,
            "image_url": None,
            "created_at": now,
            "updated_at": now,
        }
        mock_conn.fetchrow.side_effect = [
            _make_record(values1),
            _make_record(values2),
        ]

        books = [
            ScrapedBookCreate(url="http://example.com/book1", title="Book 1"),
            ScrapedBookCreate(url="http://example.com/book2", title="Book 2"),
        ]
        results = await ScrapedBookRepository.bulk_upsert(books)

        assert len(results) == 2
        assert results[0].title == "Book 1"
        assert results[1].title == "Book 2"
        assert mock_conn.fetchrow.await_count == 2

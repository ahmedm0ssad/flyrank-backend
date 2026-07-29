from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.scraped_book import (
    ScrapedBookCreate,
    ScrapedBookResponse,
)


class TestScrapedBookCreate:
    def test_valid_create(self, sample_book_data):
        data = ScrapedBookCreate(**sample_book_data)
        assert data.url == sample_book_data["url"]
        assert data.title == sample_book_data["title"]
        assert data.price == 51.77
        assert data.rating == 3

    def test_all_optionals_default_to_none(self):
        data = ScrapedBookCreate(url="http://example.com/book", title="Minimal")
        assert data.price is None
        assert data.availability is None
        assert data.rating is None
        assert data.description is None
        assert data.category is None
        assert data.upc is None
        assert data.image_url is None

    def test_url_max_length_enforced(self):
        with pytest.raises(ValidationError):
            ScrapedBookCreate(url="x" * 501, title="Book")

    def test_title_min_length_enforced(self):
        with pytest.raises(ValidationError):
            ScrapedBookCreate(url="http://example.com/book", title="")

    def test_title_max_length_enforced(self):
        with pytest.raises(ValidationError):
            ScrapedBookCreate(url="http://example.com/book", title="x" * 501)

    def test_missing_url(self):
        with pytest.raises(ValidationError):
            ScrapedBookCreate(title="Book")

    def test_missing_title(self):
        with pytest.raises(ValidationError):
            ScrapedBookCreate(url="http://example.com/book")

    def test_price_as_none(self):
        data = ScrapedBookCreate(
            url="http://example.com/book", title="Book", price=None
        )
        assert data.price is None

    def test_rating_out_of_range_accepted(self):
        data = ScrapedBookCreate(url="http://example.com/book", title="Book", rating=10)
        assert data.rating == 10


class TestScrapedBookResponse:
    def test_valid_response(self, sample_book_data):
        now = datetime.now(timezone.utc)
        data = ScrapedBookResponse(
            id=1, **sample_book_data, created_at=now, updated_at=now
        )
        assert data.id == 1
        assert data.title == sample_book_data["title"]

    def test_missing_id_raises(self, sample_book_data):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            ScrapedBookResponse(**sample_book_data, created_at=now, updated_at=now)

    def test_all_optionals_none(self):
        now = datetime.now(timezone.utc)
        data = ScrapedBookResponse(
            id=1,
            url="http://example.com/book",
            title="Book",
            created_at=now,
            updated_at=now,
        )
        assert data.price is None
        assert data.description is None

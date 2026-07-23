import pytest

from app.models.scraped_book import ScrapedBookCreate
from app.scrapers.cleaner import (
    _clean_availability,
    _clean_price,
    _clean_rating,
    clean_book,
    merge_listing_and_detail,
)


class TestCleanPrice:
    def test_cleans_gbp_price(self):
        assert _clean_price("£51.77") == 51.77

    def test_cleans_price_with_extra_text(self):
        assert _clean_price("Price: $25.99") == 25.99

    def test_returns_none_for_empty_string(self):
        assert _clean_price("") is None

    def test_returns_none_for_none(self):
        assert _clean_price(None) is None

    def test_handles_integer_string(self):
        assert _clean_price("£10") == 10.0

    def test_returns_none_for_garbage(self):
        assert _clean_price("N/A") is None

    def test_rounds_to_two_decimals(self):
        assert _clean_price("£10.456") == 10.46


class TestCleanRating:
    def test_cleans_lowercase(self):
        assert _clean_rating("five") == 5

    def test_cleans_title_case(self):
        assert _clean_rating("Three") == 3

    def test_returns_none_for_invalid(self):
        assert _clean_rating("six") is None

    def test_returns_none_for_empty(self):
        assert _clean_rating("") is None

    def test_returns_none_for_none(self):
        assert _clean_rating(None) is None

    def test_strips_whitespace(self):
        assert _clean_rating("  four  ") == 4


class TestCleanAvailability:
    def test_normalizes_in_stock(self):
        assert _clean_availability("In stock (22 available)") == "In Stock"

    def test_returns_original_if_not_in_stock(self):
        assert _clean_availability("Out of stock") == "Out of stock"

    def test_returns_none_for_empty(self):
        assert _clean_availability("") is None

    def test_returns_none_for_none(self):
        assert _clean_availability(None) is None

    def test_normalizes_whitespace(self):
        assert _clean_availability("  In   stock  ") == "In Stock"


class TestCleanBook:
    def test_clean_valid_book(self):
        raw = {
            "url": "http://books.toscrape.com/catalogue/test_1000/index.html",
            "title": "Test Book",
            "price_raw": "£51.77",
            "rating_raw": "three",
            "availability_raw": "In stock",
            "description": "A great book",
            "category": "Fiction",
            "upc": "abc123",
            "image_url": "http://example.com/img.jpg",
        }
        result = clean_book(raw)
        assert result is not None
        assert isinstance(result, ScrapedBookCreate)
        assert result.url == raw["url"]
        assert result.title == raw["title"]
        assert result.price == 51.77
        assert result.rating == 3
        assert result.availability == "In Stock"
        assert result.description == "A great book"
        assert result.category == "Fiction"
        assert result.upc == "abc123"
        assert result.image_url == "http://example.com/img.jpg"

    def test_clean_book_no_optionals(self):
        raw = {
            "url": "http://example.com/book",
            "title": "Minimal Book",
        }
        result = clean_book(raw)
        assert result is not None
        assert result.url == raw["url"]
        assert result.title == raw["title"]
        assert result.price is None
        assert result.rating is None
        assert result.availability is None

    def test_clean_book_missing_url(self):
        raw = {"title": "No URL"}
        result = clean_book(raw)
        assert result is None

    def test_clean_book_empty_url(self):
        raw = {"url": "", "title": "Book"}
        result = clean_book(raw)
        assert result is None

    def test_clean_book_missing_title(self):
        raw = {"url": "http://example.com/book"}
        result = clean_book(raw)
        assert result is None

    def test_clean_book_empty_title(self):
        raw = {"url": "http://example.com/book", "title": ""}
        result = clean_book(raw)
        assert result is None

    def test_clean_book_strips_whitespace(self):
        raw = {
            "url": "  http://example.com/book  ",
            "title": "  My Book  ",
            "description": "  Desc  ",
            "category": "  Non-Fiction  ",
            "upc": "  abc  ",
            "image_url": "  http://example.com/img.jpg  ",
        }
        result = clean_book(raw)
        assert result.url == "http://example.com/book"
        assert result.title == "My Book"
        assert result.description == "Desc"
        assert result.category == "Non-Fiction"
        assert result.upc == "abc"
        assert result.image_url == "http://example.com/img.jpg"


class TestMergeListingAndDetail:
    def test_detail_overrides_listing(self):
        listing = {"url": "http://example.com/1", "title": "Listing Title", "price_raw": "£10"}
        detail = {"title": "Detail Title", "description": "A desc"}
        merged = merge_listing_and_detail(listing, detail)
        assert merged["url"] == "http://example.com/1"
        assert merged["title"] == "Detail Title"
        assert merged["price_raw"] == "£10"
        assert merged["description"] == "A desc"

    def test_none_values_in_detail_do_not_override(self):
        listing = {"url": "http://example.com/1", "title": "Listing", "price_raw": "£10"}
        detail = {"title": None, "price_raw": None}
        merged = merge_listing_and_detail(listing, detail)
        assert merged["title"] == "Listing"
        assert merged["price_raw"] == "£10"

    def test_listing_unchanged_when_detail_empty(self):
        listing = {"url": "http://example.com/1", "title": "Book"}
        merged = merge_listing_and_detail(listing, {})
        assert merged == listing

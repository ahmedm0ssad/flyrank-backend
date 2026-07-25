from app.scrapers.parser import (
    extract_next_page_url,
    parse_detail_page,
    parse_listing_page,
)

LISTING_HTML = """
<html><body>
<article class="product_pod">
    <h3><a href="catalogue/a-light_1000/index.html" title="A Light in the Attic">A Light in the Attic</a></h3>
    <p class="star-rating Three"></p>
    <p class="price_color">£51.77</p>
    <p class="instock availability">In stock</p>
</article>
<article class="product_pod">
    <h3><a href="catalogue/tipping_1001/index.html" title="Tipping the Velvet">Tipping the Velvet</a></h3>
    <p class="star-rating One"></p>
    <p class="price_color">£53.74</p>
    <p class="instock availability">In stock</p>
</article>
</body></html>
"""

EMPTY_LISTING_HTML = "<html><body></body></html>"

DETAIL_HTML = """
<html><body>
<h1>A Light in the Attic</h1>
<table class="table table-striped">
    <tr><th>UPC</th><td>a897fe39b8b8d634</td></tr>
    <tr><th>Price (incl. tax)</th><td>£51.77</td></tr>
    <tr><th>Availability</th><td>In stock (22 available)</td></tr>
</table>
<div id="product_description">Description</div>
<p>This is a test description for the book.</p>
<ul class="breadcrumb">
    <li><a href="#">Books</a></li>
    <li><a href="#">Fiction</a></li>
    <li><a href="#">Poetry</a></li>
</ul>
<div class="item active">
    <img src="../../media/cache/fe/72/fe72f0532301ec28571326f61a29e323.jpg" alt="..."/>
</div>
</body></html>
"""

DETAIL_NO_TABLE_HTML = """
<html><body>
<h1>No Table Book</h1>
</body></html>
"""

PAGINATION_HTML = """
<html><body>
<li class="next"><a href="catalogue/page-2.html">next</a></li>
</body></html>
"""

NO_NEXT_HTML = "<html><body></body></html>"


class TestParseListingPage:
    def test_returns_list_of_books(self):
        results = parse_listing_page(
            LISTING_HTML, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert len(results) == 2

    def test_parses_book_url(self):
        results = parse_listing_page(
            LISTING_HTML, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert "a-light_1000" in results[0]["url"]
        assert "tipping_1001" in results[1]["url"]

    def test_parses_title(self):
        results = parse_listing_page(
            LISTING_HTML, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert results[0]["title"] == "A Light in the Attic"
        assert results[1]["title"] == "Tipping the Velvet"

    def test_parses_rating_raw(self):
        results = parse_listing_page(
            LISTING_HTML, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert results[0]["rating_raw"] == "three"
        assert results[1]["rating_raw"] == "one"

    def test_parses_price_raw(self):
        results = parse_listing_page(
            LISTING_HTML, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert "£51.77" in results[0]["price_raw"]
        assert "£53.74" in results[1]["price_raw"]

    def test_parses_availability_raw(self):
        results = parse_listing_page(
            LISTING_HTML, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert results[0]["availability_raw"] == "In stock"

    def test_empty_html_returns_empty_list(self):
        results = parse_listing_page(
            EMPTY_LISTING_HTML, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert results == []


class TestParseDetailPage:
    def test_parses_title(self):
        result = parse_detail_page(
            DETAIL_HTML, "http://books.toscrape.com/catalogue/a-light_1000/index.html"
        )
        assert result["title"] == "A Light in the Attic"

    def test_parses_upc(self):
        result = parse_detail_page(
            DETAIL_HTML, "http://books.toscrape.com/catalogue/a-light_1000/index.html"
        )
        assert result["upc"] == "a897fe39b8b8d634"

    def test_parses_price_raw(self):
        result = parse_detail_page(
            DETAIL_HTML, "http://books.toscrape.com/catalogue/a-light_1000/index.html"
        )
        assert "£51.77" in result.get("price_raw", "")

    def test_parses_availability_raw(self):
        result = parse_detail_page(
            DETAIL_HTML, "http://books.toscrape.com/catalogue/a-light_1000/index.html"
        )
        assert "In stock" in result.get("availability_raw", "")

    def test_parses_description(self):
        result = parse_detail_page(
            DETAIL_HTML, "http://books.toscrape.com/catalogue/a-light_1000/index.html"
        )
        assert result["description"] == "This is a test description for the book."

    def test_parses_category(self):
        result = parse_detail_page(
            DETAIL_HTML, "http://books.toscrape.com/catalogue/a-light_1000/index.html"
        )
        assert result["category"] == "Poetry"

    def test_parses_image_url(self):
        result = parse_detail_page(
            DETAIL_HTML, "http://books.toscrape.com/catalogue/a-light_1000/index.html"
        )
        assert result["image_url"] is not None
        assert ".jpg" in result["image_url"]

    def test_no_table_returns_defaults(self):
        result = parse_detail_page(
            DETAIL_NO_TABLE_HTML, "http://books.toscrape.com/catalogue/test/index.html"
        )
        assert result["title"] == "No Table Book"
        assert result["upc"] is None
        assert result["description"] is None
        assert result["category"] is None
        assert result["image_url"] is None


class TestExtractNextPageUrl:
    def test_returns_next_url(self):
        result = extract_next_page_url(
            PAGINATION_HTML, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert result is not None
        assert "page-2" in result

    def test_returns_none_when_no_next(self):
        result = extract_next_page_url(
            NO_NEXT_HTML, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert result is None

    def test_returns_none_for_empty_html(self):
        result = extract_next_page_url(
            "", "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert result is None

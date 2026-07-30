import os

from app.scrapers.parser import (
    extract_next_page_url,
    parse_detail_page,
    parse_listing_page,
)

FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "fixtures", "scraper_html"
)


def _read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as f:
        return f.read()


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


class TestParseListingPageEdgeCases:
    def test_missing_h3_skips_article(self):
        html = (
            "<html><body>"
            '<article class="product_pod"><div>No h3</div></article>'
            '<article class="product_pod">'
            '<h3><a href="catalogue/b/index.html" title="B">B</a></h3>'
            '<p class="price_color">£5.00</p>'
            '<p class="instock availability">In stock</p>'
            '<p class="star-rating One"></p>'
            "</article>"
            "</body></html>"
        )
        results = parse_listing_page(html, "http://books.toscrape.com/")
        assert len(results) == 1
        assert results[0]["title"] == "B"

    def test_article_without_link_tag_skipped(self):
        html = (
            "<html><body>"
            '<article class="product_pod">'
            "<h3>No anchor</h3>"
            "</article>"
            '<article class="product_pod">'
            '<h3><a href="catalogue/b/index.html" title="B">B</a></h3>'
            '<p class="price_color">£5.00</p>'
            '<p class="instock availability">In stock</p>'
            '<p class="star-rating Two"></p>'
            "</article>"
            "</body></html>"
        )
        results = parse_listing_page(html, "http://books.toscrape.com/")
        assert len(results) == 1

    def test_empty_href_skipped(self):
        html = (
            "<html><body>"
            '<article class="product_pod">'
            '<h3><a href="" title="Empty href">Empty</a></h3>'
            '<p class="price_color">£5.00</p>'
            '<p class="instock availability">In stock</p>'
            '<p class="star-rating One"></p>'
            "</article>"
            '<article class="product_pod">'
            '<h3><a href="catalogue/b/index.html" title="B">B</a></h3>'
            '<p class="price_color">£5.00</p>'
            '<p class="instock availability">In stock</p>'
            '<p class="star-rating One"></p>'
            "</article>"
            "</body></html>"
        )
        results = parse_listing_page(html, "http://books.toscrape.com/")
        assert len(results) == 1

    def test_fallback_to_text_when_no_title(self):
        html = (
            "<html><body>"
            '<article class="product_pod">'
            '<h3><a href="catalogue/a/index.html">No Title Attr</a></h3>'
            '<p class="price_color">£10.00</p>'
            '<p class="instock availability">In stock</p>'
            '<p class="star-rating Four"></p>'
            "</article>"
            "</body></html>"
        )
        results = parse_listing_page(html, "http://books.toscrape.com/")
        assert len(results) == 1
        assert results[0]["title"] == "No Title Attr"

    def test_no_star_rating_tag_returns_empty(self):
        html = (
            "<html><body>"
            '<article class="product_pod">'
            '<h3><a href="catalogue/a/index.html" title="A">A</a></h3>'
            '<p class="price_color">£10.00</p>'
            '<p class="instock availability">In stock</p>'
            "</article>"
            "</body></html>"
        )
        results = parse_listing_page(html, "http://books.toscrape.com/")
        assert results[0]["rating_raw"] == ""

    def test_unmatched_rating_class_returns_empty(self):
        html = (
            "<html><body>"
            '<article class="product_pod">'
            '<h3><a href="catalogue/a/index.html" title="A">A</a></h3>'
            '<p class="price_color">£10.00</p>'
            '<p class="instock availability">In stock</p>'
            '<p class="star-rating Unknown"></p>'
            "</article>"
            "</body></html>"
        )
        results = parse_listing_page(html, "http://books.toscrape.com/")
        assert results[0]["rating_raw"] == ""

    def test_no_price_color_returns_empty(self):
        html = (
            "<html><body>"
            '<article class="product_pod">'
            '<h3><a href="catalogue/a/index.html" title="A">A</a></h3>'
            '<p class="star-rating Five"></p>'
            "</article>"
            "</body></html>"
        )
        results = parse_listing_page(html, "http://books.toscrape.com/")
        assert results[0]["price_raw"] == ""

    def test_no_availability_tag_returns_empty(self):
        html = (
            "<html><body>"
            '<article class="product_pod">'
            '<h3><a href="catalogue/a/index.html" title="A">A</a></h3>'
            '<p class="price_color">£10.00</p>'
            '<p class="star-rating Three"></p>'
            "</article>"
            "</body></html>"
        )
        results = parse_listing_page(html, "http://books.toscrape.com/")
        assert results[0]["availability_raw"] == ""

    def test_parses_from_fixture_file(self):
        html = _read_fixture("valid_listing.html")
        results = parse_listing_page(
            html, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert len(results) == 3
        assert "a-light-in-the-attic" in results[0]["url"]
        assert results[0]["title"] == "A Light in the Attic"
        assert results[0]["rating_raw"] == "three"
        assert "£51.77" in results[0]["price_raw"]
        assert results[1]["rating_raw"] == "one"
        assert results[2]["rating_raw"] == "one"

    def test_parses_malformed_fixture(self):
        html = _read_fixture("listing_malformed.html")
        results = parse_listing_page(
            html, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert len(results) == 4
        assert results[0]["title"] == "Minimal Book"
        assert results[1]["title"] == "No star rating"
        assert results[1]["rating_raw"] == ""
        assert results[2]["title"] == "No Title Attribute"
        assert results[3]["title"] == "Unmatched Rating"
        assert results[3]["rating_raw"] == ""


class TestParseDetailPageEdgeCases:
    def test_no_h1_returns_no_title(self):
        html = "<html><body><p>No heading</p></body></html>"
        result = parse_detail_page(html, "http://books.toscrape.com/")
        assert "title" not in result

    def test_table_row_without_header_skipped(self):
        html = (
            "<html><body>"
            '<table class="table table-striped">'
            "<tr><td>Only cells</td></tr>"
            "<tr><th>UPC</th><td>abc123</td></tr>"
            "</table>"
            "</body></html>"
        )
        result = parse_detail_page(html, "http://books.toscrape.com/")
        assert result["upc"] == "abc123"

    def test_table_row_without_cells_skipped(self):
        html = (
            "<html><body>"
            '<table class="table table-striped">'
            "<tr><th>Empty</th></tr>"
            "<tr><th>UPC</th><td>abc123</td></tr>"
            "</table>"
            "</body></html>"
        )
        result = parse_detail_page(html, "http://books.toscrape.com/")
        assert result["upc"] == "abc123"

    def test_no_product_description_div(self):
        html = "<html><body>" "<h1>Title</h1>" "<p>Some text</p>" "</body></html>"
        result = parse_detail_page(html, "http://books.toscrape.com/")
        assert result["description"] is None

    def test_description_div_without_sibling_p(self):
        html = (
            "<html><body>"
            "<h1>Title</h1>"
            '<div id="product_description">Desc</div>'
            "<div>Not a paragraph</div>"
            "</body></html>"
        )
        result = parse_detail_page(html, "http://books.toscrape.com/")
        assert result["description"] is None

    def test_breadcrumb_fewer_than_three_links(self):
        html = (
            "<html><body>"
            '<ul class="breadcrumb">'
            '<li><a href="#">Home</a></li>'
            '<li><a href="#">Books</a></li>'
            "</ul>"
            "</body></html>"
        )
        result = parse_detail_page(html, "http://books.toscrape.com/")
        assert result["category"] is None

    def test_no_breadcrumb(self):
        html = "<html><body><h1>Title</h1></body></html>"
        result = parse_detail_page(html, "http://books.toscrape.com/")
        assert result["category"] is None

    def test_no_item_active_div(self):
        html = (
            "<html><body>"
            "<h1>Title</h1>"
            "<div>No item active here</div>"
            "</body></html>"
        )
        result = parse_detail_page(html, "http://books.toscrape.com/")
        assert result["image_url"] is None

    def test_item_active_without_img(self):
        html = (
            "<html><body>"
            "<h1>Title</h1>"
            '<div class="item active"><p>No image here</p></div>'
            "</body></html>"
        )
        result = parse_detail_page(html, "http://books.toscrape.com/")
        assert result["image_url"] is None

    def test_item_active_img_without_src(self):
        html = (
            "<html><body>"
            "<h1>Title</h1>"
            '<div class="item active"><img alt="no src"/></div>'
            "</body></html>"
        )
        result = parse_detail_page(html, "http://books.toscrape.com/")
        assert result["image_url"] is None

    def test_parses_from_fixture_file(self):
        html = _read_fixture("detail_valid.html")
        result = parse_detail_page(
            html,
            "http://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        )
        assert result["title"] == "A Light in the Attic"
        assert result["upc"] == "a897fe39b8b8d634"
        assert "£51.77" in result.get("price_raw", "")
        assert "In stock" in result.get("availability_raw", "")
        assert "wonderful collection" in result["description"]
        assert result["category"] == "Poetry"
        assert ".jpg" in result["image_url"]

    def test_parses_malformed_fixture(self):
        html = _read_fixture("detail_malformed.html")
        result = parse_detail_page(
            html, "http://books.toscrape.com/catalogue/malformed/index.html"
        )
        assert "title" not in result
        assert result["upc"] == "abc123def456"
        assert result["description"] is not None
        assert result["category"] is None
        assert result["image_url"] is None


class TestExtractNextPageUrlEdgeCases:
    def test_next_li_without_anchor(self):
        html = '<html><body><li class="next"><span>No link</span></li></body></html>'
        result = extract_next_page_url(html, "http://books.toscrape.com/page-1.html")
        assert result is None

    def test_next_link_without_href(self):
        html = '<html><body><li class="next"><a>No href</a></li></body></html>'
        result = extract_next_page_url(html, "http://books.toscrape.com/page-1.html")
        assert result is None

    def test_parses_from_fixture_file(self):
        html = _read_fixture("listing_with_pagination.html")
        result = extract_next_page_url(
            html, "http://books.toscrape.com/catalogue/page-1.html"
        )
        assert result is not None
        assert "page-2" in result

from unittest.mock import MagicMock, patch

from app.scrapers.pipeline import run


class TestRunPipeline:
    def test_max_pages_respected(self):
        session = MagicMock()

        def fetch_side_effect(url):
            if "page" in url:
                html = "<html><body>"
                for i in range(5):
                    html += (
                        f'<article class="product_pod">'
                        f'<h3><a href="catalogue/book_{i}/index.html">Book {i}</a></h3>'
                        f'<p class="price_color">£10.00</p>'
                        f'<p class="star-rating Three">Three</p>'
                        f'<p class="instock availability">In stock</p>'
                        f"</article>"
                    )
                html += '<li class="next"><a href="page-2.html">next</a></li>'
                html += "</body></html>"
                return html
            if "book_" in url:
                return (
                    "<html><body>"
                    "<table>"
                    "<tr><th>UPC</th><td>abc123</td></tr>"
                    "<tr><th>Price (incl. tax)</th><td>£10.00</td></tr>"
                    "<tr><th>Availability</th><td>In stock</td></tr>"
                    "</table>"
                    "<div id='product_description'>A book</div>"
                    "<a href='../../category/fiction_1'>Fiction</a>"
                    "<img src='../../media/cache/test.jpg' />"
                    "</body></html>"
                )
            return None

        session.fetch.side_effect = fetch_side_effect
        session.close = MagicMock()

        base_url = "http://books.toscrape.com"
        start_url = f"{base_url}/catalogue/page-1.html"

        books, errors = run(
            max_pages=2, base_url=base_url, start_url=start_url, session=session
        )

        assert len(books) == 10
        assert len(errors) == 0
        assert session.fetch.call_count >= 12

    def test_fetch_listing_failure_returns_error(self):
        session = MagicMock()
        session.fetch.return_value = None
        session.close = MagicMock()

        books, errors = run(max_pages=1, session=session)
        assert len(books) == 0
        assert any("Failed to fetch listing page" in e for e in errors)

    def test_fetch_detail_failure_logs_error(self):
        session = MagicMock()

        def fetch_side_effect(url):
            if "page-1" in url or "catalogue/page-1" in url:
                html = (
                    "<html><body>"
                    '<article class="product_pod">'
                    '<h3><a href="catalogue/book_0/index.html">Book 0</a></h3>'
                    '<p class="price_color">£10.00</p>'
                    '<p class="star-rating Three">Three</p>'
                    '<p class="instock availability">In stock</p>'
                    "</article>"
                    "</body></html>"
                )
                return html
            return None

        session.fetch.side_effect = fetch_side_effect
        session.close = MagicMock()

        books, errors = run(max_pages=1, session=session)
        assert len(books) == 0
        assert any("Failed to fetch detail" in e for e in errors)

    def test_no_next_page_stops_early(self):
        session = MagicMock()

        def fetch_side_effect(url):
            if "page-1" in url or "catalogue/page-1" in url:
                html = (
                    "<html><body>"
                    '<article class="product_pod">'
                    '<h3><a href="catalogue/book_0/index.html">Book 0</a></h3>'
                    '<p class="price_color">£10.00</p>'
                    '<p class="star-rating Three">Three</p>'
                    '<p class="instock availability">In stock</p>'
                    "</article>"
                    "</body></html>"
                )
                return html
            if "book_" in url:
                return (
                    "<html><body>"
                    "<table>"
                    "<tr><th>UPC</th><td>abc123</td></tr>"
                    "<tr><th>Price (incl. tax)</th><td>£10.00</td></tr>"
                    "<tr><th>Availability</th><td>In stock</td></tr>"
                    "</table>"
                    "<div id='product_description'>A book</div>"
                    "<a href='../../category/fiction_1'>Fiction</a>"
                    "<img src='../../media/cache/test.jpg' />"
                    "</body></html>"
                )
            return None

        session.fetch.side_effect = fetch_side_effect
        session.close = MagicMock()

        books, errors = run(max_pages=5, session=session)
        assert len(books) == 1
        assert len(errors) == 0

    def test_creates_own_session_when_none_provided(self):
        with patch("app.scrapers.pipeline.ScrapeSession") as mock_session_cls:
            mock_session = MagicMock()

            def fetch_side_effect(url):
                if "page-1" in url or "catalogue/page-1" in url:
                    return (
                        "<html><body>"
                        '<article class="product_pod">'
                        '<h3><a href="catalogue/book_0/index.html">Book 0</a></h3>'
                        '<p class="price_color">£10.00</p>'
                        '<p class="star-rating Three">Three</p>'
                        '<p class="instock availability">In stock</p>'
                        "</article>"
                        "</body></html>"
                    )
                if "book_" in url:
                    return (
                        "<html><body>"
                        "<table><tr><th>UPC</th><td>x</td></tr></table>"
                        "</body></html>"
                    )
                return None

            mock_session.fetch.side_effect = fetch_side_effect
            mock_session_cls.return_value = mock_session

            _books, _errors = run(max_pages=1)

            mock_session_cls.assert_called_once()
            mock_session.close.assert_called_once()

    def test_failed_clean_returns_error(self):
        session = MagicMock()
        bad_html = (
            "<html><body>"
            '<article class="product_pod">'
            '<h3><a href="catalogue/book_0/index.html"></a></h3>'
            '<p class="price_color"></p>'
            '<p class="star-rating"></p>'
            '<p class="instock availability"></p>'
            "</article>"
            "</body></html>"
        )

        def fetch_side_effect(url):
            if "page-1" in url or "catalogue/page-1" in url:
                return bad_html
            if "book_" in url:
                return "<html><body><table></table></body></html>"
            return None

        session.fetch.side_effect = fetch_side_effect
        session.close = MagicMock()

        books, errors = run(max_pages=1, session=session)
        assert len(books) == 0
        assert any("Failed to clean book" in e for e in errors)

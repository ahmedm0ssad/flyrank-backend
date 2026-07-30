import os
from unittest.mock import MagicMock, patch

import requests

from app.scrapers.session import DEFAULT_DELAY, RobotsChecker, ScrapeSession

FIXTURE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "fixtures", "scraper_html"
)


def _read_fixture(name: str) -> str:
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as f:
        return f.read()


class TestRobotsChecker:
    def test_init(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        assert checker._base_url == "http://example.com"
        assert checker._user_agent == "TestBot/1.0"
        assert checker._disallowed_paths == []
        assert checker._crawl_delay == 0
        assert checker._loaded is False

    def test_is_allowed_returns_true_before_load(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        assert checker.is_allowed("http://example.com/any") is True

    def test_load_success(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "User-agent: *\nDisallow: /admin\nCrawl-delay: 2"
        session.get.return_value = resp

        checker.load(session)

        assert checker._loaded is True
        assert checker._disallowed_paths == ["/admin"]
        assert checker._crawl_delay == 2.0

    def test_load_no_robots(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 404
        session.get.return_value = resp

        checker.load(session)

        assert checker._loaded is True
        assert checker._disallowed_paths == []

    def test_load_failure(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        session = MagicMock()
        session.get.side_effect = requests.RequestException("Connection error")

        checker.load(session)

        assert checker._loaded is True
        assert checker._disallowed_paths == []

    def test_is_allowed_blocked(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        checker._disallowed_paths = ["/admin", "/private"]
        checker._loaded = True

        assert checker.is_allowed("http://example.com/admin") is False
        assert checker.is_allowed("http://example.com/private/data") is False
        assert checker.is_allowed("http://example.com/public") is True

    def test_is_allowed_wildcard(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        checker._disallowed_paths = ["/admin/*"]
        checker._loaded = True

        assert checker.is_allowed("http://example.com/admin/page") is False
        assert checker.is_allowed("http://example.com/admin/") is False

    def test_crawl_delay_property(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        checker._crawl_delay = 5
        assert checker.crawl_delay == 5.0

    def test_crawl_delay_default(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        assert checker.crawl_delay == DEFAULT_DELAY

    def test_parse_relevant_user_agent_star(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        checker._parse("User-agent: *\nDisallow: /admin")
        assert checker._disallowed_paths == ["/admin"]

    def test_parse_relevant_user_agent_specific(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        checker._parse("User-agent: TestBot\nDisallow: /api")
        assert checker._disallowed_paths == ["/api"]

    def test_parse_irrelevant_user_agent(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        checker._parse("User-agent: GoogleBot\nDisallow: /api")
        assert checker._disallowed_paths == []

    def test_parse_invalid_crawl_delay(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        checker._parse("User-agent: *\nCrawl-delay: not_a_number")
        assert checker._crawl_delay == 0

    def test_parse_no_false_positive_substring_bot(self):
        checker = RobotsChecker("http://example.com", "FlyRankBot/1.0")
        checker._parse("User-agent: Bot\nDisallow: /admin")
        assert checker._disallowed_paths == []

    def test_parse_no_false_positive_substring_rank(self):
        checker = RobotsChecker("http://example.com", "FlyRankBot/1.0")
        checker._parse("User-agent: Rank\nDisallow: /admin")
        assert checker._disallowed_paths == []

    def test_parse_true_positive_exact_match(self):
        checker = RobotsChecker("http://example.com", "FlyRankBot/1.0")
        checker._parse("User-agent: FlyRankBot\nDisallow: /api")
        assert checker._disallowed_paths == ["/api"]

    def test_parse_true_positive_prefix_match(self):
        checker = RobotsChecker("http://example.com", "FlyRankBot/1.0")
        checker._parse("User-agent: FlyRankBot/1.0\nDisallow: /data")
        assert checker._disallowed_paths == ["/data"]


class TestScrapeSession:
    def test_init_sets_default_delay(self):
        with patch("app.scrapers.session.RobotsChecker.load"):
            session = ScrapeSession("http://example.com")
            assert session._delay == DEFAULT_DELAY
            session.close()

    def test_init_uses_robots_crawl_delay(self):
        with (
            patch("app.scrapers.session.RobotsChecker.load"),
            patch(
                "app.scrapers.session.RobotsChecker.crawl_delay",
                new_callable=lambda: 5.0,
            ),
        ):
            session = ScrapeSession("http://example.com")
            assert session._delay == 5.0
            session.close()

    def test_fetch_blocked_by_robots(self):
        with patch("app.scrapers.session.RobotsChecker.load"):
            session = ScrapeSession("http://example.com")
            session._robots.is_allowed = MagicMock(return_value=False)
            result = session.fetch("http://example.com/admin")
            assert result is None
            session.close()

    def test_fetch_success(self):
        with patch("app.scrapers.session.RobotsChecker.load"):
            session = ScrapeSession("http://example.com")
            session._robots.is_allowed = MagicMock(return_value=True)
            mock_resp = MagicMock()
            mock_resp.text = "<html>OK</html>"
            session._session.get = MagicMock(return_value=mock_resp)

            result = session.fetch("http://example.com/page")

            assert result == "<html>OK</html>"
            session._session.get.assert_called_once_with(
                "http://example.com/page", timeout=10
            )
            session.close()

    def test_fetch_http_error(self):
        with patch("app.scrapers.session.RobotsChecker.load"):
            session = ScrapeSession("http://example.com")
            session._robots.is_allowed = MagicMock(return_value=True)
            session._session.get = MagicMock(
                side_effect=requests.RequestException("HTTP Error")
            )

            result = session.fetch("http://example.com/page")

            assert result is None
            session.close()

    def test_rate_limit_sleeps_when_needed(self, monkeypatch):
        import time

        with patch("app.scrapers.session.RobotsChecker.load"):
            session = ScrapeSession("http://example.com", delay=2.0)
            session._last_request_time = time.monotonic() - 0.5
            session._robots.is_allowed = MagicMock(return_value=True)
            mock_resp = MagicMock()
            mock_resp.text = "OK"
            session._session.get = MagicMock(return_value=mock_resp)

            sleeps = []

            def fake_sleep(secs):
                sleeps.append(secs)

            monkeypatch.setattr(time, "sleep", fake_sleep)

            session.fetch("http://example.com/page")

            assert len(sleeps) > 0
            assert sleeps[0] > 0
            session.close()

    def test_rate_limit_does_not_sleep_when_not_needed(self, monkeypatch):
        import time

        with patch("app.scrapers.session.RobotsChecker.load"):
            session = ScrapeSession("http://example.com", delay=2.0)
            session._last_request_time = time.monotonic() - 5.0
            session._robots.is_allowed = MagicMock(return_value=True)
            mock_resp = MagicMock()
            mock_resp.text = "OK"
            session._session.get = MagicMock(return_value=mock_resp)

            sleeps = []

            def fake_sleep(secs):
                sleeps.append(secs)

            monkeypatch.setattr(time, "sleep", fake_sleep)

            session.fetch("http://example.com/page")

            assert len(sleeps) == 0
            session.close()

    def test_close_calls_session_close(self):
        with patch("app.scrapers.session.RobotsChecker.load"):
            session = ScrapeSession("http://example.com")
            session._session.close = MagicMock()
            session.close()
            session._session.close.assert_called_once()

    def test_fetch_raises_for_status(self):
        with patch("app.scrapers.session.RobotsChecker.load"):
            session = ScrapeSession("http://example.com")
            session._robots.is_allowed = MagicMock(return_value=True)
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = requests.RequestException(
                "HTTP Error"
            )
            session._session.get = MagicMock(return_value=mock_resp)

            result = session.fetch("http://example.com/page")
            assert result is None
            session.close()


class TestRobotsCheckerFixtures:
    def test_load_with_robots_disallow_all_fixture(self):
        checker = RobotsChecker("http://books.toscrape.com", "FlyRankBot/1.0")
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.text = _read_fixture("robots_disallow_all.txt")
        session.get.return_value = resp

        checker.load(session)
        assert checker._loaded is True
        assert len(checker._disallowed_paths) == 1
        assert checker._disallowed_paths[0] == "/"
        assert checker._crawl_delay == 10.0

    def test_load_with_partial_robots_fixture(self):
        checker = RobotsChecker("http://books.toscrape.com", "FlyRankBot/1.0")
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.text = _read_fixture("robots_partial.txt")
        session.get.return_value = resp

        checker.load(session)
        assert checker._loaded is True
        assert "/admin" in checker._disallowed_paths
        assert "/private" in checker._disallowed_paths
        assert checker._crawl_delay == 5.0

    def test_load_with_no_match_robots_fixture(self):
        checker = RobotsChecker("http://books.toscrape.com", "FlyRankBot/1.0")
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.text = _read_fixture("robots_no_match.txt")
        session.get.return_value = resp

        checker.load(session)
        assert checker._loaded is True
        assert len(checker._disallowed_paths) == 0
        assert checker._crawl_delay == 0.0

    def test_parse_with_empty_disallow_path(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        checker._parse("User-agent: *\nDisallow:\nDisallow: /admin")
        assert checker._disallowed_paths == ["/admin"]

    def test_parse_with_multiple_ua_sections(self):
        checker = RobotsChecker("http://example.com", "TestBot/1.0")
        checker._parse(
            "User-agent: GoogleBot\nDisallow: /google-only\n\n"
            "User-agent: TestBot\nDisallow: /api\nDisallow: /secret\n"
            "Crawl-delay: 3\n\n"
            "User-agent: BingBot\nDisallow: /bing"
        )
        assert checker._disallowed_paths == ["/api", "/secret"]
        assert checker._crawl_delay == 3.0

    def test_parse_with_multi_section_robots_fixture(self):
        checker = RobotsChecker("http://books.toscrape.com", "FlyRankBot/1.0")
        checker._parse(_read_fixture("robots_multi_section.txt"))
        assert "/api" in checker._disallowed_paths
        assert "/admin" in checker._disallowed_paths
        assert checker._crawl_delay == 3.0

    def test_load_with_multi_section_robots_fixture(self):
        checker = RobotsChecker("http://books.toscrape.com", "FlyRankBot/1.0")
        session = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.text = _read_fixture("robots_multi_section.txt")
        session.get.return_value = resp

        checker.load(session)
        assert checker._loaded is True
        assert "/api" in checker._disallowed_paths
        assert "/admin" in checker._disallowed_paths
        assert checker._crawl_delay == 3.0

    def test_parse_blank_line_resets_relevance(self):
        checker = RobotsChecker("http://example.com", "FlyRankBot/1.0")
        checker._parse(
            "User-agent: *\nDisallow: /first\n\nDisallow: /leaked\n\n"
            "User-agent: OtherBot\nDisallow: /other"
        )
        assert checker._disallowed_paths == ["/first"]
        assert checker._crawl_delay == 0.0


class TestScrapeSessionFixtures:
    def test_fetch_with_robots_deny_all(self):
        with patch("app.scrapers.session.RobotsChecker.load"):
            session = ScrapeSession("http://books.toscrape.com")
            session._robots._disallowed_paths = ["/"]
            session._robots._loaded = True
            result = session.fetch("http://books.toscrape.com/any-page")
            assert result is None
            session.close()

    def test_fetch_from_robots_fixture_validated(self):
        with patch("app.scrapers.session.RobotsChecker.load"):
            session = ScrapeSession("http://books.toscrape.com")
            session._robots._loaded = True
            session._robots._disallowed_paths = ["/admin"]
            session._robots._crawl_delay = 0
            session._delay = 0
            mock_resp = MagicMock()
            mock_resp.text = _read_fixture("valid_listing.html")
            session._session.get = MagicMock(return_value=mock_resp)
            result = session.fetch("http://books.toscrape.com/catalogue/page-1.html")
            assert result is not None
            assert "product_pod" in result
            session.close()

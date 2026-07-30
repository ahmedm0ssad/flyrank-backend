import logging
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

USER_AGENT = (
    "FlyRankBot/1.0 (Educational Project; +https://github.com/flyrank/backend-ai)"
)
DEFAULT_TIMEOUT = 10
DEFAULT_DELAY = 1.0
MAX_RETRIES = 5


class RobotsChecker:
    def __init__(self, base_url: str, user_agent: str):
        self._base_url = base_url
        self._user_agent = user_agent
        self._disallowed_paths: list[str] = []
        self._crawl_delay: float = 0
        self._loaded = False

    def load(self, session: requests.Session) -> None:
        robots_url = urljoin(self._base_url, "/robots.txt")
        try:
            resp = session.get(robots_url, timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 200:
                self._parse(resp.text)
                logger.info("Loaded robots.txt from %s", robots_url)
            else:
                logger.info(
                    "No robots.txt at %s (status %s)", robots_url, resp.status_code
                )
        except requests.RequestException:
            logger.warning(
                "Failed to fetch robots.txt from %s — allowing all", robots_url
            )
        self._loaded = True

    def _parse(self, text: str) -> None:
        relevant = False
        for line in text.splitlines():
            line = line.strip()
            if not line:
                relevant = False
            elif line.lower().startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                relevant = agent == "*" or self._user_agent.lower().startswith(
                    agent.lower()
                )
            elif relevant:
                if line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        self._disallowed_paths.append(path)
                elif line.lower().startswith("crawl-delay:"):
                    try:
                        self._crawl_delay = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass

    def is_allowed(self, url: str) -> bool:
        if not self._loaded:
            return True
        path = urlparse(url).path
        for disallowed in self._disallowed_paths:
            pattern = re.escape(disallowed).replace(r"\*", ".*")
            if re.match(pattern, path):
                return False
        return True

    @property
    def crawl_delay(self) -> float:
        return self._crawl_delay if self._crawl_delay > 0 else DEFAULT_DELAY


class ScrapeSession:
    def __init__(self, base_url: str, delay: float = DEFAULT_DELAY):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})

        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

        self._robots = RobotsChecker(base_url, USER_AGENT)
        self._robots.load(self._session)

        self._delay = max(delay, self._robots.crawl_delay)
        self._last_request_time: float = 0

    def fetch(self, url: str) -> str | None:
        if not self._robots.is_allowed(url):
            logger.warning("Blocked by robots.txt: %s", url)
            return None

        self._rate_limit()

        try:
            resp = self._session.get(url, timeout=DEFAULT_TIMEOUT)
            resp.raise_for_status()
            self._last_request_time = time.monotonic()
            return resp.text
        except requests.RequestException as e:
            logger.error("Failed to fetch %s: %s", url, e)
            return None

    def _rate_limit(self) -> None:
        if self._last_request_time:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self._delay:
                sleep_for = self._delay - elapsed
                logger.debug("Rate limiting: sleeping %.2fs", sleep_for)
                time.sleep(sleep_for)

    def close(self) -> None:
        self._session.close()

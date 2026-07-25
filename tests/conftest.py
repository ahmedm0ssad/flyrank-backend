import os

os.environ["DATABASE_URL"] = ""
os.environ["REDIS_URL"] = ""
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_KEY"] = "test-anon-key"


import pytest
from fastapi.testclient import TestClient

from app.main import app


class _FakeRedis:
    def __init__(self):
        self._data: dict[str, dict[str, str]] = {}
        self._strings: dict[str, str] = {}

    def hset(self, key, mapping=None):
        if key not in self._data:
            self._data[key] = {}
        self._data[key].update(mapping or {})

    def hgetall(self, key):
        return self._data.get(key, {})

    def hincrby(self, key, field, amount=1):
        self._data.setdefault(key, {})
        current = int(self._data[key].get(field, 0))
        self._data[key][field] = str(current + amount)
        return current + amount

    def expire(self, key, ttl):
        pass

    def get(self, key):
        return self._strings.get(key)

    def setex(self, key, ttl, value):
        self._strings[key] = value

    def scan(self, cursor=0, match=None, count=10):
        keys = [
            k
            for k in self._data
            if match is None or k.startswith(match.replace("*", ""))
        ]
        return 0, keys

    def close(self):
        pass

    def ping(self):
        return True


class _FakeQueue:
    def __init__(self):
        self.enqueued_jobs: list[dict] = []

    def enqueue(self, func, *args, **kwargs):
        self.enqueued_jobs.append({"func": func, "args": args, "kwargs": kwargs})
        return type("Job", (), {"id": kwargs.get("job_id", "fake-id")})()


_fake_redis = _FakeRedis()
_fake_queue = _FakeQueue()


@pytest.fixture(autouse=True)
def _reset_queue(monkeypatch):
    _fake_redis._data.clear()
    _fake_redis._strings.clear()
    _fake_queue.enqueued_jobs.clear()
    monkeypatch.setattr("app.queue.get_connection", lambda: _fake_redis)
    monkeypatch.setattr("app.queue.get_queue", lambda: _fake_queue)


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

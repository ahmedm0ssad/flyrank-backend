import uuid

import pytest

from app.models.widget import WidgetCreate


class _FakeAsyncRedis:
    def __init__(self, sync_redis):
        self._sync = sync_redis

    async def get(self, key):
        return self._sync.get(key)

    async def setex(self, key, ttl, value):
        self._sync.setex(key, ttl, value)

    async def delete(self, key):
        self._sync._strings.pop(key, None)
        self._sync._data.pop(key, None)

    async def ping(self):
        return True


@pytest.fixture(autouse=True)
def _reset_widget_repo():
    from app.services.widget_service import _get_repo

    repo = _get_repo()
    repo._widgets.clear()


@pytest.fixture
def fake_redis():
    from tests.conftest import _fake_redis

    return _fake_redis


@pytest.fixture
def fake_async_redis(fake_redis):
    return _FakeAsyncRedis(fake_redis)


@pytest.fixture
def mock_redis(monkeypatch, fake_async_redis):
    monkeypatch.setattr("app.main.get_redis", lambda: fake_async_redis)
    yield fake_async_redis


@pytest.fixture
def sample_widget_data():
    return {
        "name": "Test Widget",
        "domain": "https://myshop.com",
        "config": {
            "brand_color": "#2563eb",
            "button_text": "Get a Quote",
            "fields": ["name", "email", "phone"],
            "success_message": "Thanks! We'll be in touch.",
        },
    }


@pytest.fixture
async def created_widget(sample_widget_data):
    from app.services import widget_service

    data = WidgetCreate(**sample_widget_data)
    widget = await widget_service.create_widget(data, "11111111-1111-1111-1111-111111111111")
    return widget


@pytest.fixture
def anyio_backend():
    return "asyncio"

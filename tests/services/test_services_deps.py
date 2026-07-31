import pytest

from app.dependencies import services


class TestGetRedis:
    @pytest.mark.asyncio
    async def test_returns_none_when_main_get_redis_raises(self, monkeypatch):
        services._redis = None

        def _raise():
            raise RuntimeError("no redis")

        monkeypatch.setattr("app.main.get_redis", _raise)
        assert await services.get_redis() is None

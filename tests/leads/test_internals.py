import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import lead_service


class TestGetRepo:
    def test_returns_lead_repository_instance(self):
        repo = lead_service._get_repo()
        from app.repositories.lead_repo import LeadRepository

        assert isinstance(repo, LeadRepository)


class TestGetOrCreateRepo:
    def test_returns_same_instance_on_calls(self):
        lead_service._repo = None
        repo1 = lead_service._get_or_create_repo()
        repo2 = lead_service._get_or_create_repo()
        assert repo1 is repo2


class TestGetRedis:
    @pytest.mark.asyncio
    async def test_returns_redis_client(self, monkeypatch):
        lead_service._redis_client = None
        fake_redis = MagicMock()
        monkeypatch.setattr("app.main.get_redis", lambda: fake_redis)
        result = await lead_service._get_redis()
        assert result is fake_redis

    @pytest.mark.asyncio
    async def test_returns_none_when_get_redis_fails(self):
        lead_service._redis_client = None
        with patch("app.main.get_redis", side_effect=RuntimeError("no redis")):
            result = await lead_service._get_redis()
            assert result is None


class TestCacheStats:
    @pytest.mark.asyncio
    async def test_caches_stats_in_redis(self, monkeypatch):
        fake_redis = AsyncMock()
        monkeypatch.setattr(
            "app.services.lead_service._get_redis", AsyncMock(return_value=fake_redis)
        )

        await lead_service._cache_stats("stats:widget:w1", {"total": 5}, ttl=300)
        fake_redis.setex.assert_awaited_once()
        args = fake_redis.setex.call_args[0]
        assert args[0] == "stats:widget:w1"
        assert json.loads(args[2]) == {"total": 5}
        assert args[1] == 300

    @pytest.mark.asyncio
    async def test_noop_when_redis_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.lead_service._get_redis", AsyncMock(return_value=None)
        )

        await lead_service._cache_stats("stats:widget:w1", {"total": 5})

    @pytest.mark.asyncio
    async def test_does_not_crash_on_redis_error(self, monkeypatch):
        fake_redis = AsyncMock()
        fake_redis.setex.side_effect = Exception("redis error")
        monkeypatch.setattr(
            "app.services.lead_service._get_redis", AsyncMock(return_value=fake_redis)
        )

        await lead_service._cache_stats("stats:widget:w1", {"total": 5})


class TestInvalidateStatsCache:
    @pytest.mark.asyncio
    async def test_deletes_widget_and_tenant_keys(self, monkeypatch):
        fake_redis = AsyncMock()
        monkeypatch.setattr(
            "app.services.lead_service._get_redis", AsyncMock(return_value=fake_redis)
        )

        await lead_service._invalidate_stats_cache(widget_id="w1", tenant_id="t1")
        assert fake_redis.delete.await_count == 2

    @pytest.mark.asyncio
    async def test_deletes_only_widget_key(self, monkeypatch):
        fake_redis = AsyncMock()
        monkeypatch.setattr(
            "app.services.lead_service._get_redis", AsyncMock(return_value=fake_redis)
        )

        await lead_service._invalidate_stats_cache(widget_id="w1")
        fake_redis.delete.assert_awaited_once_with("stats:widget:w1")

    @pytest.mark.asyncio
    async def test_deletes_only_tenant_key(self, monkeypatch):
        fake_redis = AsyncMock()
        monkeypatch.setattr(
            "app.services.lead_service._get_redis", AsyncMock(return_value=fake_redis)
        )

        await lead_service._invalidate_stats_cache(tenant_id="t1")
        fake_redis.delete.assert_awaited_once_with("stats:tenant:t1")

    @pytest.mark.asyncio
    async def test_noop_when_no_ids(self, monkeypatch):
        fake_redis = AsyncMock()
        monkeypatch.setattr(
            "app.services.lead_service._get_redis", AsyncMock(return_value=fake_redis)
        )

        await lead_service._invalidate_stats_cache()
        fake_redis.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_noop_when_redis_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.lead_service._get_redis", AsyncMock(return_value=None)
        )

        await lead_service._invalidate_stats_cache(widget_id="w1")

    @pytest.mark.asyncio
    async def test_does_not_crash_on_redis_error(self, monkeypatch):
        fake_redis = AsyncMock()
        fake_redis.delete.side_effect = Exception("redis error")
        monkeypatch.setattr(
            "app.services.lead_service._get_redis", AsyncMock(return_value=fake_redis)
        )

        await lead_service._invalidate_stats_cache(widget_id="w1")

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services import embed_service


class TestGetRedis:
    def test_returns_none_when_main_get_redis_unavailable(self):
        with patch("app.main.get_redis", side_effect=RuntimeError("no redis")):
            result = embed_service._get_redis()
            assert result is None


class TestGetRawWidget:
    @pytest.mark.asyncio
    async def test_returns_widget_data(self):
        mock_repo = AsyncMock()
        mock_repo.get_by_id_raw.return_value = {
            "id": "w1",
            "active": True,
            "config": {"brand_color": "#ff0000"},
        }
        with patch("app.services.widget_service._get_repo", return_value=mock_repo):
            result = await embed_service.get_raw_widget("w1")
            assert result is not None
            assert result["id"] == "w1"
            mock_repo.get_by_id_raw.assert_awaited_once_with("w1")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        mock_repo = AsyncMock()
        mock_repo.get_by_id_raw.return_value = None
        with patch("app.services.widget_service._get_repo", return_value=mock_repo):
            result = await embed_service.get_raw_widget("nonexistent")
            assert result is None


class TestGetWidgetConfig:
    @pytest.mark.asyncio
    async def test_returns_config_with_defaults(self, monkeypatch):
        monkeypatch.setattr("app.services.embed_service._get_redis", lambda: None)
        monkeypatch.setattr(
            "app.services.embed_service.get_raw_widget",
            AsyncMock(
                return_value={
                    "id": "w1",
                    "active": True,
                    "config": {"brand_color": "#ff0000", "button_text": "Send"},
                }
            ),
        )
        config = await embed_service.get_widget_config("w1")
        assert config is not None
        assert config["brand_color"] == "#ff0000"
        assert config["button_text"] == "Send"
        assert "fields" in config
        assert "honeypot_field" in config

    @pytest.mark.asyncio
    async def test_returns_none_when_inactive(self, monkeypatch):
        monkeypatch.setattr("app.services.embed_service._get_redis", lambda: None)
        monkeypatch.setattr(
            "app.services.embed_service.get_raw_widget",
            AsyncMock(return_value={"id": "w1", "active": False, "config": {}}),
        )
        config = await embed_service.get_widget_config("w1")
        assert config is None

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, monkeypatch):
        monkeypatch.setattr("app.services.embed_service._get_redis", lambda: None)
        monkeypatch.setattr(
            "app.services.embed_service.get_raw_widget",
            AsyncMock(return_value=None),
        )
        config = await embed_service.get_widget_config("nonexistent")
        assert config is None

    @pytest.mark.asyncio
    async def test_cache_hit_skips_raw_widget(self, monkeypatch):
        cached_config = json.dumps({"brand_color": "#00ff00", "fields": ["email"]})
        fake_redis = AsyncMock()
        fake_redis.get.return_value = cached_config

        monkeypatch.setattr("app.services.embed_service._get_redis", lambda: fake_redis)

        raw_mock = AsyncMock()
        monkeypatch.setattr("app.services.embed_service.get_raw_widget", raw_mock)

        config = await embed_service.get_widget_config("w1")
        assert config is not None
        assert config["brand_color"] == "#00ff00"
        raw_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_miss_sets_cache(self, monkeypatch):
        fake_redis = AsyncMock()
        fake_redis.get.return_value = None

        monkeypatch.setattr("app.services.embed_service._get_redis", lambda: fake_redis)
        monkeypatch.setattr(
            "app.services.embed_service.get_raw_widget",
            AsyncMock(
                return_value={
                    "id": "w1",
                    "active": True,
                    "config": {"brand_color": "#ff0000"},
                }
            ),
        )

        config = await embed_service.get_widget_config("w1")
        assert config is not None
        fake_redis.setex.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_redis_setex_failure_does_not_crash(self, monkeypatch):
        fake_redis = AsyncMock()
        fake_redis.get.return_value = None
        fake_redis.setex.side_effect = Exception("redis error")

        monkeypatch.setattr("app.services.embed_service._get_redis", lambda: fake_redis)
        monkeypatch.setattr(
            "app.services.embed_service.get_raw_widget",
            AsyncMock(
                return_value={
                    "id": "w1",
                    "active": True,
                    "config": {"brand_color": "#ff0000"},
                }
            ),
        )

        config = await embed_service.get_widget_config("w1")
        assert config is not None

    @pytest.mark.asyncio
    async def test_redis_get_failure_falls_through(self, monkeypatch):
        fake_redis = AsyncMock()
        fake_redis.get.side_effect = Exception("redis error")

        monkeypatch.setattr("app.services.embed_service._get_redis", lambda: fake_redis)
        monkeypatch.setattr(
            "app.services.embed_service.get_raw_widget",
            AsyncMock(
                return_value={
                    "id": "w1",
                    "active": True,
                    "config": {"brand_color": "#0000ff"},
                }
            ),
        )

        config = await embed_service.get_widget_config("w1")
        assert config is not None
        assert config["brand_color"] == "#0000ff"

from unittest.mock import MagicMock, patch

import pytest

from app.services import widget_service


class TestInvalidateCache:
    @pytest.mark.asyncio
    async def test_deletes_cache_key(self, monkeypatch):
        fake_redis = MagicMock()
        monkeypatch.setattr("app.main.get_redis", lambda: fake_redis)
        widget_service._redis_client = None

        await widget_service._invalidate_cache("w1")
        fake_redis.delete.assert_called_once_with("widget:config:w1")

    @pytest.mark.asyncio
    async def test_noop_when_redis_unavailable(self):
        widget_service._redis_client = None
        with patch("app.main.get_redis", side_effect=RuntimeError("no redis")):
            await widget_service._invalidate_cache("w1")

    @pytest.mark.asyncio
    async def test_does_not_crash_on_redis_error(self, monkeypatch):
        fake_redis = MagicMock()
        fake_redis.delete.side_effect = Exception("redis error")
        monkeypatch.setattr("app.main.get_redis", lambda: fake_redis)
        widget_service._redis_client = None

        await widget_service._invalidate_cache("w1")


class TestGenerateHoneypotField:
    def test_returns_prefixed_string(self):
        field = widget_service._generate_honeypot_field()
        assert field.startswith("_hp_")
        assert len(field) == 10

    def test_generates_unique_values(self):
        fields = {widget_service._generate_honeypot_field() for _ in range(100)}
        assert len(fields) > 90

    def test_contains_only_lowercase_and_digits(self):
        import re

        field = widget_service._generate_honeypot_field()
        assert re.match(r"^_hp_[a-z0-9]+$", field)


class TestGetRepo:
    def test_returns_repo_instance(self):
        repo = widget_service._get_repo()
        assert repo is not None

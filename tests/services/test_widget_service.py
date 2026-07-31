from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.widget import WidgetUpdate
from app.services import widget_service


class TestInvalidateCache:
    @pytest.mark.asyncio
    async def test_deletes_cache_key(self, monkeypatch):
        fake_redis = MagicMock()
        monkeypatch.setattr(
            "app.services.widget_service._get_redis_provider",
            AsyncMock(return_value=fake_redis),
        )

        await widget_service._invalidate_cache("w1")
        fake_redis.delete.assert_called_once_with("widget:config:w1")

    @pytest.mark.asyncio
    async def test_noop_when_redis_unavailable(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.widget_service._get_redis_provider",
            AsyncMock(return_value=None),
        )

        await widget_service._invalidate_cache("w1")

    @pytest.mark.asyncio
    async def test_does_not_crash_on_redis_error(self, monkeypatch):
        fake_redis = MagicMock()
        fake_redis.delete.side_effect = Exception("redis error")
        monkeypatch.setattr(
            "app.services.widget_service._get_redis_provider",
            AsyncMock(return_value=fake_redis),
        )

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


class TestUpdateWidget:
    @pytest.mark.asyncio
    async def test_returns_none_when_widget_not_found(self):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        result = await widget_service.update_widget(
            "00000000-0000-0000-0000-000000000000",
            "tenant-1",
            WidgetUpdate(name="Updated"),
            repo=mock_repo,
        )
        assert result is None


class TestWidgetServicePostgresBranch:
    def test_get_widget_repo_uses_postgres_when_enabled(self, monkeypatch):
        from app.dependencies import services
        from app.repositories.postgres_widget_repo import PostgresWidgetRepository

        services._widget_repo = None
        monkeypatch.setattr("app.core.database.is_postgres_enabled", lambda: True)
        try:
            assert isinstance(services.get_widget_repo(), PostgresWidgetRepository)
        finally:
            services._widget_repo = None
            monkeypatch.setattr("app.core.database.is_postgres_enabled", lambda: False)
            services.get_widget_repo()

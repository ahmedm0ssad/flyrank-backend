from unittest.mock import AsyncMock, patch

import pytest

from app.core.database import close_pool, get_pool, is_postgres_enabled


class TestIsPostgresEnabled:
    def test_returns_true_when_url_set(self, monkeypatch):
        monkeypatch.setattr(
            "app.core.database.DATABASE_URL", "postgresql://user:pass@localhost/db"
        )
        assert is_postgres_enabled() is True

    def test_returns_false_when_url_empty(self, monkeypatch):
        monkeypatch.setattr("app.core.database.DATABASE_URL", "")
        assert is_postgres_enabled() is False

    def test_returns_false_when_url_none(self, monkeypatch):
        monkeypatch.setattr("app.core.database.DATABASE_URL", None)
        assert is_postgres_enabled() is False


class TestGetPool:
    @pytest.mark.asyncio
    async def test_creates_pool_when_none(self, monkeypatch):
        fake_pool = AsyncMock()
        monkeypatch.setattr("app.core.database._pool", None)
        with patch(
            "asyncpg.create_pool", AsyncMock(return_value=fake_pool)
        ) as mock_create:
            monkeypatch.setattr(
                "app.core.database.DATABASE_URL", "postgresql://localhost/db"
            )
            pool = await get_pool()
            assert pool is fake_pool
            mock_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_existing_pool(self, monkeypatch):
        fake_pool = AsyncMock()
        monkeypatch.setattr("app.core.database._pool", fake_pool)
        with patch("asyncpg.create_pool") as mock_create:
            pool = await get_pool()
            assert pool is fake_pool
            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_retries_on_failure(self, monkeypatch):
        monkeypatch.setattr("app.core.database._pool", None)
        monkeypatch.setattr(
            "app.core.database.DATABASE_URL", "postgresql://localhost/db"
        )
        import asyncpg

        call_count = 0

        async def create_pool_side(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncpg.PostgresError("fail")
            return AsyncMock()

        with patch("asyncpg.create_pool", side_effect=create_pool_side):
            pool = await get_pool()
            assert pool is not None
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, monkeypatch):
        monkeypatch.setattr("app.core.database._pool", None)
        monkeypatch.setattr(
            "app.core.database.DATABASE_URL", "postgresql://localhost/db"
        )
        import asyncpg

        call_count = 0

        async def always_fail(*a, **kw):
            nonlocal call_count
            call_count += 1
            raise asyncpg.PostgresError("persistent fail")

        with patch("asyncpg.create_pool", side_effect=always_fail):
            with pytest.raises(asyncpg.PostgresError, match="persistent fail"):
                await get_pool()
            assert call_count == 5


class TestClosePool:
    @pytest.mark.asyncio
    async def test_closes_pool_and_resets(self, monkeypatch):
        fake_pool = AsyncMock()
        monkeypatch.setattr("app.core.database._pool", fake_pool)
        await close_pool()
        fake_pool.close.assert_awaited_once()
        assert monkeypatch

    @pytest.mark.asyncio
    async def test_noop_when_pool_none(self):
        _pool = None
        with patch("app.core.database._pool", None):
            await close_pool()

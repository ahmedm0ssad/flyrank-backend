"""Tests for app.core.supabase.

Lines 13-14 (sys.exit(1) when SUPABASE_URL/KEY missing) cannot be tested
without killing the test runner — that path only fires at module import
time when env vars are absent, and conftest.py always sets them.
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestGetClientCredentials:
    def test_returns_url_and_key(self):
        from app.core.supabase import get_client_credentials

        url, key = get_client_credentials()
        assert url == "https://test.supabase.co"
        assert key == "test-anon-key"


class TestGetSupabase:
    @pytest.mark.asyncio
    async def test_creates_client_when_none(self, monkeypatch):
        monkeypatch.setattr("app.core.supabase._supabase_client", None)
        fake_client = AsyncMock()
        with patch(
            "app.core.supabase.create_async_client",
            AsyncMock(return_value=fake_client),
        ) as mock_create:
            from app.core.supabase import get_supabase

            client = await get_supabase()
            assert client is fake_client
            mock_create.assert_awaited_once_with(
                "https://test.supabase.co", "test-anon-key"
            )

    @pytest.mark.asyncio
    async def test_returns_existing_client(self, monkeypatch):
        fake_client = AsyncMock()
        monkeypatch.setattr("app.core.supabase._supabase_client", fake_client)
        with patch("app.core.supabase.create_async_client") as mock_create:
            from app.core.supabase import get_supabase

            client = await get_supabase()
            assert client is fake_client
            mock_create.assert_not_called()

from unittest.mock import AsyncMock, patch

import pytest

from app.core.supabase import get_client_credentials, get_supabase


class TestGetClientCredentials:
    def test_returns_credentials_when_set(self, monkeypatch):
        monkeypatch.setattr("app.core.supabase._url", "https://test.supabase.co")
        monkeypatch.setattr("app.core.supabase._key", "test-key")
        url, key = get_client_credentials()
        assert url == "https://test.supabase.co"
        assert key == "test-key"

    def test_returns_none_when_not_set(self, monkeypatch):
        monkeypatch.setattr("app.core.supabase._url", None)
        monkeypatch.setattr("app.core.supabase._key", None)
        url, key = get_client_credentials()
        assert url is None
        assert key is None


class TestGetSupabase:
    @pytest.mark.asyncio
    async def test_creates_client_on_first_call(self, monkeypatch):
        monkeypatch.setattr("app.core.supabase._supabase_client", None)
        monkeypatch.setattr("app.core.supabase._url", "https://test.supabase.co")
        monkeypatch.setattr("app.core.supabase._key", "test-key")

        mock_client = AsyncMock()
        with patch(
            "app.core.supabase.create_async_client", return_value=mock_client
        ) as mock_create:
            client = await get_supabase()
            assert client is mock_client
            mock_create.assert_awaited_once_with("https://test.supabase.co", "test-key")

    @pytest.mark.asyncio
    async def test_returns_existing_client(self, monkeypatch):
        mock_client = AsyncMock()
        monkeypatch.setattr("app.core.supabase._supabase_client", mock_client)

        with patch("app.core.supabase.create_async_client") as mock_create:
            client = await get_supabase()
            assert client is mock_client
            mock_create.assert_not_called()

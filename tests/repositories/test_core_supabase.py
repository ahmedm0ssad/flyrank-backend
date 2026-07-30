"""Tests for app.core.supabase."""

from unittest.mock import AsyncMock, patch

import pytest


class TestGetClientCredentials:
    def test_returns_url_and_key(self):
        from app.core.supabase import get_client_credentials

        url, key = get_client_credentials()
        assert url == "https://test.supabase.co"
        assert key == "test-anon-key"


class TestModuleInit:
    def test_sys_exit_when_url_missing(self, tmp_path, monkeypatch):
        import os
        import subprocess
        import sys

        project_root = os.getcwd()
        monkeypatch.chdir(tmp_path)
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("SUPABASE_URL", "SUPABASE_KEY")
        }
        env["PYTHONPATH"] = project_root
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import app.core.supabase",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "FATAL" in result.stdout


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

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from supabase import AuthApiError

from app.dependencies.auth import get_current_user


class FakeUser:
    def __init__(
        self, id="u1", email="test@example.com", created_at="2024-01-01T00:00:00Z"
    ):
        self.id = id
        self.email = email
        self.created_at = created_at


class FakeAuthResponse:
    def __init__(self, user=None):
        self.user = user


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_returns_user_dict_when_token_valid(self):
        fake_user = FakeUser()
        fake_supabase = AsyncMock()
        fake_supabase.auth.get_user.return_value = FakeAuthResponse(user=fake_user)

        with patch(
            "app.dependencies.auth.get_supabase", AsyncMock(return_value=fake_supabase)
        ):
            creds = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="valid-token"
            )
            result = await get_current_user(credentials=creds)
            assert result["id"] == "u1"
            assert result["email"] == "test@example.com"
            assert result["access_token"] == "valid-token"
            fake_supabase.auth.get_user.assert_awaited_once_with("valid-token")

    @pytest.mark.asyncio
    async def test_raises_401_when_credentials_none(self):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials=None)
        assert exc.value.status_code == 401
        assert exc.value.detail == "Access token required"

    @pytest.mark.asyncio
    async def test_raises_401_when_token_empty(self):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials=creds)
        assert exc.value.status_code == 401
        assert exc.value.detail == "Access token required"

    @pytest.mark.asyncio
    async def test_raises_401_when_token_whitespace(self):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="   ")
        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials=creds)
        assert exc.value.status_code == 401
        assert exc.value.detail == "Access token required"

    @pytest.mark.asyncio
    async def test_raises_401_on_auth_error(self):
        fake_supabase = AsyncMock()
        fake_supabase.auth.get_user.side_effect = AuthApiError("bad token", 401, None)

        with patch(
            "app.dependencies.auth.get_supabase", AsyncMock(return_value=fake_supabase)
        ):
            creds = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials="invalid-token"
            )
            with pytest.raises(HTTPException) as exc:
                await get_current_user(credentials=creds)
            assert exc.value.status_code == 401
            assert exc.value.detail == "Invalid or expired token"

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient


def _make_user():
    return SimpleNamespace(
        id="test-user-id",
        email="test@example.com",
        created_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture(autouse=True)
def mock_supabase(monkeypatch):
    mock_auth = MagicMock()
    mock_user = _make_user()

    signup_res = MagicMock()
    signup_res.user = mock_user
    mock_auth.sign_up = AsyncMock(return_value=signup_res)

    mock_session = MagicMock()
    mock_session.access_token = "test-access-token"
    mock_session.refresh_token = "test-refresh-token"
    login_res = MagicMock()
    login_res.session = mock_session
    mock_auth.sign_in_with_password = AsyncMock(return_value=login_res)

    get_user_res = MagicMock()
    get_user_res.user = mock_user
    mock_auth.get_user = AsyncMock(return_value=get_user_res)

    mock_auth.set_session = AsyncMock()
    mock_auth.sign_out = AsyncMock()

    mock_client = MagicMock()
    mock_client.auth = mock_auth

    for module in ("app.routers.auth", "app.dependencies.auth"):
        monkeypatch.setattr(
            f"{module}.get_supabase", AsyncMock(return_value=mock_client)
        )
    monkeypatch.setattr(
        "app.routers.auth.create_async_client", AsyncMock(return_value=mock_client)
    )

    return mock_auth


class TestSignup:
    def test_signup_success(self, client: TestClient, mock_supabase):
        response = client.post(
            "/auth/signup", json={"email": "test@example.com", "password": "password123"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["id"] == "test-user-id"
        mock_supabase.sign_up.assert_awaited_once_with(
            {"email": "test@example.com", "password": "password123"}
        )

    def test_signup_missing_fields(self, client: TestClient):
        response = client.post("/auth/signup", json={})
        assert response.status_code == 400

    def test_signup_supabase_error(self, client: TestClient, mock_supabase):
        mock_supabase.sign_up.side_effect = Exception("User already registered")
        response = client.post(
            "/auth/signup", json={"email": "existing@example.com", "password": "password123"}
        )

        assert response.status_code == 400
        assert response.json()["error"] == "User already registered"


class TestLogin:
    def test_login_success(self, client: TestClient, mock_supabase):
        response = client.post(
            "/auth/login", json={"email": "test@example.com", "password": "password123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "test-access-token"
        assert data["refresh_token"] == "test-refresh-token"
        mock_supabase.sign_in_with_password.assert_awaited_once_with(
            {"email": "test@example.com", "password": "password123"}
        )

    def test_login_invalid_credentials(self, client: TestClient, mock_supabase):
        mock_supabase.sign_in_with_password.side_effect = Exception(
            "Invalid login credentials"
        )
        response = client.post(
            "/auth/login", json={"email": "wrong@example.com", "password": "wrong"}
        )

        assert response.status_code == 401
        assert "Invalid login credentials" in response.json()["error"]

    def test_login_other_error(self, client: TestClient, mock_supabase):
        mock_supabase.sign_in_with_password.side_effect = Exception("Some other error")
        response = client.post(
            "/auth/login", json={"email": "test@example.com", "password": "password123"}
        )

        assert response.status_code == 400
        assert response.json()["error"] == "Some other error"

    def test_login_missing_fields(self, client: TestClient):
        response = client.post("/auth/login", json={})
        assert response.status_code == 400


class TestProtected:
    def test_profile_success(self, client: TestClient, mock_supabase):
        response = client.get(
            "/protected/profile", headers={"Authorization": "Bearer valid-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["id"] == "test-user-id"
        mock_supabase.get_user.assert_awaited_once_with("valid-token")

    def test_profile_no_token(self, client: TestClient):
        response = client.get("/protected/profile")

        assert response.status_code == 401
        assert "Access token required" in response.json()["error"]

    def test_profile_invalid_token(self, client: TestClient, mock_supabase):
        mock_supabase.get_user.side_effect = Exception("Invalid token")
        response = client.get(
            "/protected/profile", headers={"Authorization": "Bearer invalid-token"}
        )

        assert response.status_code == 401
        assert "Invalid or expired token" in response.json()["error"]

    def test_dashboard_success(self, client: TestClient, mock_supabase):
        response = client.get(
            "/protected/dashboard", headers={"Authorization": "Bearer valid-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "test@example.com" in data["message"]
        assert data["user_id"] == "test-user-id"

    def test_dashboard_no_token(self, client: TestClient):
        response = client.get("/protected/dashboard")
        assert response.status_code == 401


class TestLogout:
    def test_logout_success(self, client: TestClient, mock_supabase):
        response = client.post(
            "/auth/logout", headers={"Authorization": "Bearer valid-token"}
        )

        assert response.status_code == 204
        assert response.content == b""
        mock_supabase.set_session.assert_awaited_once_with("valid-token", "")
        mock_supabase.sign_out.assert_awaited_once()

    def test_logout_no_token(self, client: TestClient):
        response = client.post("/auth/logout")
        assert response.status_code == 401

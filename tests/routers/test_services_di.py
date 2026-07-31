import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.dependencies.services import get_lead_repo, get_widget_repo
from app.main import app
from app.models.widget import WidgetResponse

LEAD_USER = {
    "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
    "email": "test@example.com",
    "access_token": "fake-token",
}


@pytest.fixture
def client():
    return TestClient(app)


class TestLeadRepoDependencyOverride:
    def test_get_lead_repo_override_replaces_provider(self, client):
        mock_repo = MagicMock()
        mock_repo.get_tenant_stats = AsyncMock(return_value={"total_leads": 42})

        app.dependency_overrides[get_current_user] = lambda: LEAD_USER
        app.dependency_overrides[get_lead_repo] = lambda: mock_repo
        try:
            resp = client.get("/leads/stats")
            assert resp.status_code == 200
            assert resp.json() == {"total_leads": 42}
            mock_repo.get_tenant_stats.assert_awaited_once_with(str(LEAD_USER["id"]))
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_lead_repo, None)


class TestWidgetRepoDependencyOverride:
    def test_get_widget_repo_override_replaces_provider(self, client):
        user_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
        mock_user = {
            "id": user_id,
            "email": "test@example.com",
            "access_token": "fake-token",
        }
        widget_id = uuid.UUID("33333333-3333-3333-3333-333333333333")

        mock_repo = MagicMock()
        mock_repo.check_domain_exists = AsyncMock(return_value=False)
        widget = WidgetResponse(
            id=widget_id,
            tenant_id=user_id,
            name="DI Widget",
            domain="https://di.example.com",
            config={
                "brand_color": "#2563eb",
                "button_text": "Get a Quote",
                "fields": ["name", "email"],
                "success_message": "Thanks!",
                "honeypot_field": "_hp_di",
            },
            js_version=1,
            active=True,
            created_at=datetime.now(timezone.utc),
        )
        mock_repo.create = AsyncMock(return_value=widget)

        app.dependency_overrides[get_current_user] = lambda: mock_user
        app.dependency_overrides[get_widget_repo] = lambda: mock_repo
        try:
            resp = client.post(
                "/widgets/",
                json={
                    "name": "DI Widget",
                    "domain": "https://di.example.com",
                    "config": {
                        "brand_color": "#2563eb",
                        "button_text": "Get a Quote",
                        "fields": ["name", "email"],
                        "success_message": "Thanks!",
                    },
                },
            )
            assert resp.status_code == 201
            assert resp.json()["name"] == "DI Widget"
            mock_repo.check_domain_exists.assert_awaited_once()
            mock_repo.create.assert_awaited_once()
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(get_widget_repo, None)

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.widgets import service as widget_service
from app.widgets.models import WidgetCreate, WidgetResponse, WidgetUpdate
from app.widgets.repository import WidgetRepository


@pytest.fixture(autouse=True)
def mock_repo():
    repo = WidgetRepository()
    widget_service._repo = repo
    return repo


@pytest.fixture
def tenant_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_data():
    return {
        "name": "My Contact Form",
        "domain": "https://myshop.com",
        "config": {
            "brand_color": "#2563eb",
            "button_text": "Get a Quote",
            "fields": ["name", "email", "phone"],
            "success_message": "Thanks!",
        },
    }


@pytest.mark.asyncio
class TestWidgetService:
    async def test_create_widget_generates_honeypot_field(
        self, mock_repo, tenant_id, sample_data
    ):
        data = WidgetCreate(**sample_data)
        result = await widget_service.create_widget(data, tenant_id)
        hp = result.config.get("honeypot_field", "")
        assert hp.startswith("_hp_")
        assert len(hp) > 4

    async def test_create_widget_validates_domain(
        self, mock_repo, tenant_id, sample_data
    ):
        data = WidgetCreate(**sample_data)
        result = await widget_service.create_widget(data, tenant_id)
        assert result.name == sample_data["name"]
        assert result.domain == sample_data["domain"]

    async def test_create_widget_duplicate_domain(
        self, mock_repo, tenant_id, sample_data
    ):
        data = WidgetCreate(**sample_data)
        await widget_service.create_widget(data, tenant_id)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            await widget_service.create_widget(data, tenant_id)
        assert exc.value.status_code == 409

    async def test_update_widget_bumps_js_version(
        self, mock_repo, tenant_id, sample_data
    ):
        data = WidgetCreate(**sample_data)
        created = await widget_service.create_widget(data, tenant_id)
        assert created.js_version == 1

        update_data = WidgetUpdate(name="Updated Name")
        updated = await widget_service.update_widget(
            str(created.id), tenant_id, update_data
        )
        assert updated is not None
        assert updated.js_version == 2
        assert updated.name == "Updated Name"

    async def test_update_widget_invalidates_cache(
        self, mock_repo, tenant_id, sample_data
    ):
        _redis_delete = AsyncMock()
        widget_service._redis_client = AsyncMock()
        widget_service._redis_client.delete = _redis_delete

        data = WidgetCreate(**sample_data)
        created = await widget_service.create_widget(data, tenant_id)

        update_data = WidgetUpdate(name="After Update")
        await widget_service.update_widget(str(created.id), tenant_id, update_data)

        _redis_delete.assert_awaited_once_with(
            f"widget:config:{created.id}"
        )

        widget_service._redis_client = None

    async def test_delete_widget_soft_delete(
        self, mock_repo, tenant_id, sample_data
    ):
        data = WidgetCreate(**sample_data)
        created = await widget_service.create_widget(data, tenant_id)

        deleted = await widget_service.delete_widget(str(created.id), tenant_id)
        assert deleted is True

        result = await widget_service.get_widget(str(created.id), tenant_id)
        assert result is not None
        assert result.active is False

    async def test_delete_widget_not_found(self, mock_repo, tenant_id):
        deleted = await widget_service.delete_widget(str(uuid.uuid4()), tenant_id)
        assert deleted is False

    async def test_get_widget_not_found(self, mock_repo, tenant_id):
        result = await widget_service.get_widget(str(uuid.uuid4()), tenant_id)
        assert result is None

    async def test_duplicate_domain_on_update(
        self, mock_repo, tenant_id, sample_data
    ):
        data1 = WidgetCreate(**sample_data)
        await widget_service.create_widget(data1, tenant_id)

        data2 = WidgetCreate(
            name="Second Widget",
            domain="https://other.com",
            config=sample_data["config"],
        )
        created2 = await widget_service.create_widget(data2, tenant_id)

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            update_data = WidgetUpdate(domain="https://myshop.com")
            await widget_service.update_widget(
                str(created2.id), tenant_id, update_data
            )
        assert exc.value.status_code == 409

    async def test_inactive_widget_still_visible_via_service(
        self, mock_repo, tenant_id, sample_data
    ):
        data = WidgetCreate(**sample_data)
        created = await widget_service.create_widget(data, tenant_id)
        await widget_service.delete_widget(str(created.id), tenant_id)

        result = await widget_service.get_widget(str(created.id), tenant_id)
        assert result is not None
        assert result.active is False

    async def test_list_widgets_pagination(
        self, mock_repo, tenant_id, sample_data
    ):
        for i in range(3):
            d = WidgetCreate(
                name=f"Widget {i}",
                domain=f"https://ex{i}.com",
                config=sample_data["config"],
            )
            await widget_service.create_widget(d, tenant_id)

        items, total = await widget_service.get_widgets(
            tenant_id=tenant_id, page=1, page_size=2
        )
        assert total == 3
        assert len(items) == 2

    async def test_search_widgets_by_name(
        self, mock_repo, tenant_id, sample_data
    ):
        d1 = WidgetCreate(name="Alpha Team", domain="https://alpha.com", config=sample_data["config"])
        d2 = WidgetCreate(name="Beta Team", domain="https://beta.com", config=sample_data["config"])
        await widget_service.create_widget(d1, tenant_id)
        await widget_service.create_widget(d2, tenant_id)

        items, total = await widget_service.get_widgets(
            tenant_id=tenant_id, search="alpha"
        )
        assert total == 1
        assert items[0].name == "Alpha Team"

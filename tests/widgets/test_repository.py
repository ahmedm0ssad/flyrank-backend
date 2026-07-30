import uuid

import pytest

from app.repositories.widget_repo import WidgetRepository


@pytest.fixture
def repo():
    return WidgetRepository()


@pytest.fixture
def tenant_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_widget(tenant_id):
    return {
        "name": "My Contact Form",
        "domain": "https://myshop.com",
        "config": {
            "brand_color": "#2563eb",
            "button_text": "Get a Quote",
            "fields": ["name", "email", "phone"],
            "success_message": "Thanks!",
            "honeypot_field": "_hp_a3f9",
        },
    }


@pytest.mark.asyncio
class TestWidgetRepository:
    async def test_create_returns_widget(self, repo, tenant_id, sample_widget):
        result = await repo.create(
            name=sample_widget["name"],
            domain=sample_widget["domain"],
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        assert result.name == sample_widget["name"]
        assert result.domain == sample_widget["domain"]
        assert str(result.tenant_id) == tenant_id
        assert result.js_version == 1
        assert result.active is True

    async def test_get_by_id_returns_widget(self, repo, tenant_id, sample_widget):
        created = await repo.create(
            name=sample_widget["name"],
            domain=sample_widget["domain"],
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        result = await repo.get_by_id(str(created.id), tenant_id)
        assert result is not None
        assert result.id == created.id
        assert result.name == sample_widget["name"]

    async def test_get_by_id_wrong_tenant(self, repo, tenant_id, sample_widget):
        created = await repo.create(
            name=sample_widget["name"],
            domain=sample_widget["domain"],
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        other_tenant = str(uuid.uuid4())
        result = await repo.get_by_id(str(created.id), other_tenant)
        assert result is None

    async def test_get_by_id_not_found(self, repo, tenant_id):
        result = await repo.get_by_id(str(uuid.uuid4()), tenant_id)
        assert result is None

    async def test_update_increments_js_version(self, repo, tenant_id, sample_widget):
        created = await repo.create(
            name=sample_widget["name"],
            domain=sample_widget["domain"],
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        assert created.js_version == 1

        updated = await repo.update(
            widget_id=str(created.id),
            tenant_id=tenant_id,
        )
        assert updated is not None
        assert updated.js_version == 2

    async def test_update_updates_fields(self, repo, tenant_id, sample_widget):
        created = await repo.create(
            name=sample_widget["name"],
            domain=sample_widget["domain"],
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        updated = await repo.update(
            widget_id=str(created.id),
            tenant_id=tenant_id,
            name="New Name",
        )
        assert updated.name == "New Name"
        assert updated.domain == sample_widget["domain"]

    async def test_update_wrong_tenant(self, repo, tenant_id, sample_widget):
        created = await repo.create(
            name=sample_widget["name"],
            domain=sample_widget["domain"],
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        other_tenant = str(uuid.uuid4())
        result = await repo.update(
            widget_id=str(created.id),
            tenant_id=other_tenant,
            name="Hijacked",
        )
        assert result is None

    async def test_soft_delete_sets_inactive(self, repo, tenant_id, sample_widget):
        created = await repo.create(
            name=sample_widget["name"],
            domain=sample_widget["domain"],
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        deleted = await repo.soft_delete(str(created.id), tenant_id)
        assert deleted is True

        record = await repo.get_by_id(str(created.id), tenant_id)
        assert record is not None
        assert record.active is False

    async def test_soft_delete_wrong_tenant(self, repo, tenant_id, sample_widget):
        created = await repo.create(
            name=sample_widget["name"],
            domain=sample_widget["domain"],
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        other_tenant = str(uuid.uuid4())
        result = await repo.soft_delete(str(created.id), other_tenant)
        assert result is False

    async def test_soft_delete_not_found(self, repo, tenant_id):
        result = await repo.soft_delete(str(uuid.uuid4()), tenant_id)
        assert result is False

    async def test_list_by_tenant_paginated(self, repo, tenant_id, sample_widget):
        for i in range(5):
            await repo.create(
                name=f"Widget {i}",
                domain=f"https://example{i}.com",
                config=sample_widget["config"],
                tenant_id=tenant_id,
            )
        items, total = await repo.list_by_tenant(
            tenant_id=tenant_id, page=1, page_size=2
        )
        assert total == 5
        assert len(items) == 2

    async def test_list_by_tenant_second_page(self, repo, tenant_id, sample_widget):
        for i in range(3):
            await repo.create(
                name=f"Widget {i}",
                domain=f"https://example{i}.com",
                config=sample_widget["config"],
                tenant_id=tenant_id,
            )
        items, total = await repo.list_by_tenant(
            tenant_id=tenant_id, page=2, page_size=2
        )
        assert total == 3
        assert len(items) == 1

    async def test_list_by_tenant_search(self, repo, tenant_id, sample_widget):
        await repo.create(
            name="Alpha Widget",
            domain="https://alpha.com",
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        await repo.create(
            name="Beta Widget",
            domain="https://beta.com",
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        items, total = await repo.list_by_tenant(tenant_id=tenant_id, search="alpha")
        assert total == 1
        assert items[0].name == "Alpha Widget"

    async def test_list_by_tenant_active_filter(self, repo, tenant_id, sample_widget):
        created = await repo.create(
            name="Active Widget",
            domain="https://active.com",
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        await repo.create(
            name="Inactive Widget",
            domain="https://inactive.com",
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        await repo.soft_delete(str(created.id), tenant_id)

        items, total = await repo.list_by_tenant(tenant_id=tenant_id, active=True)
        assert total == 1
        assert items[0].name == "Inactive Widget"

    async def test_domain_uniqueness(self, repo, tenant_id, sample_widget):
        await repo.create(
            name="First",
            domain="https://same.com",
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        exists = await repo.check_domain_exists("https://same.com", tenant_id)
        assert exists is True

    async def test_domain_uniqueness_exclude_self(self, repo, tenant_id, sample_widget):
        created = await repo.create(
            name="First",
            domain="https://same.com",
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        exists = await repo.check_domain_exists(
            "https://same.com", tenant_id, exclude_id=str(created.id)
        )
        assert exists is False

    async def test_domain_uniqueness_different_tenant(
        self, repo, tenant_id, sample_widget
    ):
        await repo.create(
            name="First",
            domain="https://same.com",
            config=sample_widget["config"],
            tenant_id=tenant_id,
        )
        other_tenant = str(uuid.uuid4())
        exists = await repo.check_domain_exists("https://same.com", other_tenant)
        assert exists is False

    async def test_tenant_isolation_in_list(self, repo, sample_widget):
        t1 = str(uuid.uuid4())
        t2 = str(uuid.uuid4())
        await repo.create(
            name="T1 Widget",
            domain="https://t1.com",
            config=sample_widget["config"],
            tenant_id=t1,
        )
        await repo.create(
            name="T2 Widget",
            domain="https://t2.com",
            config=sample_widget["config"],
            tenant_id=t2,
        )
        _items_t1, total_t1 = await repo.list_by_tenant(tenant_id=t1)
        assert total_t1 == 1
        _items_t2, total_t2 = await repo.list_by_tenant(tenant_id=t2)
        assert total_t2 == 1

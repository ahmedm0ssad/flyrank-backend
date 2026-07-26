import uuid

import pytest

from app.repositories.lead_repo import LeadRepository


@pytest.fixture
def repo():
    return LeadRepository()


@pytest.fixture
def tenant_id():
    return str(uuid.uuid4())


@pytest.fixture
def widget_id():
    return str(uuid.uuid4())


@pytest.fixture
def sample_lead(tenant_id, widget_id):
    return {
        "widget_id": widget_id,
        "tenant_id": tenant_id,
        "form_data": {"name": "John", "email": "john@test.com"},
        "ip_address": "192.168.1.1",
        "fingerprint": "abc123",
    }


@pytest.mark.asyncio
class TestLeadRepository:
    async def test_create_returns_lead(self, repo, sample_lead):
        result = await repo.create(**sample_lead)
        assert result.form_data == sample_lead["form_data"]
        assert result.ip_address == sample_lead["ip_address"]
        assert result.fingerprint == sample_lead["fingerprint"]
        assert result.status == "pending"
        assert result.honeypot_triggered is False
        assert result.spam_score == 0.0

    async def test_get_by_id_returns_lead(self, repo, sample_lead):
        created = await repo.create(**sample_lead)
        result = await repo.get_by_id(str(created.id))
        assert result is not None
        assert result.id == created.id

    async def test_get_by_id_not_found(self, repo):
        result = await repo.get_by_id(str(uuid.uuid4()))
        assert result is None

    async def test_list_by_widget(self, repo, sample_lead, widget_id):
        await repo.create(**sample_lead)
        other = dict(sample_lead)
        other["widget_id"] = str(uuid.uuid4())
        await repo.create(**other)

        items, total = await repo.list_by_widget(
            widget_id=widget_id,
            tenant_id=sample_lead["tenant_id"],
        )
        assert total == 1
        assert len(items) == 1

    async def test_list_by_widget_excludes_honeypot(self, repo, sample_lead, widget_id):
        await repo.create(**sample_lead)
        hp = dict(sample_lead)
        hp["honeypot_triggered"] = True
        hp["fingerprint"] = "hp-fp"
        await repo.create(**hp)

        items, total = await repo.list_by_widget(
            widget_id=widget_id,
            tenant_id=sample_lead["tenant_id"],
        )
        assert total == 1

        items2, total2 = await repo.list_by_widget(
            widget_id=widget_id,
            tenant_id=sample_lead["tenant_id"],
            include_honeypot=True,
        )
        assert total2 == 2

    async def test_list_by_widget_paginated(self, repo, sample_lead, widget_id, tenant_id):
        for i in range(5):
            ld = dict(sample_lead)
            ld["fingerprint"] = f"fp-{i}"
            await repo.create(**ld)

        items, total = await repo.list_by_widget(
            widget_id=widget_id, tenant_id=tenant_id, page=1, page_size=2
        )
        assert total == 5
        assert len(items) == 2

    async def test_list_by_tenant(self, repo, sample_lead, tenant_id):
        await repo.create(**sample_lead)
        other = dict(sample_lead)
        other["tenant_id"] = str(uuid.uuid4())
        await repo.create(**other)

        items, total = await repo.list_by_tenant(tenant_id=tenant_id)
        assert total == 1

    async def test_update_status(self, repo, sample_lead):
        created = await repo.create(**sample_lead)
        updated = await repo.update_status(
            str(created.id), "enriched", geo_country="US"
        )
        assert updated is not None
        assert updated.status == "enriched"
        assert updated.geo_country == "US"

    async def test_delete(self, repo, sample_lead, widget_id, tenant_id):
        created = await repo.create(**sample_lead)
        deleted = await repo.delete(str(created.id), widget_id, tenant_id)
        assert deleted is True
        result = await repo.get_by_id(str(created.id))
        assert result is None

    async def test_delete_wrong_tenant(self, repo, sample_lead, widget_id):
        created = await repo.create(**sample_lead)
        deleted = await repo.delete(
            str(created.id), widget_id, str(uuid.uuid4())
        )
        assert deleted is False

    async def test_batch_delete(self, repo, sample_lead, widget_id, tenant_id):
        ids = []
        for i in range(3):
            ld = dict(sample_lead)
            ld["fingerprint"] = f"fp-{i}"
            created = await repo.create(**ld)
            ids.append(str(created.id))

        count = await repo.batch_delete(ids, widget_id, tenant_id)
        assert count == 3

    async def test_tenant_isolation(self, repo, sample_lead, widget_id):
        t1 = str(uuid.uuid4())
        t2 = str(uuid.uuid4())
        ld1 = dict(sample_lead, widget_id=widget_id, tenant_id=t1, fingerprint="fp1")
        ld2 = dict(sample_lead, widget_id=widget_id, tenant_id=t2, fingerprint="fp2")
        await repo.create(**ld1)
        await repo.create(**ld2)

        items1, total1 = await repo.list_by_widget(widget_id=widget_id, tenant_id=t1)
        assert total1 == 1

        items2, total2 = await repo.list_by_widget(widget_id=widget_id, tenant_id=t2)
        assert total2 == 1

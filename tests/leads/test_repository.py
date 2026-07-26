import uuid
from datetime import date, datetime, timedelta, timezone

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

    async def test_list_by_widget_search(self, repo, sample_lead, widget_id, tenant_id):
        await repo.create(**sample_lead)
        other = dict(sample_lead)
        other["fingerprint"] = "fp-other"
        other["form_data"] = {"name": "Alice", "email": "alice@test.com"}
        await repo.create(**other)

        items, total = await repo.list_by_widget(
            widget_id=widget_id,
            tenant_id=tenant_id,
            search="Alice",
        )
        assert total == 1
        assert items[0].form_data["name"] == "Alice"

    async def test_list_by_widget_filter_status(self, repo, sample_lead, widget_id, tenant_id):
        await repo.create(**sample_lead)
        enriched = dict(sample_lead)
        enriched["fingerprint"] = "fp-enriched"
        enriched["status"] = "enriched"
        await repo.create(**enriched)

        items, total = await repo.list_by_widget(
            widget_id=widget_id,
            tenant_id=tenant_id,
            status="enriched",
        )
        assert total == 1
        assert items[0].status == "enriched"

    async def test_list_by_widget_filter_spam_range(self, repo, sample_lead, widget_id, tenant_id):
        clean = dict(sample_lead, fingerprint="fp-clean", spam_score=0.0)
        await repo.create(**clean)
        spammy = dict(sample_lead, fingerprint="fp-spam", spam_score=0.8)
        await repo.create(**spammy)

        items, total = await repo.list_by_widget(
            widget_id=widget_id,
            tenant_id=tenant_id,
            spam_min=0.5,
        )
        assert total == 1
        assert items[0].spam_score == 0.8

        items2, total2 = await repo.list_by_widget(
            widget_id=widget_id,
            tenant_id=tenant_id,
            spam_max=0.5,
        )
        assert total2 == 1
        assert items2[0].spam_score == 0.0

    async def test_list_by_widget_filter_date_range(self, repo, sample_lead, widget_id, tenant_id):
        old = dict(sample_lead, fingerprint="fp-old")
        old_lead = await repo.create(**old)
        old_lead_id = str(old_lead.id)
        repo._leads[old_lead_id]["created_at"] = datetime(2024, 1, 1, tzinfo=timezone.utc)

        new = dict(sample_lead, fingerprint="fp-new")
        await repo.create(**new)

        items, total = await repo.list_by_widget(
            widget_id=widget_id,
            tenant_id=tenant_id,
            date_from=date(2025, 1, 1),
        )
        assert total == 1

    async def test_list_by_widget_sort_order(self, repo, sample_lead, widget_id, tenant_id):
        for i in range(3):
            ld = dict(sample_lead, fingerprint=f"fp-{i}")
            await repo.create(**ld)

        items_desc, _ = await repo.list_by_widget(
            widget_id=widget_id, tenant_id=tenant_id, sort_order="desc"
        )
        items_asc, _ = await repo.list_by_widget(
            widget_id=widget_id, tenant_id=tenant_id, sort_order="asc"
        )
        assert items_desc[0].created_at >= items_desc[-1].created_at
        assert items_asc[0].created_at <= items_asc[-1].created_at

    async def test_list_by_tenant(self, repo, sample_lead, tenant_id):
        await repo.create(**sample_lead)
        other = dict(sample_lead)
        other["tenant_id"] = str(uuid.uuid4())
        await repo.create(**other)

        items, total = await repo.list_by_tenant(tenant_id=tenant_id)
        assert total == 1

    async def test_list_by_tenant_excludes_honeypot(self, repo, sample_lead, tenant_id):
        await repo.create(**sample_lead)
        hp = dict(sample_lead, fingerprint="hp-fp", honeypot_triggered=True)
        await repo.create(**hp)

        items, total = await repo.list_by_tenant(tenant_id=tenant_id)
        assert total == 1

        items2, total2 = await repo.list_by_tenant(tenant_id=tenant_id, include_honeypot=True)
        assert total2 == 2

    async def test_get_stats(self, repo, sample_lead, widget_id, tenant_id):
        for i in range(5):
            ld = dict(sample_lead, fingerprint=f"fp-{i}")
            await repo.create(**ld)

        stats = await repo.get_stats(widget_id, tenant_id)
        assert stats["total_leads"] == 5
        assert stats["honeypot_blocked"] == 0

    async def test_get_stats_honeypot_excluded_from_counts(self, repo, sample_lead, widget_id, tenant_id):
        for i in range(3):
            ld = dict(sample_lead, fingerprint=f"fp-{i}")
            await repo.create(**ld)
        hp = dict(sample_lead, fingerprint="hp-fp", honeypot_triggered=True)
        await repo.create(**hp)

        stats = await repo.get_stats(widget_id, tenant_id)
        assert stats["total_leads"] == 3
        assert stats["honeypot_blocked"] == 1

    async def test_get_stats_top_countries(self, repo, sample_lead, widget_id, tenant_id):
        for country in ["US", "US", "GB", "DE"]:
            ld = dict(sample_lead, fingerprint=f"fp-{country}")
            c = await repo.create(**ld)
            repo._leads[str(c.id)]["geo_country"] = country

        stats = await repo.get_stats(widget_id, tenant_id)
        assert len(stats["top_countries"]) == 3
        us_entry = [e for e in stats["top_countries"] if e["country"] == "US"]
        assert us_entry[0]["count"] == 2

    async def test_get_stats_leads_over_time(self, repo, sample_lead, widget_id, tenant_id):
        now = datetime.now(timezone.utc)
        for i in range(3):
            ld = dict(sample_lead, fingerprint=f"fp-{i}")
            c = await repo.create(**ld)
            repo._leads[str(c.id)]["created_at"] = now - timedelta(days=i)

        stats = await repo.get_stats(widget_id, tenant_id)
        assert len(stats["leads_over_time"]) == 3

    async def test_get_tenant_stats(self, repo, sample_lead, tenant_id):
        w1 = str(uuid.uuid4())
        w2 = str(uuid.uuid4())
        for i in range(3):
            ld = dict(sample_lead, widget_id=w1, fingerprint=f"fp-w1-{i}")
            await repo.create(**ld)
        for i in range(2):
            ld = dict(sample_lead, widget_id=w2, fingerprint=f"fp-w2-{i}")
            await repo.create(**ld)

        stats = await repo.get_tenant_stats(tenant_id)
        assert stats["total_leads"] == 5

    async def test_get_export_data(self, repo, sample_lead, widget_id, tenant_id):
        for i in range(3):
            ld = dict(sample_lead, fingerprint=f"fp-{i}")
            await repo.create(**ld)

        data = await repo.get_export_data(widget_id, tenant_id)
        assert len(data) == 3
        assert "form_data" in data[0]
        assert str(data[0]["widget_id"]) == widget_id

    async def test_get_export_data_with_date_filter(self, repo, sample_lead, widget_id, tenant_id):
        old = dict(sample_lead, fingerprint="fp-old")
        old_lead = await repo.create(**old)
        repo._leads[str(old_lead.id)]["created_at"] = datetime(2024, 6, 1, tzinfo=timezone.utc)

        new = dict(sample_lead, fingerprint="fp-new")
        await repo.create(**new)

        data = await repo.get_export_data(
            widget_id, tenant_id, date_from=date(2025, 1, 1)
        )
        assert len(data) == 1

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

    async def test_stats_avg_spam_score(self, repo, sample_lead, widget_id, tenant_id):
        ld1 = dict(sample_lead, fingerprint="fp-1", spam_score=0.0)
        ld2 = dict(sample_lead, fingerprint="fp-2", spam_score=0.5)
        await repo.create(**ld1)
        await repo.create(**ld2)

        stats = await repo.get_stats(widget_id, tenant_id)
        assert stats["avg_spam_score"] == 0.25

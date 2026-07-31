from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from app.repositories.postgres_lead_repo import (
    PostgresLeadRepository,
    _inet,
)


@pytest.fixture
def repo():
    return PostgresLeadRepository()


class FakeRow:
    def __init__(self, **kwargs):
        self._data = kwargs

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data.items())

    def get(self, key, default=None):
        return self._data.get(key, default)


def _make_row(**overrides):
    now = datetime.now(timezone.utc)
    data = {
        "id": "00000000-0000-0000-0000-000000000001",
        "widget_id": "00000000-0000-0000-0000-000000000010",
        "tenant_id": "00000000-0000-0000-0000-000000000002",
        "form_data": {"name": "Ada Lovelace", "email": "ada@example.com"},
        "ip_address": "203.0.113.5",
        "user_agent": "Mozilla/5.0",
        "referer": "https://myshop.com/",
        "fingerprint": "abc123",
        "geo_country": None,
        "geo_city": None,
        "geo_region": None,
        "geo_isp": None,
        "geo_provider": None,
        "spam_score": 0.0,
        "spam_reasons": None,
        "honeypot_triggered": False,
        "status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)
    return FakeRow(**data)


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool, conn


class TestInet:
    def test_valid_ip_passthrough(self):
        assert _inet("203.0.113.5") == "203.0.113.5"

    def test_non_ip_falls_back_to_sentinel(self):
        assert _inet("unknown") == "0.0.0.0"
        assert _inet("localhost") == "0.0.0.0"


class TestPostgresLeadRepository:
    @pytest.mark.asyncio
    async def test_create_returns_lead(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = _make_row()
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.create(
                widget_id="00000000-0000-0000-0000-000000000010",
                tenant_id="00000000-0000-0000-0000-000000000002",
                form_data={"name": "Ada Lovelace", "email": "ada@example.com"},
                ip_address="203.0.113.5",
                fingerprint="abc123",
            )
            assert result is not None
            assert result.id == UUID("00000000-0000-0000-0000-000000000001")
            assert result.form_data["name"] == "Ada Lovelace"
            conn.fetchrow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_returns_lead(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = _make_row()
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.get_by_id("00000000-0000-0000-0000-000000000001")
            assert result is not None
            assert result.ip_address == "203.0.113.5"

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = None
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.get_by_id("missing")
            assert result is None

    @pytest.mark.asyncio
    async def test_list_by_widget_returns_items_and_count(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [_make_row()]
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            items, total = await repo.list_by_widget(
                widget_id="00000000-0000-0000-0000-000000000010",
                tenant_id="00000000-0000-0000-0000-000000000002",
            )
            assert total == 1
            assert len(items) == 1
            conn.fetchval.assert_awaited_once()
            conn.fetch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_by_widget_uses_whitelisted_sort(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            await repo.list_by_widget(
                widget_id="00000000-0000-0000-0000-000000000010",
                tenant_id="00000000-0000-0000-0000-000000000002",
                sort_by="spam_score",
                sort_order="asc",
            )
            call_args = conn.fetch.await_args.args
            assert "ORDER BY spam_score ASC" in call_args[0]

    @pytest.mark.asyncio
    async def test_list_by_widget_falls_back_on_unknown_sort(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.return_value = 0
        conn.fetch.return_value = []
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            await repo.list_by_widget(
                widget_id="00000000-0000-0000-0000-000000000010",
                tenant_id="00000000-0000-0000-0000-000000000002",
                sort_by="form_data->>name",
                sort_order="desc",
            )
            call_args = conn.fetch.await_args.args
            assert "ORDER BY created_at DESC" in call_args[0]

    @pytest.mark.asyncio
    async def test_list_by_tenant_returns_items_and_count(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.return_value = 2
        conn.fetch.return_value = [_make_row(), _make_row()]
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            items, total = await repo.list_by_tenant(
                tenant_id="00000000-0000-0000-0000-000000000002"
            )
            assert total == 2
            assert len(items) == 2

    @pytest.mark.asyncio
    async def test_get_stats_returns_expected_shape(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.side_effect = [10, 2, 4, 6, 0.5, 1]
        conn.fetch.return_value = []
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            stats = await repo.get_stats(
                widget_id="00000000-0000-0000-0000-000000000010",
                tenant_id="00000000-0000-0000-0000-000000000002",
            )
            assert stats["total_leads"] == 10
            assert stats["today"] == 2
            assert stats["this_week"] == 4
            assert stats["this_month"] == 6
            assert stats["avg_spam_score"] == 0.5
            assert stats["honeypot_blocked"] == 1
            assert stats["top_countries"] == []
            assert stats["leads_over_time"] == []

    @pytest.mark.asyncio
    async def test_get_tenant_stats_returns_expected_shape(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.side_effect = [5, 1, 2, 3, 0.25, 0]
        conn.fetch.return_value = []
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            stats = await repo.get_tenant_stats(
                tenant_id="00000000-0000-0000-0000-000000000002"
            )
            assert stats["total_leads"] == 5
            assert stats["avg_spam_score"] == 0.25

    @pytest.mark.asyncio
    async def test_get_export_data_returns_model_dumps(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetch.return_value = [_make_row()]
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            rows = await repo.get_export_data(
                widget_id="00000000-0000-0000-0000-000000000010",
                tenant_id="00000000-0000-0000-0000-000000000002",
            )
            assert isinstance(rows, list)
            assert str(rows[0]["id"]) == "00000000-0000-0000-0000-000000000001"
            assert "form_data" in rows[0]

    @pytest.mark.asyncio
    async def test_update_status_with_geo_extras(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = _make_row(
            status="enriched",
            geo_country="Egypt",
            geo_provider="ipapi",
        )
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.update_status(
                "00000000-0000-0000-0000-000000000001",
                "enriched",
                geo_country="Egypt",
                geo_provider="ipapi",
            )
            assert result is not None
            assert result.status == "enriched"
            assert result.geo_country == "Egypt"
            conn.fetchrow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_status_returns_none_when_missing(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = None
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.update_status("missing", "failed")
            assert result is None

    @pytest.mark.asyncio
    async def test_delete_returns_true(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = _make_row()
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            deleted = await repo.delete(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000010",
                "00000000-0000-0000-0000-000000000002",
            )
            assert deleted is True

    @pytest.mark.asyncio
    async def test_delete_returns_false(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = None
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            deleted = await repo.delete("missing", "w", "t")
            assert deleted is False

    @pytest.mark.asyncio
    async def test_batch_delete_uses_single_any_query(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.return_value = 3
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            count = await repo.batch_delete(
                [
                    "00000000-0000-0000-0000-000000000001",
                    "00000000-0000-0000-0000-000000000002",
                    "00000000-0000-0000-0000-000000000003",
                ],
                "00000000-0000-0000-0000-000000000010",
                "00000000-0000-0000-0000-000000000002",
            )
            assert count == 3
            conn.fetchval.assert_awaited_once()
            query = conn.fetchval.await_args.args[0]
            assert "ANY($1::uuid[])" in query

    @pytest.mark.asyncio
    async def test_batch_delete_empty_returns_zero(self, repo, mock_pool):
        pool, conn = mock_pool
        with patch(
            "app.repositories.postgres_lead_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            count = await repo.batch_delete([], "w", "t")
            assert count == 0
            conn.fetchval.assert_not_awaited()

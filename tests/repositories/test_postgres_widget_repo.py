from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.repositories.postgres_widget_repo import PostgresWidgetRepository


@pytest.fixture
def repo():
    return PostgresWidgetRepository()


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
        "tenant_id": "00000000-0000-0000-0000-000000000002",
        "name": "Test Widget",
        "domain": "https://myshop.com",
        "config": {"brand_color": "#2563eb"},
        "js_version": 1,
        "active": True,
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


class TestPostgresWidgetRepository:
    @pytest.mark.asyncio
    async def test_create_returns_widget(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = _make_row()
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.create(
                name="New Widget",
                domain="https://example.com",
                config={"brand_color": "#ff0000"},
                tenant_id="00000000-0000-0000-0000-000000000002",
            )
            assert result is not None
            assert result.name == "Test Widget"
            conn.fetchrow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_by_id_returns_widget(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = _make_row()
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.get_by_id(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
            )
            assert result is not None
            assert str(result.id) == "00000000-0000-0000-0000-000000000001"

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = None
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.get_by_id(
                "00000000-0000-0000-0000-000000009999",
                "00000000-0000-0000-0000-000000000002",
            )
            assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_raw_returns_dict(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = _make_row()
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.get_by_id_raw("00000000-0000-0000-0000-000000000001")
            assert result is not None
            assert isinstance(result, dict)
            assert result["id"] == "00000000-0000-0000-0000-000000000001"

    @pytest.mark.asyncio
    async def test_get_by_id_raw_returns_none_when_not_found(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = None
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.get_by_id_raw("nonexistent")
            assert result is None

    @pytest.mark.asyncio
    async def test_list_by_tenant_returns_items_and_count(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.return_value = 2
        conn.fetch.return_value = [_make_row(), _make_row()]
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            items, total = await repo.list_by_tenant(
                "00000000-0000-0000-0000-000000000002", page=1, page_size=20
            )
            assert total == 2
            assert len(items) == 2

    @pytest.mark.asyncio
    async def test_list_by_tenant_with_search(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [_make_row()]
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            items, total = await repo.list_by_tenant(
                "00000000-0000-0000-0000-000000000002",
                search="Test",
                page=1,
                page_size=20,
            )
            assert total == 1

    @pytest.mark.asyncio
    async def test_list_by_tenant_with_active_filter(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchval.return_value = 1
        conn.fetch.return_value = [_make_row()]
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            items, total = await repo.list_by_tenant(
                "00000000-0000-0000-0000-000000000002",
                active=True,
                page=1,
                page_size=20,
            )
            assert total == 1

    @pytest.mark.asyncio
    async def test_update_returns_updated_widget(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.side_effect = [
            _make_row(),
            _make_row(name="Updated", config={"brand_color": "#ff0000"}),
        ]
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.update(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
                name="Updated",
                config={"brand_color": "#ff0000"},
            )
            assert result is not None
            assert result.name == "Updated"

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = None
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.update("nonexistent", "t1", name="Updated")
            assert result is None

    @pytest.mark.asyncio
    async def test_soft_delete_returns_true(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.execute.return_value = "UPDATE 1"
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.soft_delete(
                "00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000002",
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_soft_delete_returns_false_when_no_rows(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.execute.return_value = "UPDATE 0"
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.soft_delete("nonexistent", "t1")
            assert result is False

    @pytest.mark.asyncio
    async def test_check_domain_exists_returns_true(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = FakeRow(**{"1": 1})
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.check_domain_exists(
                "https://myshop.com",
                "00000000-0000-0000-0000-000000000002",
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_check_domain_exists_returns_false(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = None
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.check_domain_exists(
                "https://other.com",
                "00000000-0000-0000-0000-000000000002",
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_check_domain_exists_with_exclude_id(self, repo, mock_pool):
        pool, conn = mock_pool
        conn.fetchrow.return_value = None
        with patch(
            "app.repositories.postgres_widget_repo.get_pool",
            AsyncMock(return_value=pool),
        ):
            result = await repo.check_domain_exists(
                "https://myshop.com",
                "00000000-0000-0000-0000-000000000002",
                exclude_id="00000000-0000-0000-0000-000000000003",
            )
            assert result is False

    def test_row_to_response(self, repo):
        row = _make_row()
        response = repo._row_to_response(row)
        assert str(response.id) == "00000000-0000-0000-0000-000000000001"
        assert response.name == "Test Widget"
        assert response.config == {"brand_color": "#2563eb"}

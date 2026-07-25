from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.task import TaskCreate, TaskUpdate
from app.repositories.postgres_repo import PostgresRepository


@pytest.fixture
def mock_conn():
    conn = AsyncMock()
    return conn


@pytest.fixture
def mock_pool_and_conn(mock_conn):
    pool = MagicMock()
    cm = AsyncMock()
    cm.__aenter__.return_value = mock_conn
    cm.__aexit__.return_value = None
    pool.acquire.return_value = cm
    return pool, mock_conn


@pytest.fixture(autouse=True)
def patch_get_pool(mock_pool_and_conn):
    pool, _ = mock_pool_and_conn
    with patch(
        "app.repositories.postgres_repo.get_pool", new=AsyncMock(return_value=pool)
    ):
        yield


from collections.abc import Mapping


class _MockRecord(Mapping):
    def __init__(self, values: dict):
        self._values = values

    def __getitem__(self, key):
        return self._values[key]

    def __iter__(self):
        return iter(self._values.keys())

    def __len__(self):
        return len(self._values)


def _make_record(values: dict):
    return _MockRecord(values)


@pytest.mark.asyncio
class TestPostgresRepository:
    async def test_create_task(self, mock_conn):
        now = datetime.now(timezone.utc)
        row = _make_record(
            {
                "id": 1,
                "title": "Test",
                "done": False,
                "created_at": now,
                "updated_at": now,
            }
        )
        mock_conn.fetchrow.return_value = row

        result = await PostgresRepository.create_task(
            TaskCreate(title="Test", done=False)
        )

        assert result.id == 1
        assert result.title == "Test"
        mock_conn.fetchrow.assert_awaited_once()

    async def test_get_all_tasks(self, mock_conn):
        now = datetime.now(timezone.utc)
        row = _make_record(
            {
                "id": 1,
                "title": "Test",
                "done": False,
                "created_at": now,
                "updated_at": now,
            }
        )
        mock_conn.fetch.return_value = [row]

        results = await PostgresRepository.get_all_tasks()
        assert len(results) == 1
        assert results[0].title == "Test"
        mock_conn.fetch.assert_awaited_once()

    async def test_get_task_found(self, mock_conn):
        now = datetime.now(timezone.utc)
        row = _make_record(
            {
                "id": 1,
                "title": "Test",
                "done": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        mock_conn.fetchrow.return_value = row

        result = await PostgresRepository.get_task(1)
        assert result is not None
        assert result.title == "Test"
        assert result.done is True

    async def test_get_task_not_found(self, mock_conn):
        mock_conn.fetchrow.return_value = None

        result = await PostgresRepository.get_task(999)
        assert result is None

    async def test_update_task_found(self, mock_conn):
        now = datetime.now(timezone.utc)
        row = _make_record(
            {
                "id": 1,
                "title": "Updated",
                "done": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        mock_conn.fetchrow.return_value = row

        result = await PostgresRepository.update_task(
            1, TaskUpdate(title="Updated", done=True)
        )
        assert result is not None
        assert result.title == "Updated"
        assert result.done is True

    async def test_update_task_not_found(self, mock_conn):
        mock_conn.fetchrow.return_value = None

        result = await PostgresRepository.update_task(
            999, TaskUpdate(title="Nope", done=False)
        )
        assert result is None

    async def test_delete_task_found(self, mock_conn):
        mock_conn.execute.return_value = "DELETE 1"

        result = await PostgresRepository.delete_task(1)
        assert result is True

    async def test_delete_task_not_found(self, mock_conn):
        mock_conn.execute.return_value = "DELETE 0"

        result = await PostgresRepository.delete_task(999)
        assert result is False

    async def test_create_task_passes_correct_params(self, mock_conn):
        now = datetime.now(timezone.utc)
        row = _make_record(
            {
                "id": 1,
                "title": "Task",
                "done": False,
                "created_at": now,
                "updated_at": now,
            }
        )
        mock_conn.fetchrow.return_value = row

        await PostgresRepository.create_task(TaskCreate(title="Task", done=True))

        call_args = mock_conn.fetchrow.await_args
        assert call_args is not None
        args = call_args[0]
        assert "INSERT INTO tasks" in args[0]
        assert args[1] == "Task"
        assert args[2] is True

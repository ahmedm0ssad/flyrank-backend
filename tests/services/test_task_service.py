from unittest.mock import AsyncMock

import pytest

from app.models.task import TaskCreate, TaskResponse, TaskUpdate
from app.services import task_service


@pytest.fixture(autouse=True)
def mock_repo():
    repo = AsyncMock()
    task_service._repo = repo
    return repo


class TestTaskService:
    @pytest.mark.asyncio
    async def test_create_task(self, mock_repo):
        task_data = TaskCreate(title="Test", done=True)
        expected = TaskResponse(
            id=1,
            title="Test",
            done=True,
            created_at=__import__("datetime").datetime.now(),
            updated_at=__import__("datetime").datetime.now(),
        )
        mock_repo.create_task.return_value = expected

        result = await task_service.create_task(task_data)

        assert result.id == 1
        assert result.title == "Test"
        mock_repo.create_task.assert_awaited_once_with(task_data)

    @pytest.mark.asyncio
    async def test_get_all_tasks(self, mock_repo):
        expected = [
            TaskResponse(
                id=1,
                title="Task 1",
                done=False,
                created_at=__import__("datetime").datetime.now(),
                updated_at=__import__("datetime").datetime.now(),
            )
        ]
        mock_repo.get_all_tasks.return_value = expected

        result = await task_service.get_all_tasks()

        assert len(result) == 1
        assert result[0].title == "Task 1"
        mock_repo.get_all_tasks.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_task_found(self, mock_repo):
        expected = TaskResponse(
            id=1,
            title="Found",
            done=False,
            created_at=__import__("datetime").datetime.now(),
            updated_at=__import__("datetime").datetime.now(),
        )
        mock_repo.get_task.return_value = expected

        result = await task_service.get_task(1)

        assert result is not None
        assert result.title == "Found"
        mock_repo.get_task.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, mock_repo):
        mock_repo.get_task.return_value = None

        result = await task_service.get_task(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_task_found(self, mock_repo):
        task_data = TaskUpdate(title="Updated", done=True)
        expected = TaskResponse(
            id=1,
            title="Updated",
            done=True,
            created_at=__import__("datetime").datetime.now(),
            updated_at=__import__("datetime").datetime.now(),
        )
        mock_repo.update_task.return_value = expected

        result = await task_service.update_task(1, task_data)

        assert result is not None
        assert result.title == "Updated"
        mock_repo.update_task.assert_awaited_once_with(1, task_data)

    @pytest.mark.asyncio
    async def test_update_task_not_found(self, mock_repo):
        mock_repo.update_task.return_value = None

        result = await task_service.update_task(
            999, TaskUpdate(title="Nope", done=False)
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_task_success(self, mock_repo):
        mock_repo.delete_task.return_value = True

        result = await task_service.delete_task(1)

        assert result is True
        mock_repo.delete_task.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self, mock_repo):
        mock_repo.delete_task.return_value = False

        result = await task_service.delete_task(999)

        assert result is False

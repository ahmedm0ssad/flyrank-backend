import pytest

from app.models.task import TaskCreate, TaskUpdate
from app.repositories.inmemory_repo import InMemoryRepository


@pytest.fixture
def repo():
    return InMemoryRepository()


@pytest.mark.asyncio
class TestInMemoryRepository:
    async def test_create_task_returns_task_with_auto_id(self, repo):
        task_data = TaskCreate(title="New task", done=True)
        result = await repo.create_task(task_data)
        assert result.title == "New task"
        assert result.done is True
        assert result.id == 4

    async def test_create_task_increments_id(self, repo):
        t1 = await repo.create_task(TaskCreate(title="Task A"))
        t2 = await repo.create_task(TaskCreate(title="Task B"))
        assert t2.id == t1.id + 1

    async def test_get_all_tasks_returns_seeded_tasks(self, repo):
        tasks = await repo.get_all_tasks()
        assert len(tasks) == 3
        assert tasks[0].title == "Build a project"

    async def test_get_all_tasks_after_create(self, repo):
        await repo.create_task(TaskCreate(title="Extra"))
        tasks = await repo.get_all_tasks()
        assert len(tasks) == 4

    async def test_get_task_returns_task(self, repo):
        task = await repo.get_task(1)
        assert task is not None
        assert task.id == 1
        assert task.title == "Learn FastAPI"

    async def test_get_task_returns_none_for_missing(self, repo):
        task = await repo.get_task(999)
        assert task is None

    async def test_update_task_updates_fields(self, repo):
        updated = await repo.update_task(
            1, TaskUpdate(title="Updated title", done=True)
        )
        assert updated is not None
        assert updated.title == "Updated title"
        assert updated.done is True
        assert updated.id == 1

    async def test_update_task_updates_timestamp(self, repo):
        import asyncio

        original = await repo.get_task(1)
        await asyncio.sleep(0.01)
        updated = await repo.update_task(
            1, TaskUpdate(title="Updated title", done=True)
        )
        assert updated.updated_at > original.updated_at

    async def test_update_task_returns_none_for_missing(self, repo):
        result = await repo.update_task(999, TaskUpdate(title="Nope", done=False))
        assert result is None

    async def test_delete_task_returns_true(self, repo):
        result = await repo.delete_task(1)
        assert result is True

    async def test_delete_task_removes_task(self, repo):
        await repo.delete_task(1)
        task = await repo.get_task(1)
        assert task is None

    async def test_delete_task_returns_false_for_missing(self, repo):
        result = await repo.delete_task(999)
        assert result is False

    async def test_all_tasks_after_delete(self, repo):
        await repo.delete_task(1)
        tasks = await repo.get_all_tasks()
        assert len(tasks) == 2

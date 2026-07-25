import os
import tempfile

import pytest

from app.models.task import TaskCreate, TaskUpdate
from app.repositories.sqlite_repo import SqliteRepository


@pytest.fixture
def repo(tmp_path):
    return SqliteRepository(db_path=str(tmp_path / "test.db"))


@pytest.mark.asyncio
class TestSqliteRepository:
    async def test_seed_creates_three_tasks(self, repo):
        tasks = await repo.get_all_tasks()
        assert len(tasks) == 3
        titles = {t.title for t in tasks}
        assert titles == {"Learn FastAPI", "Write tests", "Build a project"}

    async def test_seed_runs_at_most_once(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        repo1 = SqliteRepository(db_path=db_path)
        tasks1 = await repo1.get_all_tasks()
        assert len(tasks1) == 3
        repo2 = SqliteRepository(db_path=db_path)
        tasks2 = await repo2.get_all_tasks()
        assert len(tasks2) == 3

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

    async def test_create_task_sets_created_and_updated(self, repo):
        result = await repo.create_task(TaskCreate(title="Timed task"))
        assert result.created_at is not None
        assert result.updated_at is not None
        assert result.created_at == result.updated_at

    async def test_get_all_tasks_returns_seeded_tasks(self, repo):
        tasks = await repo.get_all_tasks()
        assert len(tasks) == 3

    async def test_get_all_tasks_after_create(self, repo):
        await repo.create_task(TaskCreate(title="Extra"))
        tasks = await repo.get_all_tasks()
        assert len(tasks) == 4

    async def test_get_all_tasks_order_by_title(self, repo):
        tasks = await repo.get_all_tasks()
        titles = [t.title for t in tasks]
        assert titles == sorted(titles)

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

    async def test_update_task_refreshes_updated_at(self, repo):
        import asyncio

        original = await repo.get_task(1)
        await asyncio.sleep(0.01)
        updated = await repo.update_task(
            1, TaskUpdate(title="Updated title", done=True)
        )
        assert updated.updated_at > original.updated_at

    async def test_update_task_does_not_change_created_at(self, repo):
        original = await repo.get_task(1)
        updated = await repo.update_task(1, TaskUpdate(title="Still same", done=True))
        assert updated.created_at == original.created_at

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

    async def test_search_filter(self, repo):
        await repo.create_task(TaskCreate(title="FastAPI rocks"))
        await repo.create_task(TaskCreate(title="not matching"))
        tasks = await repo.get_all_tasks(search="fast")
        assert all("fast" in t.title.lower() for t in tasks)
        assert len(tasks) == 2

    async def test_done_filter(self, repo):
        await repo.create_task(TaskCreate(title="Do me", done=True))
        tasks_done = await repo.get_all_tasks(done=True)
        assert all(t.done for t in tasks_done)
        assert len(tasks_done) == 1

        tasks_not_done = await repo.get_all_tasks(done=False)
        assert all(not t.done for t in tasks_not_done)
        assert len(tasks_not_done) == 3

    async def test_search_and_done_combined(self, repo):
        await repo.create_task(TaskCreate(title="Finish FastAPI", done=True))
        await repo.create_task(TaskCreate(title="FastAPI intro", done=False))
        tasks = await repo.get_all_tasks(search="fast", done=True)
        assert len(tasks) == 1
        assert tasks[0].title == "Finish FastAPI"

    async def test_stats(self, repo):
        stats = await repo.get_stats()
        assert stats["total"] == 3
        assert stats["done"] == 0
        assert stats["not_done"] == 3

        await repo.create_task(TaskCreate(title="Done task", done=True))
        stats = await repo.get_stats()
        assert stats["total"] == 4
        assert stats["done"] == 1
        assert stats["not_done"] == 3

    async def test_stats_after_delete(self, repo):
        await repo.delete_task(1)
        stats = await repo.get_stats()
        assert stats["total"] == 2

    async def test_persistence_across_restart(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            repo1 = SqliteRepository(db_path=path)
            created = await repo1.create_task(TaskCreate(title="Survivor"))
            task_id = created.id

            repo2 = SqliteRepository(db_path=path)
            task = await repo2.get_task(task_id)
            assert task is not None
            assert task.title == "Survivor"

            tasks = await repo2.get_all_tasks()
            assert len(tasks) == 4
        finally:
            os.unlink(path)

    async def test_delete_db_recreates_and_reseeds(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            repo1 = SqliteRepository(db_path=path)
            await repo1.create_task(TaskCreate(title="Temp"))
            os.unlink(path)

            repo2 = SqliteRepository(db_path=path)
            tasks = await repo2.get_all_tasks()
            assert len(tasks) == 3
            titles = {t.title for t in tasks}
            assert titles == {"Learn FastAPI", "Write tests", "Build a project"}
        finally:
            if os.path.exists(path):
                os.unlink(path)

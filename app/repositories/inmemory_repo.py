from datetime import datetime, timezone
from typing import Optional

from app.models.task import TaskCreate, TaskUpdate, TaskResponse


class InMemoryRepository:
    def __init__(self):
        self._tasks: dict[int, dict] = {}
        self._next_id: int = 1
        self._seed()

    def _seed(self):
        now = datetime.now(timezone.utc)
        examples = [
            {"title": "Learn FastAPI", "done": False},
            {"title": "Write tests", "done": False},
            {"title": "Build a project", "done": False},
        ]
        for ex in examples:
            task = {
                "id": self._next_id,
                "title": ex["title"],
                "done": ex["done"],
                "created_at": now,
                "updated_at": now,
            }
            self._tasks[self._next_id] = task
            self._next_id += 1

    async def create_task(self, task_data: TaskCreate) -> TaskResponse:
        now = datetime.now(timezone.utc)
        task = {
            "id": self._next_id,
            "title": task_data.title,
            "done": task_data.done,
            "created_at": now,
            "updated_at": now,
        }
        self._tasks[self._next_id] = task
        self._next_id += 1
        return TaskResponse(**task)

    async def get_all_tasks(self) -> list[TaskResponse]:
        return [TaskResponse(**t) for t in self._tasks.values()]

    async def get_task(self, task_id: int) -> Optional[TaskResponse]:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return TaskResponse(**task)

    async def update_task(
        self, task_id: int, task_data: TaskUpdate
    ) -> Optional[TaskResponse]:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        now = datetime.now(timezone.utc)
        task["title"] = task_data.title
        task["done"] = task_data.done
        task["updated_at"] = now
        return TaskResponse(**task)

    async def delete_task(self, task_id: int) -> bool:
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

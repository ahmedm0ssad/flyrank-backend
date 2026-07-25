from typing import Protocol

from app.models.task import TaskCreate, TaskResponse, TaskUpdate


class TaskRepository(Protocol):
    async def create_task(self, task_data: TaskCreate) -> TaskResponse: ...

    async def get_all_tasks(
        self,
        search: str | None = None,
        done: bool | None = None,
    ) -> list[TaskResponse]: ...

    async def get_task(self, task_id: int) -> TaskResponse | None: ...

    async def update_task(
        self, task_id: int, task_data: TaskUpdate
    ) -> TaskResponse | None: ...

    async def delete_task(self, task_id: int) -> bool: ...

    async def get_stats(self) -> dict: ...

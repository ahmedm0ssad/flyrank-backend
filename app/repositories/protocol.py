from typing import Optional, Protocol

from app.models.task import TaskCreate, TaskUpdate, TaskResponse


class TaskRepository(Protocol):
    async def create_task(self, task_data: TaskCreate) -> TaskResponse: ...

    async def get_all_tasks(
        self,
        search: Optional[str] = None,
        done: Optional[bool] = None,
    ) -> list[TaskResponse]: ...

    async def get_task(self, task_id: int) -> Optional[TaskResponse]: ...

    async def update_task(
        self, task_id: int, task_data: TaskUpdate
    ) -> Optional[TaskResponse]: ...

    async def delete_task(self, task_id: int) -> bool: ...

    async def get_stats(self) -> dict: ...

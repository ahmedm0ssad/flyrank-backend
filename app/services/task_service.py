from typing import Optional

from app.database import is_postgres_enabled
from app.models.task import TaskCreate, TaskUpdate, TaskResponse
from app.repositories.protocol import TaskRepository


if is_postgres_enabled():
    from app.repositories.postgres_repo import PostgresRepository

    _repo: TaskRepository = PostgresRepository()
else:
    from app.repositories.inmemory_repo import InMemoryRepository

    _repo: TaskRepository = InMemoryRepository()


async def create_task(task_data: TaskCreate) -> TaskResponse:
    return await _repo.create_task(task_data)


async def get_all_tasks() -> list[TaskResponse]:
    return await _repo.get_all_tasks()


async def get_task(task_id: int) -> Optional[TaskResponse]:
    return await _repo.get_task(task_id)


async def update_task(task_id: int, task_data: TaskUpdate) -> Optional[TaskResponse]:
    return await _repo.update_task(task_id, task_data)


async def delete_task(task_id: int) -> bool:
    return await _repo.delete_task(task_id)

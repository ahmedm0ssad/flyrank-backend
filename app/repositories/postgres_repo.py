from datetime import datetime, timezone
from typing import Optional

from app.database import get_pool
from app.models.task import TaskCreate, TaskUpdate, TaskResponse


class PostgresRepository:
    @staticmethod
    async def create_task(task_data: TaskCreate) -> TaskResponse:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tasks (title, done, created_at, updated_at)
                VALUES ($1, $2, $3, $4)
                RETURNING id, title, done, created_at, updated_at
                """,
                task_data.title,
                task_data.done,
                now,
                now,
            )
        return TaskResponse(**dict(row))

    @staticmethod
    async def get_all_tasks() -> list[TaskResponse]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, title, done, created_at, updated_at FROM tasks ORDER BY id"
            )
        return [TaskResponse(**dict(r)) for r in rows]

    @staticmethod
    async def get_task(task_id: int) -> Optional[TaskResponse]:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, title, done, created_at, updated_at FROM tasks WHERE id = $1",
                task_id,
            )
        if row is None:
            return None
        return TaskResponse(**dict(row))

    @staticmethod
    async def update_task(task_id: int, task_data: TaskUpdate) -> Optional[TaskResponse]:
        pool = await get_pool()
        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE tasks SET title = $1, done = $2, updated_at = $3
                WHERE id = $4
                RETURNING id, title, done, created_at, updated_at
                """,
                task_data.title,
                task_data.done,
                now,
                task_id,
            )
        if row is None:
            return None
        return TaskResponse(**dict(row))

    @staticmethod
    async def delete_task(task_id: int) -> bool:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM tasks WHERE id = $1", task_id
            )
        return result != "DELETE 0"

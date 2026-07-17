from datetime import datetime, timezone
from typing import Optional

from app.models.task import TaskCreate, TaskUpdate, TaskResponse


_tasks: dict[int, dict] = {}
_next_id: int = 1


def _seed():
    global _next_id
    now = datetime.now(timezone.utc)
    examples = [
        {"title": "Learn FastAPI", "done": False},
        {"title": "Write tests", "done": False},
        {"title": "Build a project", "done": False},
    ]
    for ex in examples:
        task = {
            "id": _next_id,
            "title": ex["title"],
            "done": ex["done"],
            "created_at": now,
            "updated_at": now,
        }
        _tasks[_next_id] = task
        _next_id += 1


_seed()


def create_task(task_data: TaskCreate) -> TaskResponse:
    global _next_id
    now = datetime.now(timezone.utc)
    task = {
        "id": _next_id,
        "title": task_data.title,
        "done": task_data.done,
        "created_at": now,
        "updated_at": now,
    }
    _tasks[_next_id] = task
    _next_id += 1
    return TaskResponse(**task)


def get_all_tasks() -> list[TaskResponse]:
    return [TaskResponse(**t) for t in _tasks.values()]


def get_task(task_id: int) -> Optional[TaskResponse]:
    task = _tasks.get(task_id)
    if task is None:
        return None
    return TaskResponse(**task)


def update_task(task_id: int, task_data: TaskUpdate) -> Optional[TaskResponse]:
    task = _tasks.get(task_id)
    if task is None:
        return None
    now = datetime.now(timezone.utc)
    task["title"] = task_data.title
    task["done"] = task_data.done
    task["updated_at"] = now
    return TaskResponse(**task)


def delete_task(task_id: int) -> bool:
    if task_id in _tasks:
        del _tasks[task_id]
        return True
    return False

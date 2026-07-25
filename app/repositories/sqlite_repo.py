import sqlite3
from datetime import datetime, timezone

from starlette.concurrency import run_in_threadpool

from app.models.task import TaskCreate, TaskResponse, TaskUpdate


class SqliteRepository:
    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    done BOOLEAN NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            if count == 0:
                now = datetime.now(timezone.utc).isoformat()
                examples = [
                    ("Learn FastAPI", 0, now, now),
                    ("Write tests", 0, now, now),
                    ("Build a project", 0, now, now),
                ]
                conn.executemany(
                    "INSERT INTO tasks (title, done, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    examples,
                )
                conn.commit()
        finally:
            conn.close()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    @staticmethod
    def _row_to_response(row):
        return TaskResponse(
            id=row[0],
            title=row[1],
            done=bool(row[2]),
            created_at=datetime.fromisoformat(row[3]),
            updated_at=datetime.fromisoformat(row[4]),
        )

    async def create_task(self, task_data: TaskCreate) -> TaskResponse:
        def _work():
            conn = self._connect()
            try:
                now = datetime.now(timezone.utc).isoformat()
                cursor = conn.execute(
                    "INSERT INTO tasks (title, done, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (task_data.title, int(task_data.done), now, now),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT id, title, done, created_at, updated_at FROM tasks WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
                return self._row_to_response(row)
            finally:
                conn.close()

        return await run_in_threadpool(_work)

    async def get_all_tasks(
        self,
        search: str | None = None,
        done: bool | None = None,
    ) -> list[TaskResponse]:
        def _work():
            conn = self._connect()
            try:
                query = "SELECT id, title, done, created_at, updated_at FROM tasks WHERE 1=1"
                params: list = []
                if search is not None:
                    query += " AND title LIKE ?"
                    params.append(f"%{search}%")
                if done is not None:
                    query += " AND done = ?"
                    params.append(int(done))
                query += " ORDER BY title"
                rows = conn.execute(query, params).fetchall()
                return [self._row_to_response(r) for r in rows]
            finally:
                conn.close()

        return await run_in_threadpool(_work)

    async def get_task(self, task_id: int) -> TaskResponse | None:
        def _work():
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT id, title, done, created_at, updated_at FROM tasks WHERE id = ?",
                    (task_id,),
                ).fetchone()
                if row is None:
                    return None
                return self._row_to_response(row)
            finally:
                conn.close()

        return await run_in_threadpool(_work)

    async def update_task(
        self, task_id: int, task_data: TaskUpdate
    ) -> TaskResponse | None:
        def _work():
            conn = self._connect()
            try:
                now = datetime.now(timezone.utc).isoformat()
                cursor = conn.execute(
                    "UPDATE tasks SET title = ?, done = ?, updated_at = ? WHERE id = ?",
                    (task_data.title, int(task_data.done), now, task_id),
                )
                conn.commit()
                if cursor.rowcount == 0:
                    return None
                row = conn.execute(
                    "SELECT id, title, done, created_at, updated_at FROM tasks WHERE id = ?",
                    (task_id,),
                ).fetchone()
                return self._row_to_response(row)
            finally:
                conn.close()

        return await run_in_threadpool(_work)

    async def delete_task(self, task_id: int) -> bool:
        def _work():
            conn = self._connect()
            try:
                cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

        return await run_in_threadpool(_work)

    async def get_stats(self) -> dict:
        def _work():
            conn = self._connect()
            try:
                total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
                done_count = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE done = 1"
                ).fetchone()[0]
                return {
                    "total": total,
                    "done": done_count,
                    "not_done": total - done_count,
                }
            finally:
                conn.close()

        return await run_in_threadpool(_work)

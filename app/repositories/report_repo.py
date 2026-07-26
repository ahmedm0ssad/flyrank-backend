from datetime import datetime, timezone

from app.database import get_pool, is_postgres_enabled
from app.models.report import ReportResponse, ReportStatus


class ReportRepository:
    def __init__(self):
        if is_postgres_enabled():
            self._use_postgres = True
        else:
            self._use_postgres = False
            self._init_sqlite()

    @staticmethod
    def _init_sqlite():
        import sqlite3

        conn = sqlite3.connect("tasks.db")
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'queued',
                    file_path TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def _connect_sqlite(self):
        import sqlite3

        return sqlite3.connect("tasks.db")

    @staticmethod
    def _row_to_response(row) -> ReportResponse:
        return ReportResponse(
            report_id=row[0],
            job_id=row[1],
            status=ReportStatus(row[2]),
            file_path=row[3],
            error=row[4],
            created_at=datetime.fromisoformat(row[5]),
            started_at=datetime.fromisoformat(row[6]) if row[6] else None,
            finished_at=datetime.fromisoformat(row[7]) if row[7] else None,
        )

    async def create_report(self, job_id: str) -> ReportResponse:
        now = datetime.now(timezone.utc)
        if self._use_postgres:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO reports (job_id, status, created_at)
                    VALUES ($1, $2, $3)
                    RETURNING id, job_id, status, file_path, error, created_at, started_at, finished_at
                    """,
                    job_id,
                    ReportStatus.QUEUED.value,
                    now,
                )
            return ReportResponse(**dict(row))
        else:
            conn = self._connect_sqlite()
            try:
                cursor = conn.execute(
                    "INSERT INTO reports (job_id, status, created_at) VALUES (?, ?, ?)",
                    (job_id, ReportStatus.QUEUED.value, now.isoformat()),
                )
                conn.commit()
                row = conn.execute(
                    "SELECT id, job_id, status, file_path, error, created_at, started_at, finished_at FROM reports WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
                return self._row_to_response(row)
            finally:
                conn.close()

    async def get_report_by_job_id(self, job_id: str) -> ReportResponse | None:
        if self._use_postgres:
            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT id, job_id, status, file_path, error, created_at, started_at, finished_at FROM reports WHERE job_id = $1",
                    job_id,
                )
            if row is None:
                return None
            return ReportResponse(**dict(row))
        else:
            conn = self._connect_sqlite()
            try:
                row = conn.execute(
                    "SELECT id, job_id, status, file_path, error, created_at, started_at, finished_at FROM reports WHERE job_id = ?",
                    (job_id,),
                ).fetchone()
                if row is None:
                    return None
                return self._row_to_response(row)
            finally:
                conn.close()

    async def update_report_status(
        self,
        job_id: str,
        status: ReportStatus,
        file_path: str | None = None,
        error: str | None = None,
    ) -> ReportResponse | None:
        now = datetime.now(timezone.utc)
        if self._use_postgres:
            pool = await get_pool()
            async with pool.acquire() as conn:
                fields = ["status = $1"]
                params = [status.value]
                param_idx = 2

                if status == ReportStatus.STARTED:
                    fields.append(f"started_at = ${param_idx}")
                    params.append(now)
                    param_idx += 1
                elif status in (ReportStatus.FINISHED, ReportStatus.FAILED):
                    fields.append(f"finished_at = ${param_idx}")
                    params.append(now)
                    param_idx += 1

                if file_path is not None:
                    fields.append(f"file_path = ${param_idx}")
                    params.append(file_path)
                    param_idx += 1
                if error is not None:
                    fields.append(f"error = ${param_idx}")
                    params.append(error)
                    param_idx += 1

                params.append(job_id)
                query = f"""
                    UPDATE reports SET {', '.join(fields)}
                    WHERE job_id = ${param_idx - 1}
                    RETURNING id, job_id, status, file_path, error, created_at, started_at, finished_at
                """
                row = await conn.fetchrow(query, *params)
            if row is None:
                return None
            return ReportResponse(**dict(row))
        else:
            conn = self._connect_sqlite()
            try:
                fields = ["status = ?"]
                params = [status.value]

                if status == ReportStatus.STARTED:
                    fields.append("started_at = ?")
                    params.append(now.isoformat())
                elif status in (ReportStatus.FINISHED, ReportStatus.FAILED):
                    fields.append("finished_at = ?")
                    params.append(now.isoformat())

                if file_path is not None:
                    fields.append("file_path = ?")
                    params.append(file_path)
                if error is not None:
                    fields.append("error = ?")
                    params.append(error)

                params.append(job_id)
                conn.execute(
                    f"UPDATE reports SET {', '.join(fields)} WHERE job_id = ?",
                    params,
                )
                conn.commit()
                row = conn.execute(
                    "SELECT id, job_id, status, file_path, error, created_at, started_at, finished_at FROM reports WHERE job_id = ?",
                    (job_id,),
                ).fetchone()
                if row is None:
                    return None
                return self._row_to_response(row)
            finally:
                conn.close()

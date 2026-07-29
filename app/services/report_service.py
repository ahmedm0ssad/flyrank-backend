import logging
import os

from app.core.queue import create_report_job
from app.models.report import ReportMetadataResponse, ReportStatus
from app.repositories.report_repo import ReportRepository

logger = logging.getLogger(__name__)

_repo = ReportRepository()
REPORTS_DIR = "generated_reports"


async def enqueue_report() -> dict:
    job_id, status = create_report_job()
    await _repo.create_report(job_id)
    logger.info("Report job %s created with status %s", job_id, status.value)
    return {"job_id": job_id, "status": status.value}


async def get_report_metadata(job_id: str) -> ReportMetadataResponse:
    report = await _repo.get_report_by_job_id(job_id)
    if report is None:
        return None

    download_url = None
    if report.status == ReportStatus.FINISHED and report.file_path:
        filename = os.path.basename(report.file_path)
        download_url = f"/reports/files/{filename}"

    return ReportMetadataResponse(
        job_id=report.job_id,
        status=report.status,
        download_url=download_url,
        error=report.error,
    )


def get_report_data_for_worker(job_id: str) -> dict:
    import sqlite3

    data = {
        "total": 0,
        "done": 0,
        "not_done": 0,
        "completion_pct": 0.0,
        "recent_tasks": [],
    }

    db_path = "tasks.db"
    if not os.path.exists(db_path):
        return data

    conn = sqlite3.connect(db_path)
    try:
        total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        done = conn.execute("SELECT COUNT(*) FROM tasks WHERE done = 1").fetchone()[0]
        not_done = total - done
        pct = (done / total * 100) if total > 0 else 0.0

        recent = conn.execute(
            "SELECT id, title, done FROM tasks ORDER BY id DESC LIMIT 10"
        ).fetchall()

        data = {
            "total": total,
            "done": done,
            "not_done": not_done,
            "completion_pct": round(pct, 1),
            "recent_tasks": [
                {"id": r[0], "title": r[1], "done": bool(r[2])} for r in recent
            ],
        }
    finally:
        conn.close()
    return data


def get_scraped_books_stats() -> dict | None:
    import sqlite3

    db_path = "tasks.db"
    if not os.path.exists(db_path):
        return None

    conn = sqlite3.connect(db_path)
    try:
        try:
            total = conn.execute("SELECT COUNT(*) FROM scraped_books").fetchone()[0]
        except sqlite3.OperationalError:
            return None

        if total == 0:
            return {"total": 0}

        avg_price = conn.execute(
            "SELECT AVG(price) FROM scraped_books WHERE price IS NOT NULL"
        ).fetchone()[0]
        categories = conn.execute(
            "SELECT COUNT(DISTINCT category) FROM scraped_books WHERE category IS NOT NULL"
        ).fetchone()[0]

        return {
            "total": total,
            "avg_price": round(avg_price, 2) if avg_price else None,
            "categories": categories,
        }
    finally:
        conn.close()


def get_ai_jobs_stats() -> dict | None:
    try:
        from app.core.queue import get_connection

        conn = get_connection()
        cursor = 0
        total = 0
        completed = 0
        failed = 0

        while True:
            cursor, keys = conn.scan(cursor=cursor, match="job:*", count=100)
            for key in keys:
                if isinstance(key, bytes):
                    key = key.decode()
                data = conn.hgetall(key)
                status = (
                    data.get(b"status", b"").decode()
                    if isinstance(data.get(b"status"), bytes)
                    else data.get("status", "")
                )
                if status == "finished":
                    completed += 1
                elif status == "failed":
                    failed += 1
                total += 1
            if cursor == 0:
                break

        if total == 0:
            return None

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
        }
    except Exception:  # noqa: BLE001
        return None


async def update_report_status(
    job_id: str,
    status: ReportStatus,
    file_path: str | None = None,
    error: str | None = None,
):
    return await _repo.update_report_status(
        job_id, status, file_path=file_path, error=error
    )

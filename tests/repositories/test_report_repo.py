import os

import pytest

from app.models.report import ReportStatus


@pytest.fixture(autouse=True)
def _cleanup_db():
    yield
    db_path = "tasks.db"
    if os.path.exists(db_path):
        conn = __import__("sqlite3").connect(db_path)
        try:
            conn.execute("DELETE FROM reports")
            conn.commit()
        finally:
            conn.close()


class TestReportRepository:
    @pytest.mark.asyncio
    async def test_create_report_returns_report_response(self):
        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        result = await repo.create_report("test-job-1")
        assert result.job_id == "test-job-1"
        assert result.status == ReportStatus.QUEUED

    @pytest.mark.asyncio
    async def test_create_report_has_created_at(self):
        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        result = await repo.create_report("test-job-2")
        assert result.created_at is not None

    @pytest.mark.asyncio
    async def test_get_report_by_job_id_found(self):
        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        await repo.create_report("test-job-3")
        result = await repo.get_report_by_job_id("test-job-3")
        assert result is not None
        assert result.job_id == "test-job-3"

    @pytest.mark.asyncio
    async def test_get_report_by_job_id_not_found(self):
        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        result = await repo.get_report_by_job_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_report_status_to_started(self):
        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        await repo.create_report("test-job-4")
        result = await repo.update_report_status("test-job-4", ReportStatus.STARTED)
        assert result.status == ReportStatus.STARTED
        assert result.started_at is not None

    @pytest.mark.asyncio
    async def test_update_report_status_to_finished(self):
        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        await repo.create_report("test-job-5")
        await repo.update_report_status("test-job-5", ReportStatus.STARTED)
        result = await repo.update_report_status(
            "test-job-5", ReportStatus.FINISHED, file_path="/path/to/report.pdf"
        )
        assert result.status == ReportStatus.FINISHED
        assert result.file_path == "/path/to/report.pdf"
        assert result.finished_at is not None

    @pytest.mark.asyncio
    async def test_update_report_status_to_failed(self):
        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        await repo.create_report("test-job-6")
        result = await repo.update_report_status(
            "test-job-6", ReportStatus.FAILED, error="Something went wrong"
        )
        assert result.status == ReportStatus.FAILED
        assert result.error == "Something went wrong"
        assert result.finished_at is not None

    @pytest.mark.asyncio
    async def test_update_report_nonexistent(self):
        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        result = await repo.update_report_status("nonexistent", ReportStatus.STARTED)
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_reports(self):
        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        await repo.create_report("job-a")
        await repo.create_report("job-b")
        r1 = await repo.get_report_by_job_id("job-a")
        r2 = await repo.get_report_by_job_id("job-b")
        assert r1 is not None
        assert r2 is not None
        assert r1.job_id == "job-a"
        assert r2.job_id == "job-b"

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        await repo.create_report("lifecycle-job")
        await repo.update_report_status("lifecycle-job", ReportStatus.STARTED)
        await repo.update_report_status(
            "lifecycle-job", ReportStatus.FINISHED, file_path="/path/to/report.pdf"
        )
        result = await repo.get_report_by_job_id("lifecycle-job")
        assert result.status == ReportStatus.FINISHED
        assert result.file_path == "/path/to/report.pdf"
        assert result.started_at is not None
        assert result.finished_at is not None

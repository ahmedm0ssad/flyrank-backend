import pytest

from app.models.report import ReportStatus


class TestReportService:
    @pytest.mark.asyncio
    async def test_enqueue_report_returns_job_id_and_status(self, monkeypatch):
        from app.services.report_service import enqueue_report

        result = await enqueue_report()
        assert "job_id" in result
        assert result["status"] == "queued"

    @pytest.mark.asyncio
    async def test_enqueue_report_creates_different_jobs(self, monkeypatch):
        from app.services.report_service import enqueue_report

        r1 = await enqueue_report()
        r2 = await enqueue_report()
        assert r1["job_id"] != r2["job_id"]

    @pytest.mark.asyncio
    async def test_get_report_metadata_returns_none_for_missing(self, monkeypatch):
        from app.services.report_service import get_report_metadata

        result = await get_report_metadata("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_report_metadata_returns_metadata(self, monkeypatch):
        from app.services.report_service import enqueue_report, get_report_metadata

        enqueued = await enqueue_report()
        job_id = enqueued["job_id"]
        metadata = await get_report_metadata(job_id)
        assert metadata is not None
        assert metadata.job_id == job_id
        assert metadata.status == ReportStatus.QUEUED

    def test_get_report_data_for_worker_returns_task_data(self, monkeypatch):
        from app.services.report_service import get_report_data_for_worker

        data = get_report_data_for_worker("test-job")
        assert "total" in data
        assert "done" in data
        assert "not_done" in data
        assert "completion_pct" in data
        assert "recent_tasks" in data

    def test_get_scraped_books_stats_returns_none_without_db(self, monkeypatch):
        from app.services.report_service import get_scraped_books_stats

        result = get_scraped_books_stats()
        assert result is None

    def test_get_ai_jobs_stats_returns_none_on_error(self, monkeypatch):
        from app.services.report_service import get_ai_jobs_stats

        result = get_ai_jobs_stats()
        assert result is None

    @pytest.mark.asyncio
    async def test_report_lifecycle_through_service(self, monkeypatch):
        from app.services.report_service import (
            enqueue_report,
            get_report_metadata,
            update_report_status,
        )

        enqueued = await enqueue_report()
        job_id = enqueued["job_id"]

        await update_report_status(job_id, ReportStatus.STARTED)
        metadata = await get_report_metadata(job_id)
        assert metadata.status == ReportStatus.STARTED

        await update_report_status(
            job_id, ReportStatus.FINISHED, file_path="/path/to/report.pdf"
        )
        metadata = await get_report_metadata(job_id)
        assert metadata.status == ReportStatus.FINISHED
        assert metadata.download_url is not None
        assert "/reports/files/" in metadata.download_url

    @pytest.mark.asyncio
    async def test_failed_report_has_error_in_metadata(self, monkeypatch):
        from app.services.report_service import (
            enqueue_report,
            get_report_metadata,
            update_report_status,
        )

        enqueued = await enqueue_report()
        job_id = enqueued["job_id"]

        await update_report_status(job_id, ReportStatus.FAILED, error="Test error")
        metadata = await get_report_metadata(job_id)
        assert metadata.status == ReportStatus.FAILED
        assert metadata.error == "Test error"
        assert metadata.download_url is None

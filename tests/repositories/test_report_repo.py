import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

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


class TestReportRepositoryPostgres:
    """Test the Postgres code paths in ReportRepository.

    These tests undo the conftest _no_postgres patch and provide a
    mock asyncpg pool so the self._use_postgres = True branch runs.
    """

    @pytest.fixture(autouse=True)
    def _enable_postgres(self, monkeypatch):
        monkeypatch.setattr(
            "app.repositories.report_repo.is_postgres_enabled", lambda: True
        )
        monkeypatch.setattr(
            "app.core.database.DATABASE_URL", "postgresql://localhost/test"
        )

    @pytest.fixture
    def _mock_pg_pool(self):
        class _AsyncCtxMgr:
            def __init__(self, conn):
                self._conn = conn

            async def __aenter__(self):
                return self._conn

            async def __aexit__(self, *args):
                return None

        def _build(mock_conn=None):
            mock_pool = MagicMock()
            cm = _AsyncCtxMgr(mock_conn)
            mock_pool.acquire = MagicMock(return_value=cm)
            return mock_pool

        return _build

    @pytest.mark.asyncio
    async def test_create_report_postgres_path(self, monkeypatch, _mock_pg_pool):
        mock_conn = AsyncMock()
        mock_row = {
            "report_id": 1,
            "job_id": "pg-job-1",
            "status": "queued",
            "file_path": None,
            "error": None,
            "created_at": datetime.now(timezone.utc),
            "started_at": None,
            "finished_at": None,
        }
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = _mock_pg_pool(mock_conn)

        async def fake_get_pool():
            return mock_pool

        monkeypatch.setattr("app.repositories.report_repo.get_pool", fake_get_pool)

        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        assert repo._use_postgres is True
        result = await repo.create_report("pg-job-1")
        assert result.job_id == "pg-job-1"

    @pytest.mark.asyncio
    async def test_update_report_status_postgres_started(
        self, monkeypatch, _mock_pg_pool
    ):
        mock_conn = AsyncMock()
        mock_row = {
            "report_id": 1,
            "job_id": "pg-job-2",
            "status": "started",
            "file_path": None,
            "error": None,
            "created_at": datetime.now(timezone.utc),
            "started_at": datetime.now(timezone.utc),
            "finished_at": None,
        }
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = _mock_pg_pool(mock_conn)

        async def fake_get_pool():
            return mock_pool

        monkeypatch.setattr("app.repositories.report_repo.get_pool", fake_get_pool)

        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        result = await repo.update_report_status("pg-job-2", ReportStatus.STARTED)
        assert result.status == ReportStatus.STARTED

    @pytest.mark.asyncio
    async def test_get_report_by_job_id_postgres_returns_none(
        self, monkeypatch, _mock_pg_pool
    ):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = _mock_pg_pool(mock_conn)

        async def fake_get_pool():
            return mock_pool

        monkeypatch.setattr("app.repositories.report_repo.get_pool", fake_get_pool)

        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        result = await repo.get_report_by_job_id("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_report_status_postgres_nonexistent(
        self, monkeypatch, _mock_pg_pool
    ):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = _mock_pg_pool(mock_conn)

        async def fake_get_pool():
            return mock_pool

        monkeypatch.setattr("app.repositories.report_repo.get_pool", fake_get_pool)

        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        result = await repo.update_report_status("nonexistent", ReportStatus.STARTED)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_report_by_job_id_postgres_found(
        self, monkeypatch, _mock_pg_pool
    ):
        mock_conn = AsyncMock()
        mock_row = {
            "report_id": 1,
            "job_id": "pg-job-found",
            "status": "started",
            "file_path": None,
            "error": None,
            "created_at": datetime.now(timezone.utc),
            "started_at": datetime.now(timezone.utc),
            "finished_at": None,
        }
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = _mock_pg_pool(mock_conn)

        async def fake_get_pool():
            return mock_pool

        monkeypatch.setattr("app.repositories.report_repo.get_pool", fake_get_pool)

        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        result = await repo.get_report_by_job_id("pg-job-found")
        assert result is not None
        assert result.job_id == "pg-job-found"
        assert result.status == ReportStatus.STARTED

    @pytest.mark.asyncio
    async def test_update_report_status_postgres_finished_with_file(
        self, monkeypatch, _mock_pg_pool
    ):
        mock_conn = AsyncMock()
        mock_row = {
            "report_id": 1,
            "job_id": "pg-job-fin",
            "status": "finished",
            "file_path": "/tmp/report.pdf",
            "error": None,
            "created_at": datetime.now(timezone.utc),
            "started_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
        }
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = _mock_pg_pool(mock_conn)

        async def fake_get_pool():
            return mock_pool

        monkeypatch.setattr("app.repositories.report_repo.get_pool", fake_get_pool)

        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        result = await repo.update_report_status(
            "pg-job-fin", ReportStatus.FINISHED, file_path="/tmp/report.pdf"
        )
        assert result is not None
        assert result.status == ReportStatus.FINISHED
        assert result.file_path == "/tmp/report.pdf"

    @pytest.mark.asyncio
    async def test_update_report_status_postgres_failed_with_error(
        self, monkeypatch, _mock_pg_pool
    ):
        mock_conn = AsyncMock()
        mock_row = {
            "report_id": 1,
            "job_id": "pg-job-fail",
            "status": "failed",
            "file_path": None,
            "error": "processing error",
            "created_at": datetime.now(timezone.utc),
            "started_at": None,
            "finished_at": datetime.now(timezone.utc),
        }
        mock_conn.fetchrow = AsyncMock(return_value=mock_row)
        mock_pool = _mock_pg_pool(mock_conn)

        async def fake_get_pool():
            return mock_pool

        monkeypatch.setattr("app.repositories.report_repo.get_pool", fake_get_pool)

        from app.repositories.report_repo import ReportRepository

        repo = ReportRepository()
        result = await repo.update_report_status(
            "pg-job-fail", ReportStatus.FAILED, error="processing error"
        )
        assert result is not None
        assert result.status == ReportStatus.FAILED
        assert result.error == "processing error"

import os

from fastapi.testclient import TestClient


class TestCreateReport:
    def test_post_report_returns_202(self, client: TestClient):
        response = client.post("/reports")
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_post_report_returns_job_id(self, client: TestClient):
        response = client.post("/reports")
        assert response.status_code == 202
        data = response.json()
        assert len(data["job_id"]) > 0


class TestGetReport:
    def test_unknown_report_returns_404(self, client: TestClient):
        response = client.get("/reports/unknown-id")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_get_report_returns_metadata(self, client: TestClient):
        create_resp = client.post("/reports")
        job_id = create_resp.json()["job_id"]

        response = client.get(f"/reports/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert "status" in data

    def test_get_report_includes_download_url_when_finished(
        self, client: TestClient, monkeypatch
    ):
        from datetime import datetime, timezone

        async def fake_get_report(self, job_id):
            from app.models.report import ReportResponse, ReportStatus

            return ReportResponse(
                report_id=1,
                job_id="finished-report",
                status=ReportStatus.FINISHED,
                file_path="/fake/path/generated_reports/report_finished-report.pdf",
                created_at=datetime.now(timezone.utc),
            )

        monkeypatch.setattr(
            "app.services.report_service.ReportRepository.get_report_by_job_id",
            fake_get_report,
        )

        response = client.get("/reports/finished-report")
        assert response.status_code == 200
        data = response.json()
        assert data["download_url"] is not None
        assert data["download_url"].startswith("/reports/files/")


class TestDownloadReport:
    def test_download_nonexistent_file_returns_404(self, client: TestClient):
        response = client.get("/reports/files/nonexistent.pdf")
        assert response.status_code == 404

    def test_download_invalid_extension_returns_400(self, client: TestClient):
        response = client.get("/reports/files/report.txt")
        assert response.status_code == 400

    def test_download_valid_filename_not_found_404(self, client: TestClient):
        response = client.get("/reports/files/valid_name_only.pdf")
        assert response.status_code == 404

    def test_download_path_traversal_rejected_400(self, client: TestClient):
        response = client.get("/reports/files/test..pdf")
        assert response.status_code == 400

    def test_download_successful_200(self, client: TestClient, tmp_path, monkeypatch):
        reports_dir = tmp_path / "generated_reports"
        reports_dir.mkdir()
        pdf_file = reports_dir / "report_test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")

        monkeypatch.setattr("app.routers.reports.REPORTS_DIR", str(reports_dir))

        response = client.get("/reports/files/report_test.pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"


class TestDownloadSecurityDirect:
    def test_filename_with_slash_rejected(self):
        from app.routers.reports import ALLOWED_EXTENSION

        filename = "../../etc/passwd"
        assert not filename.endswith(ALLOWED_EXTENSION)

    def test_filename_with_backslash_rejected(self):
        from app.routers.reports import ALLOWED_EXTENSION

        filename = "..\\..\\etc\\passwd"
        assert not filename.endswith(ALLOWED_EXTENSION)

    def test_filename_normalization_check(self):
        reports_dir = "generated_reports"
        filename = "../../etc/passwd"
        filepath = os.path.normpath(os.path.join(reports_dir, filename))
        assert not filepath.startswith(os.path.normpath(reports_dir))

    def test_absolute_path_normalization_check(self):
        reports_dir = "generated_reports"
        filename = "/absolute/path.pdf"
        filepath = os.path.normpath(os.path.join(reports_dir, filename))
        assert not filepath.startswith(os.path.normpath(reports_dir))

    def test_valid_filename_normalization_check(self):
        reports_dir = "generated_reports"
        filename = "report_test.pdf"
        filepath = os.path.normpath(os.path.join(reports_dir, filename))
        assert filepath.startswith(os.path.normpath(reports_dir))


class TestReportErrorResponses:
    def test_404_returns_json_error(self, client: TestClient):
        response = client.get("/reports/nonexistent")
        assert response.status_code == 404
        assert "detail" in response.json()

    def test_no_stack_trace_on_404(self, client: TestClient):
        response = client.get("/reports/nonexistent")
        assert "File" not in response.text

    def test_no_stack_trace_on_file_404(self, client: TestClient):
        response = client.get("/reports/files/missing.pdf")
        assert "File" not in response.text

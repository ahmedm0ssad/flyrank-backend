import os

from app.services.pdf_generator import REPORTS_DIR, generate_report


class TestPDFGenerator:
    def setup_method(self):
        if not os.path.exists(REPORTS_DIR):
            os.makedirs(REPORTS_DIR)

    def teardown_method(self):
        for f in os.listdir(REPORTS_DIR):
            os.remove(os.path.join(REPORTS_DIR, f))
        if os.path.exists(REPORTS_DIR):
            os.rmdir(REPORTS_DIR)

    def test_generate_report_creates_pdf_file(self):
        stats = {
            "total": 10,
            "done": 6,
            "not_done": 4,
            "completion_pct": 60.0,
            "recent_tasks": [
                {"id": 1, "title": "Task 1", "done": True},
                {"id": 2, "title": "Task 2", "done": False},
            ],
        }
        filepath = generate_report("test-job-1", stats, None, None)
        assert os.path.exists(filepath)
        assert filepath.endswith(".pdf")
        assert "report_test-job-1" in filepath

    def test_generate_report_returns_valid_path(self):
        stats = {
            "total": 5,
            "done": 3,
            "not_done": 2,
            "completion_pct": 60.0,
            "recent_tasks": [],
        }
        filepath = generate_report("test-job-2", stats, None, None)
        assert filepath.startswith(REPORTS_DIR)
        assert os.path.getsize(filepath) > 0

    def test_generate_report_with_all_data(self):
        stats = {
            "total": 20,
            "done": 15,
            "not_done": 5,
            "completion_pct": 75.0,
            "recent_tasks": [
                {"id": 1, "title": "Task A", "done": True},
                {"id": 2, "title": "Task B", "done": False},
            ],
        }
        books_stats = {
            "total": 50,
            "avg_price": 25.99,
            "categories": 10,
        }
        ai_stats = {
            "total": 30,
            "completed": 25,
            "failed": 5,
        }
        filepath = generate_report("test-job-3", stats, books_stats, ai_stats)
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 1000

    def test_generate_report_is_valid_pdf(self):
        stats = {
            "total": 3,
            "done": 1,
            "not_done": 2,
            "completion_pct": 33.3,
            "recent_tasks": [],
        }
        filepath = generate_report("test-job-4", stats, None, None)
        with open(filepath, "rb") as f:
            content = f.read()
        assert content[:5] == b"%PDF-"
        assert content.count(b"/Type") > 1

    def test_generate_report_pdf_signature(self):
        stats = {
            "total": 0,
            "done": 0,
            "not_done": 0,
            "completion_pct": 0.0,
            "recent_tasks": [],
        }
        filepath = generate_report("test-job-5", stats, None, None)
        with open(filepath, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"

    def test_generate_report_with_empty_stats(self):
        stats = {
            "total": 0,
            "done": 0,
            "not_done": 0,
            "completion_pct": 0.0,
            "recent_tasks": [],
        }
        filepath = generate_report("test-job-6", stats, None, None)
        assert os.path.exists(filepath)
        assert os.path.getsize(filepath) > 0

    def test_pdf_is_not_plain_text(self):
        stats = {
            "total": 5,
            "done": 2,
            "not_done": 3,
            "completion_pct": 40.0,
            "recent_tasks": [],
        }
        filepath = generate_report("test-job-7", stats, None, None)
        with open(filepath, "rb") as f:
            content = f.read()
        assert content[:5] == b"%PDF-"
        assert content.count(b"PDF") > 1

    def test_unique_job_id_produces_unique_filename(self):
        stats = {
            "total": 1,
            "done": 0,
            "not_done": 1,
            "completion_pct": 0.0,
            "recent_tasks": [],
        }
        fp1 = generate_report("unique-1", stats, None, None)
        fp2 = generate_report("unique-2", stats, None, None)
        assert fp1 != fp2
        assert "unique-1" in fp1
        assert "unique-2" in fp2

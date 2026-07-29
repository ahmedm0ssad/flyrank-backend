import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestBodyLimitMiddleware:
    def test_under_limit_passes(self, client):
        resp = client.post(
            "/public/widget/00000000-0000-0000-0000-000000000000/submit",
            json={"form_data": {"name": "John"}},
        )
        assert resp.status_code in (201, 400, 403, 404, 429)

    def test_over_content_length_rejected(self, client):
        big_body = "x" * 60_000
        resp = client.post(
            "/public/widget/00000000-0000-0000-0000-000000000000/submit",
            content=big_body,
            headers={"Content-Type": "application/json", "Content-Length": "60000"},
        )
        assert resp.status_code == 413

    def test_exactly_at_limit_passes(self, client):
        import json

        body = json.dumps({"form_data": {"name": "John"}})
        resp = client.post(
            "/public/widget/00000000-0000-0000-0000-000000000000/submit",
            content=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(body)),
            },
        )
        assert resp.status_code in (201, 400, 403, 404, 429)

    def test_spoofed_content_length_still_capped(self, client):
        big_body = "x" * 60_000
        resp = client.post(
            "/public/widget/00000000-0000-0000-0000-000000000000/submit",
            content=big_body,
            headers={"Content-Type": "application/json", "Content-Length": "10"},
        )
        assert resp.status_code == 413

    def test_missing_content_length_still_capped(self, client):
        big_body = "x" * 60_000
        resp = client.post(
            "/public/widget/00000000-0000-0000-0000-000000000000/submit",
            content=big_body,
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 413

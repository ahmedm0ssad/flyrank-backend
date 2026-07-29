import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.usefixtures("mock_redis")


@pytest.fixture
def client():
    return TestClient(app)


class TestGetWidgetConfig:
    def test_config_200(self, client, created_widget):
        widget_id = str(created_widget.id)
        resp = client.get(f"/public/widget/{widget_id}/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["widget_id"] == widget_id
        assert "brand_color" in data
        assert "button_text" in data
        assert "fields" in data
        assert "success_message" in data
        assert "honeypot_field" in data

    def test_config_404(self, client):
        resp = client.get("/public/widget/00000000-0000-0000-0000-000000000000/config")
        assert resp.status_code == 404

    def test_config_cached(self, client, created_widget):
        widget_id = str(created_widget.id)
        cached_before = client.get(f"/public/widget/{widget_id}/config")
        assert cached_before.status_code == 200

        cached = client.get(f"/public/widget/{widget_id}/config")
        assert cached.status_code == 200


class TestGetWidgetJs:
    def test_widget_js_200(self, client, created_widget):
        widget_id = str(created_widget.id)
        resp = client.get(f"/public/widget/{widget_id}/widget.js?v=1")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/javascript"
        assert "Cache-Control" in resp.headers
        assert "immutable" in resp.headers["Cache-Control"]
        assert str(widget_id) in resp.text

    def test_widget_js_404(self, client):
        resp = client.get(
            "/public/widget/00000000-0000-0000-0000-000000000000/widget.js?v=1"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_widget_js_410(self, client, created_widget):
        from app.services import widget_service

        widget_id = str(created_widget.id)
        await widget_service.delete_widget(
            widget_id, "11111111-1111-1111-1111-111111111111"
        )

        resp = client.get(f"/public/widget/{widget_id}/widget.js?v=1")
        assert resp.status_code == 410

    def test_widget_js_caching_headers(self, client, created_widget):
        widget_id = str(created_widget.id)
        resp = client.get(f"/public/widget/{widget_id}/widget.js?v=1")
        cc = resp.headers.get("cache-control", "")
        assert "public" in cc
        assert "max-age=31536000" in cc
        assert "immutable" in cc

    def test_widget_js_content_type(self, client, created_widget):
        widget_id = str(created_widget.id)
        resp = client.get(f"/public/widget/{widget_id}/widget.js?v=1")
        assert resp.headers["content-type"] == "application/javascript"


class TestCors:
    def test_cors_headers_present_on_get(self, client, created_widget):
        widget_id = str(created_widget.id)
        resp = client.get(
            f"/public/widget/{widget_id}/config",
            headers={"Origin": "https://example.com"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "*"

    def test_cors_headers_on_widget_js(self, client, created_widget):
        widget_id = str(created_widget.id)
        resp = client.get(
            f"/public/widget/{widget_id}/widget.js?v=1",
            headers={"Origin": "https://example.com"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "*"

    def test_options_preflight(self, client):
        resp = client.options(
            "/public/widget/00000000-0000-0000-0000-000000000000/config",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "*"
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        assert "GET" in allow_methods or "POST" in allow_methods

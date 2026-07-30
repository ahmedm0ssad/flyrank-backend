import pytest
from fastapi.testclient import TestClient

from app.main import app


class _FakeAsyncRedis:
    def __init__(self, sync_redis):
        self._sync = sync_redis

    async def get(self, key):
        return self._sync.get(key)

    async def setex(self, key, ttl, value):
        self._sync.setex(key, ttl, value)

    async def delete(self, key):
        self._sync._strings.pop(key, None)
        self._sync._data.pop(key, None)

    async def ping(self):
        return True

    def pipeline(self):
        return (
            self._sync.pipeline()
            if hasattr(self._sync, "pipeline")
            else _FakePipeline(self._sync)
        )

    async def expire(self, key, ttl):
        self._sync.expire(key, ttl)

    async def incr(self, key):
        val = int(self._sync._strings.get(key, 0)) + 1
        self._sync._strings[key] = str(val)
        return val


class _FakePipeline:
    def __init__(self, sync_redis):
        self._sync = sync_redis
        self._commands = []

    def incr(self, key):
        self._commands.append(("incr", key))
        return self

    async def execute(self):
        results = []
        for cmd, key in self._commands:
            if cmd == "incr":
                val = int(self._sync._strings.get(key, 0)) + 1
                self._sync._strings[key] = str(val)
                results.append(val)
        return results


@pytest.fixture(autouse=True)
def _reset_widget_repo():
    from app.services.widget_service import _get_repo

    repo = _get_repo()
    repo._widgets.clear()


@pytest.fixture
def fake_redis():
    from tests.conftest import _fake_redis

    return _fake_redis


@pytest.fixture
def fake_async_redis(fake_redis):
    return _FakeAsyncRedis(fake_redis)


@pytest.fixture
def mock_redis(monkeypatch, fake_async_redis):
    monkeypatch.setattr("app.main.get_redis", lambda: fake_async_redis)
    yield fake_async_redis


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_widget_data():
    return {
        "name": "Test Widget",
        "domain": "https://myshop.com",
        "config": {
            "brand_color": "#2563eb",
            "button_text": "Get a Quote",
            "fields": ["name", "email", "phone"],
            "success_message": "Thanks! We'll be in touch.",
        },
    }


@pytest.fixture
async def created_widget(sample_widget_data):
    from app.models.widget import WidgetCreate
    from app.services import widget_service

    data = WidgetCreate(**sample_widget_data)
    widget = await widget_service.create_widget(
        data, "11111111-1111-1111-1111-111111111111"
    )
    return widget


@pytest.fixture
async def created_wildcard_widget(sample_widget_data):
    from app.models.widget import WidgetCreate
    from app.services import widget_service

    data = WidgetCreate(
        name="Wildcard Widget",
        domain="https://*.myshop.com",
        config=sample_widget_data["config"],
    )
    widget = await widget_service.create_widget(
        data, "11111111-1111-1111-1111-111111111111"
    )
    return widget


@pytest.mark.usefixtures("mock_redis")
class TestCorsHeaders:
    def test_wildcard_cors_on_get_config(self, client, created_widget):
        resp = client.get(
            f"/public/widget/{created_widget.id}/config",
            headers={"Origin": "https://random-site.com"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "*"

    def test_wildcard_cors_on_get_widget_js(self, client, created_widget):
        resp = client.get(
            f"/public/widget/{created_widget.id}/widget.js?v=1",
            headers={"Origin": "https://random-site.com"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "*"

    def test_options_preflight_returns_cors(self, client):
        resp = client.options(
            "/public/widget/00000000-0000-0000-0000-000000000000/config",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "*"

    def test_cors_on_submit_success(self, client, created_widget):
        widget_id = str(created_widget.id)
        resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={"form_data": {"name": "John"}},
            headers={"Origin": "https://myshop.com"},
        )
        assert resp.status_code == 201
        assert resp.headers.get("access-control-allow-origin") == "*"

    def test_preflight_headers_include_allow_headers_and_max_age(self, client):
        resp = client.options(
            "/public/widget/00000000-0000-0000-0000-000000000000/config",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "*"
        allow_headers = resp.headers.get("access-control-allow-headers", "")
        assert "Content-Type" in allow_headers
        max_age = resp.headers.get("access-control-max-age", "")
        assert max_age != ""
        assert int(max_age) > 0

    def test_preflight_with_disallowed_method_returns_400(self, client):
        resp = client.options(
            "/public/widget/00000000-0000-0000-0000-000000000000/config",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "PUT",
            },
        )
        assert resp.status_code == 400


@pytest.mark.usefixtures("mock_redis")
class TestOriginValidationViaSubmit:
    @pytest.mark.asyncio
    async def test_origin_exact_match_accepted(self, created_widget):
        from app.models.lead import LeadSubmit
        from app.services.lead_service import submit_lead

        class FakeRequest:
            client = type("obj", (object,), {"host": "1.2.3.4"})()
            headers = {
                "origin": "https://myshop.com",
                "user-agent": "test",
                "referer": "",
            }

        body = LeadSubmit(form_data={"name": "John", "email": "john@test.com"})
        lead, was_dedup = await submit_lead(str(created_widget.id), body, FakeRequest())
        assert lead is not None
        assert was_dedup is False

    @pytest.mark.asyncio
    async def test_subdomain_suffix_bypass_rejected(self, created_widget):
        from fastapi import HTTPException

        from app.models.lead import LeadSubmit
        from app.services.lead_service import submit_lead

        class FakeRequest:
            client = type("obj", (object,), {"host": "1.2.3.4"})()
            headers = {
                "origin": "https://myshop.com.evil.com",
                "user-agent": "test",
                "referer": "",
            }

        body = LeadSubmit(form_data={"name": "John"})
        with pytest.raises(HTTPException) as exc:
            await submit_lead(str(created_widget.id), body, FakeRequest())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_wildcard_matches_subdomain(self, created_wildcard_widget):
        from app.models.lead import LeadSubmit
        from app.services.lead_service import submit_lead

        class FakeRequest:
            client = type("obj", (object,), {"host": "1.2.3.4"})()
            headers = {
                "origin": "https://shop.myshop.com",
                "user-agent": "test",
                "referer": "",
            }

        body = LeadSubmit(form_data={"name": "John"})
        lead, was_dedup = await submit_lead(
            str(created_wildcard_widget.id), body, FakeRequest()
        )
        assert lead is not None

    @pytest.mark.asyncio
    async def test_wildcard_matches_bare_domain(self, created_wildcard_widget):
        from app.models.lead import LeadSubmit
        from app.services.lead_service import submit_lead

        class FakeRequest:
            client = type("obj", (object,), {"host": "1.2.3.4"})()
            headers = {
                "origin": "https://myshop.com",
                "user-agent": "test",
                "referer": "",
            }

        body = LeadSubmit(form_data={"name": "John"})
        lead, was_dedup = await submit_lead(
            str(created_wildcard_widget.id), body, FakeRequest()
        )
        assert lead is not None

    @pytest.mark.asyncio
    async def test_wildcard_rejects_unrelated(self, created_wildcard_widget):
        from fastapi import HTTPException

        from app.models.lead import LeadSubmit
        from app.services.lead_service import submit_lead

        class FakeRequest:
            client = type("obj", (object,), {"host": "1.2.3.4"})()
            headers = {
                "origin": "https://evil.com",
                "user-agent": "test",
                "referer": "",
            }

        body = LeadSubmit(form_data={"name": "John"})
        with pytest.raises(HTTPException) as exc:
            await submit_lead(str(created_wildcard_widget.id), body, FakeRequest())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_missing_origin_rejected_on_post(self, created_widget):
        from fastapi import HTTPException

        from app.models.lead import LeadSubmit
        from app.services.lead_service import submit_lead

        class FakeRequest:
            client = type("obj", (object,), {"host": "1.2.3.4"})()
            headers = {"user-agent": "test"}

        body = LeadSubmit(form_data={"name": "John"})
        with pytest.raises(HTTPException) as exc:
            await submit_lead(str(created_widget.id), body, FakeRequest())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_origin_rejected_on_post(self, created_widget):
        from fastapi import HTTPException

        from app.models.lead import LeadSubmit
        from app.services.lead_service import submit_lead

        class FakeRequest:
            client = type("obj", (object,), {"host": "1.2.3.4"})()
            headers = {"origin": "", "user-agent": "test"}

        body = LeadSubmit(form_data={"name": "John"})
        with pytest.raises(HTTPException) as exc:
            await submit_lead(str(created_widget.id), body, FakeRequest())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_malformed_origin_rejected(self, created_widget):
        from fastapi import HTTPException

        from app.models.lead import LeadSubmit
        from app.services.lead_service import submit_lead

        class FakeRequest:
            client = type("obj", (object,), {"host": "1.2.3.4"})()
            headers = {"origin": "not-a-valid-url", "user-agent": "test", "referer": ""}

        body = LeadSubmit(form_data={"name": "John"})
        with pytest.raises(HTTPException) as exc:
            await submit_lead(str(created_widget.id), body, FakeRequest())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_punycode_origin_mismatch(self, created_widget):
        from app.dependencies.embed import validate_origin

        class FakeRequest:
            headers = {"origin": "https://xn--mgba3a4e16a.com"}

        result = await validate_origin(FakeRequest(), created_widget.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_idn_origin_normalization(self, created_widget):
        from app.dependencies.embed import _normalize_host, validate_origin

        normalized = _normalize_host("пример.рф")
        assert normalized == "xn--e1afmkfd.xn--p1ai"

        class FakeRequest:
            headers = {"origin": "https://xn--e1afmkfd.xn--p1ai"}

        result = await validate_origin(FakeRequest(), created_widget.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_origin_with_port_stripped(self, created_widget):
        from app.dependencies.embed import validate_origin

        class FakeRequest:
            headers = {"origin": "https://myshop.com:8443"}

        result = await validate_origin(FakeRequest(), created_widget.id)
        assert result is True

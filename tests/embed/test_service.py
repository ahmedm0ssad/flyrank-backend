import pytest

from app.dependencies.embed import validate_origin
from app.services.embed_service import generate_snippet, get_widget_config
from app.models.widget import WidgetCreate

pytestmark = pytest.mark.usefixtures("mock_redis")


@pytest.mark.asyncio
async def test_config_caching(created_widget, fake_async_redis):
    widget_id = str(created_widget.id)
    cache_key = f"widget:config:{widget_id}"

    cache_before = await fake_async_redis.get(cache_key)
    assert cache_before is None

    config = await get_widget_config(widget_id)
    assert config is not None
    assert config["widget_id"] == widget_id

    cached = await fake_async_redis.get(cache_key)
    assert cached is not None


@pytest.mark.asyncio
async def test_config_missing():
    config = await get_widget_config("00000000-0000-0000-0000-000000000000")
    assert config is None


@pytest.mark.asyncio
async def test_snippet_generation_with_version_param():
    snippet = await generate_snippet("abc-123", 5)
    assert "abc-123" in snippet
    assert "v=5" in snippet
    assert snippet.startswith("<script ")


@pytest.mark.asyncio
async def test_origin_exact_match():
    from app.services import widget_service

    data = WidgetCreate(
        name="Test",
        domain="https://myshop.com",
        config={"brand_color": "#000000", "button_text": "Go", "fields": ["email"], "success_message": "OK"},
    )
    widget = await widget_service.create_widget(data, "22222222-2222-2222-2222-222222222222")

    class FakeRequest:
        headers = {"origin": "https://myshop.com"}

    result = await validate_origin(FakeRequest(), widget.id)
    assert result is True, "exact origin match should pass"


@pytest.mark.asyncio
async def test_origin_wildcard_match():
    from app.services import widget_service

    data = WidgetCreate(
        name="Test",
        domain="https://*.myshop.com",
        config={"brand_color": "#000000", "button_text": "Go", "fields": ["email"], "success_message": "OK"},
    )
    widget = await widget_service.create_widget(data, "22222222-2222-2222-2222-222222222222")

    class FakeRequest1:
        headers = {"origin": "https://foo.myshop.com"}

    result1 = await validate_origin(FakeRequest1(), widget.id)
    assert result1 is True, "subdomain should match wildcard"

    class FakeRequest2:
        headers = {"origin": "https://myshop.com"}

    result2 = await validate_origin(FakeRequest2(), widget.id)
    assert result2 is True, "bare domain should match *.myshop.com"


@pytest.mark.asyncio
async def test_origin_subdomain_suffix_bypass_rejected():
    allowed = "https://myshop.com"
    bypass_attempt = "https://myshop.com.evil.com"

    from app.services import widget_service

    data = WidgetCreate(
        name="Test",
        domain=allowed,
        config={"brand_color": "#000000", "button_text": "Go", "fields": ["email"], "success_message": "OK"},
    )
    widget = await widget_service.create_widget(data, "22222222-2222-2222-2222-222222222222")

    class FakeRequest:
        headers = {"origin": bypass_attempt}

    result = await validate_origin(FakeRequest(), widget.id)
    assert result is False, (
        f"bypass attempt {bypass_attempt!r} against domain {allowed!r} "
        f"must be rejected; prefix-match bug would let this pass"
    )


@pytest.mark.asyncio
async def test_origin_missing_rejected():
    from app.services import widget_service

    data = WidgetCreate(
        name="Test",
        domain="https://myshop.com",
        config={"brand_color": "#000000", "button_text": "Go", "fields": ["email"], "success_message": "OK"},
    )
    widget = await widget_service.create_widget(data, "22222222-2222-2222-2222-222222222222")

    class FakeRequest:
        headers = {}

    result = await validate_origin(FakeRequest(), widget.id)
    assert result is False, "missing origin should be rejected"


@pytest.mark.asyncio
async def test_origin_wildcard_no_match_rejected():
    from app.services import widget_service

    data = WidgetCreate(
        name="Test",
        domain="https://*.myshop.com",
        config={"brand_color": "#000000", "button_text": "Go", "fields": ["email"], "success_message": "OK"},
    )
    widget = await widget_service.create_widget(data, "22222222-2222-2222-2222-222222222222")

    class FakeRequest:
        headers = {"origin": "https://evil.com"}

    result = await validate_origin(FakeRequest(), widget.id)
    assert result is False, "unrelated domain should be rejected"

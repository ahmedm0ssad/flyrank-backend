from app.services.widget_js import generate_script_tag, render_widget_js


class TestRenderWidgetJs:
    def test_js_generation_returns_string(self):
        js = render_widget_js("test-id", {"brand_color": "#000000"}, 1)
        assert isinstance(js, str)
        assert len(js) > 100

    def test_js_contains_widget_id(self):
        js = render_widget_js("widget-123", {}, 1)
        assert "widget-123" in js

    def test_js_references_config_at_runtime(self):
        js = render_widget_js("widget-1", {}, 1)
        assert "config.brand_color" in js
        assert "config.button_text" in js
        assert "config.honeypot_field" in js

    def test_uses_self_invoking_function(self):
        js = render_widget_js("test-id", {}, 1)
        assert "(function()" in js
        assert "})()" in js or "})();" in js

    def test_client_side_config_url_constructed_at_runtime(self):
        js = render_widget_js("widget-1", {}, 1)
        assert "configUrl" in js
        assert "/public/widget/" in js


class TestGenerateScriptTag:
    def test_basic_script_tag(self):
        tag = generate_script_tag("abc-123", 1)
        assert 'src="/public/widget/abc-123/widget.js?v=1"' in tag
        assert 'data-widget-id="abc-123"' in tag
        assert "defer" in tag

    def test_versioned_url_changes_with_version(self):
        tag_v1 = generate_script_tag("wid", 1)
        tag_v2 = generate_script_tag("wid", 2)
        assert "v=1" in tag_v1
        assert "v=2" in tag_v2
        assert tag_v1 != tag_v2

    def test_custom_base_url(self):
        tag = generate_script_tag("wid", 3, base_url="https://api.example.com")
        assert "https://api.example.com/public/widget/wid/widget.js?v=3" in tag

    def test_script_tag_format(self):
        tag = generate_script_tag("wid-99", 5)
        assert tag.startswith("<script ")
        assert tag.endswith("></script>")

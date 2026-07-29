from app.models.lead import _sanitize


class TestSanitize:
    def test_escapes_html_tags(self):
        assert (
            _sanitize("<script>alert('xss')</script>")
            == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
        )

    def test_escapes_quotes(self):
        assert _sanitize('say "hello"') == "say &quot;hello&quot;"

    def test_strips_whitespace(self):
        assert _sanitize("  hello  ") == "hello"

    def test_ampersand_escaped(self):
        assert _sanitize("a & b") == "a &amp; b"

    def test_plain_text_unchanged(self):
        assert _sanitize("John Doe") == "John Doe"

    def test_empty_string_returns_empty(self):
        assert _sanitize("") == ""

    def test_single_quote_escaped(self):
        assert _sanitize("it's") == "it&#x27;s"

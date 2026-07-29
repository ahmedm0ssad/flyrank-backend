from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import Request

from app.dependencies.embed import _normalize_host, _parse_origin_host, validate_origin


class TestNormalizeHost:
    def test_empty_string_returns_empty(self):
        assert _normalize_host("") == ""

    def test_ascii_host_unchanged(self):
        assert _normalize_host("example.com") == "example.com"

    def test_idna_encoded(self):
        result = _normalize_host("münchen.de")
        assert result == "xn--mnchen-3ya.de"

    def test_unicode_error_returns_original(self):
        assert _normalize_host("\udce0") == "\udce0"


class TestParseOriginHost:
    def test_empty_origin_returns_empty(self):
        assert _parse_origin_host("") == ""

    def test_full_url_returns_hostname(self):
        assert _parse_origin_host("https://www.example.com/path") == "www.example.com"

    def test_strips_port(self):
        assert _parse_origin_host("http://example.com:8080") == "example.com"

    def test_idna_punycode_origin(self):
        result = _parse_origin_host("https://münchen.de")
        assert result == "xn--mnchen-3ya.de"


class TestValidateOrigin:
    @pytest.mark.asyncio
    async def test_valid_origin_exact_match(self):
        request = Request(
            {
                "type": "http",
                "headers": [
                    (b"origin", b"https://myshop.com"),
                ],
            }
        )
        with patch(
            "app.dependencies.embed.get_raw_widget",
            AsyncMock(return_value={"domain": "https://myshop.com", "active": True}),
        ):
            result = await validate_origin(
                request, UUID("00000000-0000-0000-0000-000000000001")
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_wildcard_domain_matches_subdomain(self):
        request = Request(
            {
                "type": "http",
                "headers": [
                    (b"origin", b"https://app.myshop.com"),
                ],
            }
        )
        with patch(
            "app.dependencies.embed.get_raw_widget",
            AsyncMock(return_value={"domain": "https://*.myshop.com", "active": True}),
        ):
            result = await validate_origin(
                request, UUID("00000000-0000-0000-0000-000000000001")
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_wildcard_domain_rejects_unrelated(self):
        request = Request(
            {
                "type": "http",
                "headers": [
                    (b"origin", b"https://evil.com"),
                ],
            }
        )
        with patch(
            "app.dependencies.embed.get_raw_widget",
            AsyncMock(return_value={"domain": "*.myshop.com", "active": True}),
        ):
            result = await validate_origin(
                request, UUID("00000000-0000-0000-0000-000000000001")
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_empty_origin_rejected(self):
        request = Request({"type": "http", "headers": []})
        result = await validate_origin(
            request, UUID("00000000-0000-0000-0000-000000000001")
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_inactive_widget_rejected(self):
        request = Request(
            {
                "type": "http",
                "headers": [
                    (b"origin", b"https://myshop.com"),
                ],
            }
        )
        with patch(
            "app.dependencies.embed.get_raw_widget",
            AsyncMock(return_value={"domain": "https://myshop.com", "active": False}),
        ):
            result = await validate_origin(
                request, UUID("00000000-0000-0000-0000-000000000001")
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_nonexistent_widget_rejected(self):
        request = Request(
            {
                "type": "http",
                "headers": [
                    (b"origin", b"https://myshop.com"),
                ],
            }
        )
        with patch(
            "app.dependencies.embed.get_raw_widget",
            AsyncMock(return_value=None),
        ):
            result = await validate_origin(
                request, UUID("00000000-0000-0000-0000-000000000001")
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_referer_used_when_no_origin(self):
        request = Request(
            {
                "type": "http",
                "headers": [
                    (b"referer", b"https://myshop.com/contact"),
                ],
            }
        )
        with patch(
            "app.dependencies.embed.get_raw_widget",
            AsyncMock(return_value={"domain": "https://myshop.com", "active": True}),
        ):
            result = await validate_origin(
                request, UUID("00000000-0000-0000-0000-000000000001")
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_origin_mismatch_rejected(self):
        request = Request(
            {
                "type": "http",
                "headers": [
                    (b"origin", b"https://other.com"),
                ],
            }
        )
        with patch(
            "app.dependencies.embed.get_raw_widget",
            AsyncMock(return_value={"domain": "https://myshop.com", "active": True}),
        ):
            result = await validate_origin(
                request, UUID("00000000-0000-0000-0000-000000000001")
            )
            assert result is False

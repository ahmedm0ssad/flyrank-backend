"""Tests for app.dependencies.embed — uncovered lines 17-18, 23, 37, 48-51.

These are placed in tests/repositories/ since the CI path includes
that directory (tests/dependencies/ is not in CI).
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import Request


class TestNormalizeHost:
    def test_returns_empty_when_empty(self):
        from app.dependencies.embed import _normalize_host

        assert _normalize_host("") == ""

    def test_returns_hostname_on_unicode_error(self):
        from app.dependencies.embed import _normalize_host

        result = _normalize_host(
            "a" * 64
        )  # label > 63 chars triggers UnicodeEncodeError
        assert result == "a" * 64


class TestParseOriginHost:
    def test_returns_empty_when_empty(self):
        from app.dependencies.embed import _parse_origin_host

        assert _parse_origin_host("") == ""

    def test_parses_valid_origin(self):
        from app.dependencies.embed import _parse_origin_host

        assert _parse_origin_host("https://example.com") == "example.com"


class TestValidateOrigin:
    @pytest.mark.asyncio
    async def test_returns_false_when_raw_widget_none(self, monkeypatch):
        monkeypatch.setattr(
            "app.dependencies.embed.get_raw_widget", AsyncMock(return_value=None)
        )
        from uuid import UUID

        from app.dependencies.embed import validate_origin

        request = AsyncMock(spec=Request)
        request.headers.get.return_value = "https://example.com"
        result = await validate_origin(request, UUID(int=1))
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_widget_inactive(self, monkeypatch):
        monkeypatch.setattr(
            "app.dependencies.embed.get_raw_widget",
            AsyncMock(return_value={"active": False}),
        )
        from uuid import UUID

        from app.dependencies.embed import validate_origin

        request = AsyncMock(spec=Request)
        request.headers.get.return_value = "https://example.com"
        result = await validate_origin(request, UUID(int=1))
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_allowed_domain_unparseable(self, monkeypatch):
        monkeypatch.setattr(
            "app.dependencies.embed.get_raw_widget",
            AsyncMock(return_value={"active": True, "domain": ""}),
        )
        from uuid import UUID

        from app.dependencies.embed import validate_origin

        request = AsyncMock(spec=Request)
        request.headers.get.return_value = "https://example.com"
        result = await validate_origin(request, UUID(int=1))
        assert result is False

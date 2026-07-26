import asyncio
from unittest.mock import MagicMock

import pytest

from app.services import geo_service


async def _ipapi_result(ip):
    return {
        "country": "United States",
        "city": "Mountain View",
        "region": "California",
        "isp": "Google LLC",
        "provider": "ipapi",
    }


async def _ipinfo_result(ip):
    return {
        "country": "US",
        "city": "Mountain View",
        "region": "California",
        "isp": "AS15169 Google LLC",
        "provider": "ipinfo",
    }


async def _ipapi_com_result(ip):
    return {
        "country": "United States",
        "city": "Mountain View",
        "region": "California",
        "isp": "Google LLC",
        "provider": "ip-api",
    }


async def _none_result(ip):
    return None


class TestGeoEnrich:
    def test_provider_1_ipapi_success(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.geo_service.get_cached_geo", lambda ip: None
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi", _ipapi_result
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipinfo", _none_result
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi_com", _none_result
        )
        monkeypatch.setattr(
            "app.services.geo_service.set_cached_geo", MagicMock()
        )

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert result["provider"] == "ipapi"
        assert result["country"] == "United States"

    def test_fallback_to_ipinfo_when_ipapi_fails(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.geo_service.get_cached_geo", lambda ip: None
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi", _none_result
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipinfo", _ipinfo_result
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi_com", _none_result
        )
        monkeypatch.setattr(
            "app.services.geo_service.set_cached_geo", MagicMock()
        )

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert result["provider"] == "ipinfo"

    def test_fallback_to_ipapi_com_when_first_two_fail(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.geo_service.get_cached_geo", lambda ip: None
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi", _none_result
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipinfo", _none_result
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi_com", _ipapi_com_result
        )
        monkeypatch.setattr(
            "app.services.geo_service.set_cached_geo", MagicMock()
        )

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert result["provider"] == "ip-api"

    def test_all_providers_fail_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.geo_service.get_cached_geo", lambda ip: None
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi", _none_result
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipinfo", _none_result
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi_com", _none_result
        )
        monkeypatch.setattr(
            "app.services.geo_service.set_cached_geo", MagicMock()
        )

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is None

    def test_cache_hit_skips_all_providers(self, monkeypatch):
        cached = {
            "country": "United States",
            "city": "Mountain View",
            "region": "California",
            "isp": "Google LLC",
            "provider": "ipapi",
        }
        monkeypatch.setattr(
            "app.services.geo_service.get_cached_geo", lambda ip: cached
        )

        call_count = 0

        async def never_called(ip):
            nonlocal call_count
            call_count += 1
            return None

        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi", never_called
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipinfo", never_called
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi_com", never_called
        )

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert result["provider"] == "ipapi"
        assert call_count == 0

    def test_empty_ip_returns_none(self, monkeypatch):
        result = geo_service.geo_enrich("")
        assert result is None

        result = geo_service.geo_enrich("unknown")
        assert result is None

        result = geo_service.geo_enrich("127.0.0.1")
        assert result is None

        result = geo_service.geo_enrich(None)
        assert result is None

    def test_timeout_on_first_provider_falls_through(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.geo_service.get_cached_geo", lambda ip: None
        )

        async def timeout_ipapi(ip):
            raise asyncio.TimeoutError()

        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi", timeout_ipapi
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipinfo", _ipinfo_result
        )
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi_com", _none_result
        )
        monkeypatch.setattr(
            "app.services.geo_service.set_cached_geo", MagicMock()
        )

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert result["provider"] == "ipinfo"

    def test_provider_order_is_correct(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.geo_service.get_cached_geo", lambda ip: None
        )

        call_order = []

        async def first(ip):
            call_order.append("ipapi")
            return None

        async def second(ip):
            call_order.append("ipinfo")
            return await _ipinfo_result(ip)

        async def third(ip):
            call_order.append("ip-api")
            return None

        monkeypatch.setattr("app.services.geo_service._call_ipapi", first)
        monkeypatch.setattr("app.services.geo_service._call_ipinfo", second)
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi_com", third
        )
        monkeypatch.setattr(
            "app.services.geo_service.set_cached_geo", MagicMock()
        )

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert call_order == ["ipapi", "ipinfo"]

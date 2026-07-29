import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services import geo_service


class TestGetCacheKey:
    def test_returns_prefixed_key(self):
        assert geo_service._get_cache_key("8.8.8.8") == "geo:ip:8.8.8.8"


class TestGetCachedGeo:
    def test_returns_parsed_data_when_found(self):
        cached = '{"country": "US", "city": "NYC"}'
        fake_conn = MagicMock()
        fake_conn.get.return_value = cached
        with patch("app.services.geo_service.get_connection", return_value=fake_conn):
            result = geo_service.get_cached_geo("8.8.8.8")
            assert result == {"country": "US", "city": "NYC"}

    def test_returns_none_when_not_found(self):
        fake_conn = MagicMock()
        fake_conn.get.return_value = None
        with patch("app.services.geo_service.get_connection", return_value=fake_conn):
            result = geo_service.get_cached_geo("8.8.8.8")
            assert result is None

    def test_returns_none_on_json_error(self):
        fake_conn = MagicMock()
        fake_conn.get.return_value = "not-json"
        with patch("app.services.geo_service.get_connection", return_value=fake_conn):
            result = geo_service.get_cached_geo("8.8.8.8")
            assert result is None

    def test_returns_none_on_stale_malformed_json(self):
        fake_conn = MagicMock()
        fake_conn.get.return_value = "{broken: json,"
        with patch("app.services.geo_service.get_connection", return_value=fake_conn):
            result = geo_service.get_cached_geo("8.8.8.8")
            assert result is None


class TestSetCachedGeo:
    def test_sets_data_with_ttl(self):
        fake_conn = MagicMock()
        with patch("app.services.geo_service.get_connection", return_value=fake_conn):
            geo_service.set_cached_geo("8.8.8.8", {"country": "US"})
            fake_conn.setex.assert_called_once()
            args = fake_conn.setex.call_args[0]
            assert args[0] == "geo:ip:8.8.8.8"
            assert args[1] == geo_service.GEO_CACHE_TTL


class TestCallIpapi:
    @pytest.mark.asyncio
    async def test_returns_parsed_data_on_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "country_name": "United States",
                "city": "Mountain View",
                "region": "California",
                "org": "Google LLC",
            }
        )
        mock_client = MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await geo_service._call_ipapi("8.8.8.8")
            assert result is not None
            assert result["country"] == "United States"
            assert result["provider"] == "ipapi"

    @pytest.mark.asyncio
    async def test_returns_none_on_error_response(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={"error": True, "reason": "rate limited"}
        )
        mock_client = MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await geo_service._call_ipapi("8.8.8.8")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await geo_service._call_ipapi("8.8.8.8")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        from httpx import TimeoutException

        mock_client = MagicMock()
        mock_client.__aenter__.return_value.get.side_effect = TimeoutException(
            "timeout"
        )
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await geo_service._call_ipapi("8.8.8.8")
            assert result is None


class TestCallIpinfo:
    @pytest.mark.asyncio
    async def test_returns_parsed_data_on_success(self):
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("IPINFO_TOKEN", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "country": "US",
                "city": "Mountain View",
                "region": "California",
                "org": "AS15169 Google LLC",
            }
        )
        mock_client = MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await geo_service._call_ipinfo("8.8.8.8")
            assert result is not None
            assert result["country"] == "US"
            assert result["provider"] == "ipinfo"

    @pytest.mark.asyncio
    async def test_skips_when_no_token(self):
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("IPINFO_TOKEN", "")

        mock_client = MagicMock()
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await geo_service._call_ipinfo("8.8.8.8")
            assert result is None
            mock_client.__aenter__.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("IPINFO_TOKEN", "test-token")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json = MagicMock()
        mock_client = MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await geo_service._call_ipinfo("8.8.8.8")
            assert result is None


class TestCallIpapiCom:
    @pytest.mark.asyncio
    async def test_returns_parsed_data_on_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={
                "status": "success",
                "country": "United States",
                "city": "Mountain View",
                "regionName": "California",
                "isp": "Google LLC",
            }
        )
        mock_client = MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await geo_service._call_ipapi_com("8.8.8.8")
            assert result is not None
            assert result["country"] == "United States"
            assert result["provider"] == "ip-api"

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json = MagicMock(
            return_value={"status": "fail", "message": "invalid query"}
        )
        mock_client = MagicMock()
        mock_client.__aenter__.return_value.get.return_value = mock_response
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await geo_service._call_ipapi_com("8.8.8.8")
            assert result is None


class TestCallWithTimeout:
    @pytest.mark.asyncio
    async def test_returns_coro_result(self):
        async def success(ip):
            return {"ip": ip}

        result = await geo_service._call_with_timeout(
            success("1.2.3.4"), "1.2.3.4", "test"
        )
        assert result == {"ip": "1.2.3.4"}

    @pytest.mark.asyncio
    async def test_returns_none_on_timeout(self):
        async def slow(ip):
            await asyncio.sleep(10)
            return {"ip": ip}

        coro = slow("1.2.3.4")
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError):
            result = await geo_service._call_with_timeout(coro, "1.2.3.4", "test")
            assert result is None
        coro.close()


class TestGeoEnrich:
    def test_private_ip_returns_none(self):
        result = geo_service.geo_enrich("127.0.0.1")
        assert result is None

        result = geo_service.geo_enrich("::1")
        assert result is None

        result = geo_service.geo_enrich("localhost")
        assert result is None

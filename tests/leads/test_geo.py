import asyncio
from unittest.mock import MagicMock

import pytest

from app.services import geo_service, lead_service


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
        monkeypatch.setattr("app.services.geo_service.get_cached_geo", lambda ip: None)
        monkeypatch.setattr("app.services.geo_service._call_ipapi", _ipapi_result)
        monkeypatch.setattr("app.services.geo_service._call_ipinfo", _none_result)
        monkeypatch.setattr("app.services.geo_service._call_ipapi_com", _none_result)
        monkeypatch.setattr("app.services.geo_service.set_cached_geo", MagicMock())

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert result["provider"] == "ipapi"
        assert result["country"] == "United States"

    def test_fallback_to_ipinfo_when_ipapi_fails(self, monkeypatch):
        monkeypatch.setattr("app.services.geo_service.get_cached_geo", lambda ip: None)
        monkeypatch.setattr("app.services.geo_service._call_ipapi", _none_result)
        monkeypatch.setattr("app.services.geo_service._call_ipinfo", _ipinfo_result)
        monkeypatch.setattr("app.services.geo_service._call_ipapi_com", _none_result)
        monkeypatch.setattr("app.services.geo_service.set_cached_geo", MagicMock())

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert result["provider"] == "ipinfo"

    def test_fallback_to_ipapi_com_when_first_two_fail(self, monkeypatch):
        monkeypatch.setattr("app.services.geo_service.get_cached_geo", lambda ip: None)
        monkeypatch.setattr("app.services.geo_service._call_ipapi", _none_result)
        monkeypatch.setattr("app.services.geo_service._call_ipinfo", _none_result)
        monkeypatch.setattr(
            "app.services.geo_service._call_ipapi_com", _ipapi_com_result
        )
        monkeypatch.setattr("app.services.geo_service.set_cached_geo", MagicMock())

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert result["provider"] == "ip-api"

    def test_all_providers_fail_returns_none(self, monkeypatch):
        monkeypatch.setattr("app.services.geo_service.get_cached_geo", lambda ip: None)
        monkeypatch.setattr("app.services.geo_service._call_ipapi", _none_result)
        monkeypatch.setattr("app.services.geo_service._call_ipinfo", _none_result)
        monkeypatch.setattr("app.services.geo_service._call_ipapi_com", _none_result)
        monkeypatch.setattr("app.services.geo_service.set_cached_geo", MagicMock())

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

        monkeypatch.setattr("app.services.geo_service._call_ipapi", never_called)
        monkeypatch.setattr("app.services.geo_service._call_ipinfo", never_called)
        monkeypatch.setattr("app.services.geo_service._call_ipapi_com", never_called)

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
        monkeypatch.setattr("app.services.geo_service.get_cached_geo", lambda ip: None)

        async def timeout_ipapi(ip):
            raise asyncio.TimeoutError()

        monkeypatch.setattr("app.services.geo_service._call_ipapi", timeout_ipapi)
        monkeypatch.setattr("app.services.geo_service._call_ipinfo", _ipinfo_result)
        monkeypatch.setattr("app.services.geo_service._call_ipapi_com", _none_result)
        monkeypatch.setattr("app.services.geo_service.set_cached_geo", MagicMock())

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert result["provider"] == "ipinfo"

    def test_provider_response_parsing(self, monkeypatch):
        monkeypatch.setattr("app.services.geo_service.get_cached_geo", lambda ip: None)

        async def mock_ipapi(ip):
            return {
                "country": "United States",
                "city": "Mountain View",
                "region": "California",
                "isp": "Google LLC",
                "provider": "ipapi",
            }

        monkeypatch.setattr("app.services.geo_service._call_ipapi", mock_ipapi)
        monkeypatch.setattr("app.services.geo_service._call_ipinfo", _none_result)
        monkeypatch.setattr("app.services.geo_service._call_ipapi_com", _none_result)
        monkeypatch.setattr("app.services.geo_service.set_cached_geo", MagicMock())

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert result["country"] == "United States"
        assert result["city"] == "Mountain View"
        assert result["region"] == "California"
        assert result["isp"] == "Google LLC"
        assert result["provider"] == "ipapi"

    def test_provider_order_is_correct(self, monkeypatch):
        monkeypatch.setattr("app.services.geo_service.get_cached_geo", lambda ip: None)

        call_order = []

        async def first(ip):
            call_order.append("ipapi")

        async def second(ip):
            call_order.append("ipinfo")
            return await _ipinfo_result(ip)

        async def third(ip):
            call_order.append("ip-api")

        monkeypatch.setattr("app.services.geo_service._call_ipapi", first)
        monkeypatch.setattr("app.services.geo_service._call_ipinfo", second)
        monkeypatch.setattr("app.services.geo_service._call_ipapi_com", third)
        monkeypatch.setattr("app.services.geo_service.set_cached_geo", MagicMock())

        result = geo_service.geo_enrich("8.8.8.8")
        assert result is not None
        assert call_order == ["ipapi", "ipinfo"]


class TestEnrichmentFailureFlow:
    def test_submit_201_when_enrichment_fails(
        self, client, created_widget, monkeypatch
    ):
        widget_id = str(created_widget.id)
        resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={"form_data": {"name": "John", "email": "john@test.com"}},
            headers={"Origin": "https://myshop.com"},
        )
        assert resp.status_code == 201
        lead_id = resp.json()["lead_id"]

        repo = lead_service._get_or_create_repo()
        monkeypatch.setattr("app.services.lead_worker.LeadRepository", lambda: repo)

        mock_job = MagicMock()
        mock_job.id = "test-enrich-fail"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0
        monkeypatch.setattr(
            "app.services.lead_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.lead_worker.update_enrichment_job", MagicMock()
        )
        monkeypatch.setattr("app.services.lead_worker.send_alert", MagicMock())
        monkeypatch.setattr("app.services.lead_worker.logger", MagicMock())
        monkeypatch.setattr("app.services.lead_worker.geo_enrich", lambda ip: None)

        from app.services.lead_worker import run_enrichment_job

        with pytest.raises(RuntimeError):
            run_enrichment_job(lead_id)

    def test_nullable_geo_fields_on_enrichment_failure(
        self, client, created_widget, monkeypatch
    ):
        widget_id = str(created_widget.id)
        resp = client.post(
            f"/public/widget/{widget_id}/submit",
            json={"form_data": {"name": "John", "email": "john@test.com"}},
            headers={"Origin": "https://myshop.com"},
        )
        assert resp.status_code == 201
        lead_id = resp.json()["lead_id"]

        repo = lead_service._get_or_create_repo()
        monkeypatch.setattr("app.services.lead_worker.LeadRepository", lambda: repo)

        mock_job = MagicMock()
        mock_job.id = "test-enrich-geo-null"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0
        monkeypatch.setattr(
            "app.services.lead_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.lead_worker.update_enrichment_job", MagicMock()
        )
        monkeypatch.setattr("app.services.lead_worker.send_alert", MagicMock())
        monkeypatch.setattr("app.services.lead_worker.logger", MagicMock())
        monkeypatch.setattr("app.services.lead_worker.geo_enrich", lambda ip: None)

        from app.services.lead_worker import run_enrichment_job

        with pytest.raises(RuntimeError):
            run_enrichment_job(lead_id)

        from app.services import widget_service

        raw = asyncio.run(widget_service._get_repo().get_by_id_raw(widget_id))
        tenant_id = str(raw["tenant_id"])

        lead = asyncio.run(lead_service.get_lead_detail(lead_id, widget_id, tenant_id))
        assert lead is not None
        assert lead.status == "failed"
        assert lead.geo_country is None
        assert lead.geo_city is None
        assert lead.geo_region is None
        assert lead.geo_isp is None
        assert lead.geo_provider is None

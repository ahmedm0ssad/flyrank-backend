import asyncio
from unittest.mock import MagicMock

import pytest

from app.models.job import JobStatus


class TestRunEnrichmentJob:
    def test_successful_enrichment(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-enrich-1"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr(
            "app.services.lead_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.lead_worker.update_enrichment_job", MagicMock()
        )

        fake_lead = MagicMock()
        fake_lead.status = "pending"
        fake_lead.ip_address = "8.8.8.8"

        async def mock_get_by_id(self, lead_id):
            return fake_lead

        async def mock_update_status(self, lead_id, status, **kw):
            return fake_lead

        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.get_by_id",
            mock_get_by_id,
        )
        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.update_status",
            mock_update_status,
        )
        monkeypatch.setattr(
            "app.services.lead_worker.geo_enrich",
            lambda ip: {
                "country": "US",
                "city": "Mountain View",
                "region": "California",
                "isp": "Google",
                "provider": "ipapi",
            },
        )

        from app.services.lead_worker import run_enrichment_job

        result = run_enrichment_job("lead-1")
        assert result == "enriched"

    def test_cache_hit_path(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-enrich-2"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr(
            "app.services.lead_worker.get_current_job", lambda: mock_job
        )

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status, **extra})

        monkeypatch.setattr(
            "app.services.lead_worker.update_enrichment_job", fake_update
        )

        fake_lead = MagicMock()
        fake_lead.status = "pending"
        fake_lead.ip_address = "8.8.8.8"

        async def mock_get_by_id(self, lead_id):
            return fake_lead

        async def mock_update_status(self, lead_id, status, **kw):
            return fake_lead

        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.get_by_id",
            mock_get_by_id,
        )
        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.update_status",
            mock_update_status,
        )
        monkeypatch.setattr(
            "app.services.lead_worker.geo_enrich",
            lambda ip: {
                "country": "US",
                "city": "Mountain View",
                "region": "California",
                "isp": "Google",
                "provider": "ipapi",
            },
        )

        from app.services.lead_worker import run_enrichment_job

        run_enrichment_job("lead-1")
        assert any(u["status"] == JobStatus.FINISHED.value for u in updates)

    def test_idempotent_skip_when_already_enriched(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-enrich-3"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr(
            "app.services.lead_worker.get_current_job", lambda: mock_job
        )

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status, **extra})

        monkeypatch.setattr(
            "app.services.lead_worker.update_enrichment_job", fake_update
        )

        fake_lead = MagicMock()
        fake_lead.status = "enriched"
        fake_lead.ip_address = "8.8.8.8"

        async def mock_get_by_id(self, lead_id):
            return fake_lead

        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.get_by_id",
            mock_get_by_id,
        )

        geo_call_count = 0

        def fake_geo(ip):
            nonlocal geo_call_count
            geo_call_count += 1
            return None

        monkeypatch.setattr(
            "app.services.lead_worker.geo_enrich", fake_geo
        )

        from app.services.lead_worker import run_enrichment_job

        result = run_enrichment_job("lead-1")
        assert result == "already_enriched"
        assert geo_call_count == 0
        assert any(u["status"] == JobStatus.FINISHED.value for u in updates)

    def test_all_providers_fail(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-enrich-4"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr(
            "app.services.lead_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.lead_worker.update_enrichment_job", MagicMock()
        )

        fake_lead = MagicMock()
        fake_lead.status = "pending"
        fake_lead.ip_address = "8.8.8.8"

        async def mock_get_by_id(self, lead_id):
            return fake_lead

        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.get_by_id",
            mock_get_by_id,
        )
        monkeypatch.setattr(
            "app.services.lead_worker.geo_enrich", lambda ip: None
        )
        monkeypatch.setattr(
            "app.services.lead_worker.send_alert", MagicMock()
        )
        monkeypatch.setattr(
            "app.services.lead_worker.logger", MagicMock()
        )

        from app.services.lead_worker import run_enrichment_job

        with pytest.raises(RuntimeError):
            run_enrichment_job("lead-1")

    def test_retry_cycle_requeues_on_intermediate_failure(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-enrich-5"
        mock_job.meta = {"max_retries": 3, "current_attempt": 1}
        mock_job.retries_left = 2
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr(
            "app.services.lead_worker.get_current_job", lambda: mock_job
        )

        updates = []

        def fake_update(job_id, status, **extra):
            updates.append({"status": status})

        monkeypatch.setattr(
            "app.services.lead_worker.update_enrichment_job", fake_update
        )

        fake_lead = MagicMock()
        fake_lead.status = "pending"
        fake_lead.ip_address = "8.8.8.8"

        async def mock_get_by_id(self, lead_id):
            return fake_lead

        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.get_by_id",
            mock_get_by_id,
        )
        monkeypatch.setattr(
            "app.services.lead_worker.geo_enrich", lambda ip: None
        )
        monkeypatch.setattr(
            "app.services.lead_worker.send_alert", MagicMock()
        )
        monkeypatch.setattr(
            "app.services.lead_worker.logger", MagicMock()
        )

        from app.services.lead_worker import run_enrichment_job

        with pytest.raises(RuntimeError):
            run_enrichment_job("lead-1")

        last_update = updates[-1]
        assert last_update.get("status") == JobStatus.QUEUED.value

    def test_alert_sent_on_final_failure(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-enrich-6"
        mock_job.meta = {"max_retries": 3, "current_attempt": 3}
        mock_job.retries_left = 0
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr(
            "app.services.lead_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.lead_worker.update_enrichment_job", MagicMock()
        )

        fake_lead = MagicMock()
        fake_lead.status = "pending"
        fake_lead.ip_address = "8.8.8.8"

        async def mock_get_by_id(self, lead_id):
            return fake_lead

        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.get_by_id",
            mock_get_by_id,
        )
        monkeypatch.setattr(
            "app.services.lead_worker.geo_enrich", lambda ip: None
        )

        alerts = []

        def fake_alert(msg):
            alerts.append(msg)

        monkeypatch.setattr(
            "app.services.lead_worker.send_alert", fake_alert
        )
        monkeypatch.setattr(
            "app.services.lead_worker.logger", MagicMock()
        )

        from app.services.lead_worker import run_enrichment_job

        with pytest.raises(RuntimeError):
            run_enrichment_job("lead-1")

        assert len(alerts) == 1
        assert "lead-1" in alerts[0]

    def test_lead_status_updated_on_final_failure(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-enrich-7"
        mock_job.meta = {"max_retries": 3, "current_attempt": 3}
        mock_job.retries_left = 0
        mock_job.save_meta = MagicMock()

        monkeypatch.setattr(
            "app.services.lead_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.lead_worker.update_enrichment_job", MagicMock()
        )

        fake_lead = MagicMock()
        fake_lead.status = "pending"
        fake_lead.ip_address = "8.8.8.8"

        async def mock_get_by_id(self, lead_id):
            return fake_lead

        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.get_by_id",
            mock_get_by_id,
        )
        monkeypatch.setattr(
            "app.services.lead_worker.geo_enrich", lambda ip: None
        )

        lead_updates = []

        async def mock_update_status(self, lead_id, status, **kw):
            lead_updates.append({"lead_id": lead_id, "status": status, **kw})
            return fake_lead

        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.update_status",
            mock_update_status,
        )
        monkeypatch.setattr(
            "app.services.lead_worker.send_alert", MagicMock()
        )
        monkeypatch.setattr(
            "app.services.lead_worker.logger", MagicMock()
        )

        from app.services.lead_worker import run_enrichment_job

        with pytest.raises(RuntimeError):
            run_enrichment_job("lead-1")

        assert len(lead_updates) > 0
        last_lead_update = lead_updates[-1]
        assert last_lead_update["status"] == "failed"

    def test_lead_status_updated_to_enriched_on_success(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.id = "test-enrich-8"
        mock_job.meta = {"max_retries": 3, "current_attempt": 0}
        mock_job.retries_left = 0

        monkeypatch.setattr(
            "app.services.lead_worker.get_current_job", lambda: mock_job
        )
        monkeypatch.setattr(
            "app.services.lead_worker.update_enrichment_job", MagicMock()
        )

        fake_lead = MagicMock()
        fake_lead.status = "pending"
        fake_lead.ip_address = "8.8.8.8"

        async def mock_get_by_id(self, lead_id):
            return fake_lead

        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.get_by_id",
            mock_get_by_id,
        )

        lead_updates = []

        async def mock_update_status(self, lead_id, status, **kw):
            lead_updates.append({"lead_id": lead_id, "status": status, **kw})
            return fake_lead

        monkeypatch.setattr(
            "app.repositories.lead_repo.LeadRepository.update_status",
            mock_update_status,
        )
        monkeypatch.setattr(
            "app.services.lead_worker.geo_enrich",
            lambda ip: {
                "country": "US",
                "city": "Mountain View",
                "region": "California",
                "isp": "Google",
                "provider": "ipapi",
            },
        )

        from app.services.lead_worker import run_enrichment_job

        run_enrichment_job("lead-1")
        assert len(lead_updates) == 1
        assert lead_updates[0]["status"] == "enriched"
        assert lead_updates[0]["geo_country"] == "US"

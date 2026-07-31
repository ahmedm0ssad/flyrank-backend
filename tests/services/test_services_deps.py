import pytest

from app.dependencies import services


class TestGetLeadRepoPostgresBranch:
    def test_returns_postgres_repo_when_enabled(self, monkeypatch):
        from app.repositories.postgres_lead_repo import PostgresLeadRepository

        services._lead_repo = None
        monkeypatch.setattr("app.core.database.is_postgres_enabled", lambda: True)
        try:
            repo = services.get_lead_repo()
            assert isinstance(repo, PostgresLeadRepository)
        finally:
            services._lead_repo = None


class TestGetRedis:
    @pytest.mark.asyncio
    async def test_returns_none_when_main_get_redis_raises(self, monkeypatch):
        services._redis = None

        def _raise():
            raise RuntimeError("no redis")

        monkeypatch.setattr("app.main.get_redis", _raise)
        assert await services.get_redis() is None

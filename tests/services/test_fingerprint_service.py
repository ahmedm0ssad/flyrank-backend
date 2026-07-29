from unittest.mock import AsyncMock, patch

import pytest

from app.services.fingerprint_service import (
    FINGERPRINT_TTL,
    _get_redis,
    check_dedup,
    compute_fingerprint,
    mark_seen,
)


class TestComputeFingerprint:
    def test_same_input_produces_same_hash(self):
        fp1 = compute_fingerprint(
            "w1", "127.0.0.1", {"name": "John", "email": "j@x.com"}
        )
        fp2 = compute_fingerprint(
            "w1", "127.0.0.1", {"name": "John", "email": "j@x.com"}
        )
        assert fp1 == fp2

    def test_different_input_produces_different_hash(self):
        fp1 = compute_fingerprint("w1", "127.0.0.1", {"name": "John"})
        fp2 = compute_fingerprint("w1", "10.0.0.1", {"name": "John"})
        assert fp1 != fp2

    def test_different_widget_produces_different_hash(self):
        fp1 = compute_fingerprint("w1", "127.0.0.1", {"name": "John"})
        fp2 = compute_fingerprint("w2", "127.0.0.1", {"name": "John"})
        assert fp1 != fp2

    def test_different_form_data_produces_different_hash(self):
        fp1 = compute_fingerprint("w1", "127.0.0.1", {"name": "John"})
        fp2 = compute_fingerprint("w1", "127.0.0.1", {"name": "Jane"})
        assert fp1 != fp2

    def test_returns_sha256_hex_string(self):
        fp = compute_fingerprint("w1", "127.0.0.1", {"name": "John"})
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


class TestGetRedis:
    def test_returns_none_when_main_get_redis_fails(self):
        with patch("app.main.get_redis", side_effect=RuntimeError("no redis")):
            assert _get_redis() is None


class TestCheckDedup:
    @pytest.mark.asyncio
    async def test_returns_existing_lead_id(self, monkeypatch):
        fake_redis = AsyncMock()
        fake_redis.get.return_value = "lead-123"
        monkeypatch.setattr(
            "app.services.fingerprint_service._get_redis", lambda: fake_redis
        )

        result = await check_dedup("fp123")
        assert result == "lead-123"
        fake_redis.get.assert_awaited_once_with("submission:fp:fp123")

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, monkeypatch):
        fake_redis = AsyncMock()
        fake_redis.get.return_value = None
        monkeypatch.setattr(
            "app.services.fingerprint_service._get_redis", lambda: fake_redis
        )

        result = await check_dedup("fp456")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_redis_unavailable(self):
        with patch("app.services.fingerprint_service._get_redis", return_value=None):
            result = await check_dedup("fp789")
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_redis_error(self, monkeypatch):
        fake_redis = AsyncMock()
        fake_redis.get.side_effect = Exception("redis error")
        monkeypatch.setattr(
            "app.services.fingerprint_service._get_redis", lambda: fake_redis
        )

        result = await check_dedup("fp999")
        assert result is None


class TestMarkSeen:
    @pytest.mark.asyncio
    async def test_sets_lead_id_in_redis(self, monkeypatch):
        fake_redis = AsyncMock()
        monkeypatch.setattr(
            "app.services.fingerprint_service._get_redis", lambda: fake_redis
        )

        await mark_seen("fp123", "lead-456")
        fake_redis.setex.assert_awaited_once_with(
            "submission:fp:fp123", FINGERPRINT_TTL, "lead-456"
        )

    @pytest.mark.asyncio
    async def test_noop_when_redis_unavailable(self):
        with patch("app.services.fingerprint_service._get_redis", return_value=None):
            await mark_seen("fp123", "lead-456")

    @pytest.mark.asyncio
    async def test_does_not_crash_on_redis_error(self, monkeypatch):
        fake_redis = AsyncMock()
        fake_redis.setex.side_effect = Exception("redis error")
        monkeypatch.setattr(
            "app.services.fingerprint_service._get_redis", lambda: fake_redis
        )

        await mark_seen("fp123", "lead-456")

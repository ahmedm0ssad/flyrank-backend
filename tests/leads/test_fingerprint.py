import pytest

from app.services.fingerprint_service import (
    check_dedup,
    compute_fingerprint,
    mark_seen,
)

pytestmark = pytest.mark.usefixtures("mock_redis")


class TestFingerprint:
    def test_compute_fingerprint_is_deterministic(self):
        fp1 = compute_fingerprint("w1", "1.2.3.4", {"name": "John", "email": "j@t.com"})
        fp2 = compute_fingerprint("w1", "1.2.3.4", {"email": "j@t.com", "name": "John"})
        assert fp1 == fp2

    def test_compute_fingerprint_differs_by_ip(self):
        fp1 = compute_fingerprint("w1", "1.2.3.4", {"name": "John"})
        fp2 = compute_fingerprint("w1", "5.6.7.8", {"name": "John"})
        assert fp1 != fp2

    def test_compute_fingerprint_differs_by_widget(self):
        fp1 = compute_fingerprint("w1", "1.2.3.4", {"name": "John"})
        fp2 = compute_fingerprint("w2", "1.2.3.4", {"name": "John"})
        assert fp1 != fp2

    def test_compute_fingerprint_differs_by_data(self):
        fp1 = compute_fingerprint("w1", "1.2.3.4", {"name": "John"})
        fp2 = compute_fingerprint("w1", "1.2.3.4", {"name": "Jane"})
        assert fp1 != fp2

    @pytest.mark.asyncio
    async def test_dedup_none_when_not_seen(self):
        fp = compute_fingerprint("w1", "1.2.3.4", {"name": "John"})
        result = await check_dedup(fp)
        assert result is None

    @pytest.mark.asyncio
    async def test_dedup_finds_seen_fingerprint(self):
        fp = compute_fingerprint("w1", "1.2.3.4", {"name": "John"})
        await mark_seen(fp, "lead-123")
        result = await check_dedup(fp)
        assert result == "lead-123"

    @pytest.mark.asyncio
    async def test_dedup_expires_after_window(self):
        fp = compute_fingerprint("w1", "1.2.3.4", {"name": "John"})
        await mark_seen(fp, "lead-123")

        from tests.conftest import _fake_redis
        _fake_redis._strings.pop(f"submission:fp:{fp}", None)

        result = await check_dedup(fp)
        assert result is None

    @pytest.mark.asyncio
    async def test_dedup_different_ip_not_found(self):
        fp1 = compute_fingerprint("w1", "1.2.3.4", {"name": "John"})
        fp2 = compute_fingerprint("w1", "5.6.7.8", {"name": "John"})
        await mark_seen(fp1, "lead-123")
        result = await check_dedup(fp2)
        assert result is None

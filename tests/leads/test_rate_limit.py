import pytest

from app.dependencies.leads import (
    _in_process_limits,
    check_rate_limits,
)


class _FakeCountRedis:
    def __init__(self, fake_redis):
        self._strings = fake_redis._strings
        self._data = fake_redis._data
        self._commands = []

    def pipeline(self):
        return _FakePipeline(self._strings)

    async def expire(self, key, ttl):
        pass

    async def incr(self, key):
        val = int(self._strings.get(key, 0)) + 1
        self._strings[key] = str(val)
        return val


class _FakePipeline:
    def __init__(self, strings):
        self._strings = strings
        self._cmds = []

    def incr(self, key):
        self._cmds.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self._cmds.append(("expire", key))
        return self

    async def execute(self):
        results = []
        for cmd, key in self._cmds:
            if cmd == "incr":
                val = int(self._strings.get(key, 0)) + 1
                self._strings[key] = str(val)
                results.append(val)
            else:
                results.append(True)
        return results


@pytest.fixture(autouse=True)
def _clear_in_process_limits():
    _in_process_limits.clear()


@pytest.fixture
def monkey_redis(monkeypatch, fake_redis):
    fr = _FakeCountRedis(fake_redis)
    monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: fr)
    return fr


@pytest.mark.asyncio
class TestRateLimits:
    async def test_all_tiers_pass(self, monkey_redis):
        retry_after = await check_rate_limits("1.2.3.4", "widget-1")
        assert retry_after is None

    async def test_global_ip_blocks(self, monkey_redis):
        ip = "1.2.3.4"
        limit = 100
        for _ in range(limit + 1):
            retry_after = await check_rate_limits(ip, "widget-1")
        assert retry_after is not None

    async def test_widget_ip_blocks(self, monkey_redis):
        ip = "1.2.3.4"
        limit = 30
        for _ in range(limit + 1):
            retry_after = await check_rate_limits(ip, "widget-1")
        assert retry_after is not None

    async def test_widget_global_blocks(self, monkey_redis):
        limit = 1000
        for i in range(limit + 1):
            retry_after = await check_rate_limits(f"ip-{i}", "widget-1")
        assert retry_after is not None

    async def test_per_ip_isolation(self, monkey_redis):
        for _ in range(30):
            await check_rate_limits("1.2.3.4", "widget-1")
        retry_after = await check_rate_limits("5.6.7.8", "widget-1")
        assert retry_after is None

    async def test_per_widget_isolation(self, monkey_redis):
        for _ in range(30):
            await check_rate_limits("1.2.3.4", "widget-1")
        retry_after = await check_rate_limits("1.2.3.4", "widget-2")
        assert retry_after is None

    async def test_redis_down_fails_open(self, monkeypatch):
        monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: None)
        retry_after = await check_rate_limits("1.2.3.4", "widget-1")
        assert retry_after is None

    async def test_redis_down_in_process_blocks_after_limit(self, monkeypatch):
        monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: None)

        ip = "1.2.3.4"
        limit = 100
        for _ in range(limit + 1):
            retry_after = await check_rate_limits(ip, "widget-1")
        assert (
            retry_after is not None
        ), "in-process limiter should block after exceeding limit"

    async def test_redis_down_in_process_per_ip_isolation(self, monkeypatch):
        monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: None)

        for _ in range(30):
            await check_rate_limits("1.2.3.4", "widget-1")
        retry_after = await check_rate_limits("5.6.7.8", "widget-1")
        assert retry_after is None, "different IP should not be blocked"

    async def test_redis_pipeline_widget_ip_triggers_limit(self, monkey_redis):
        """Cover lines 77-84: pipeline.execute(), count extraction via
        [::2], limit comparison, and return of RATE_LIMIT_WINDOW."""
        ip = "10.0.0.1"
        widget = "widget-wip"
        limit = 30

        for _ in range(limit):
            retry = await check_rate_limits(ip, widget)
            assert retry is None

        retry = await check_rate_limits(ip, widget)
        assert retry is not None
        assert retry == 60, "should return RATE_LIMIT_WINDOW (=60)"

    async def test_redis_down_redis_error_falls_to_in_process(
        self, monkeypatch, monkey_redis
    ):

        class BrokenRedis:
            def pipeline(self):
                raise Exception("Redis connection error")

        monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: BrokenRedis())

        retry_after = await check_rate_limits("1.2.3.4", "widget-1")
        assert (
            retry_after is None
        ), "should fall back to in-process limiter on Redis error"


class TestInProcessLimitBounding:
    @pytest.mark.asyncio
    async def test_fails_open_and_bounded(self, monkeypatch):
        monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: None)
        monkeypatch.setattr(
            "app.dependencies.leads._MAX_IN_PROCESS_KEYS", 12
        )

        bound = 12
        for i in range(bound * 3):
            await check_rate_limits(f"ip-{i}", f"widget-{i % 4}")

        assert len(_in_process_limits) <= bound

    @pytest.mark.asyncio
    async def test_new_ip_still_rate_limited_after_lru_eviction(self, monkeypatch):
        """An IP that starts fresh after eviction still builds up to the
        limit correctly (no ghost state from pre-eviction keys)."""
        monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: None)
        monkeypatch.setattr(
            "app.dependencies.leads._MAX_IN_PROCESS_KEYS", 12
        )

        for i in range(12 * 3):
            await check_rate_limits(f"ip-{i}", "widget-1")

        ip = "10.0.0.1"
        limit = 100
        for _ in range(limit + 1):
            retry_after = await check_rate_limits(ip, "widget-1")
        assert retry_after is not None

    @pytest.mark.asyncio
    async def test_over_limit_ip_stays_blocked_after_lru_eviction(self, monkeypatch):
        """Block an IP on a tight bound, then add more keys past the
        bound. The most recently accessed per-widget limit key survives
        LRU eviction, so the victim stays blocked."""
        monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: None)
        monkeypatch.setattr(
            "app.dependencies.leads._MAX_IN_PROCESS_KEYS", 12
        )

        for i in range(3):
            await check_rate_limits(f"filler-{i}", f"fw-{i}")

        victim = "10.0.0.1"
        widget_v = "victim-w"
        for _ in range(31):
            await check_rate_limits(victim, widget_v)
        retry_after = await check_rate_limits(victim, widget_v)
        assert retry_after is not None, "victim should be blocked"

        for i in range(2):
            await check_rate_limits(f"extra-{i}", f"ew-{i}")

        assert len(_in_process_limits) <= 12

        retry_after = await check_rate_limits(victim, widget_v)
        assert retry_after is not None, (
            "victim should still be blocked — its widget_ip count "
            "key was recently accessed and survived LRU eviction"
        )

    @pytest.mark.asyncio
    async def test_lru_recent_access_survives_eviction(self, monkeypatch):
        """Create key A early, fill near bound, access A again (moves it
        to end via move_to_end), then flood past bound — A survives
        because it was recently touched, not because of creation order."""
        monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: None)
        monkeypatch.setattr(
            "app.dependencies.leads._MAX_IN_PROCESS_KEYS", 12
        )

        # 1. Create key A early (3 keys)
        await check_rate_limits("victim", "w-v")         # count = 1

        # 2. Fill to bound with 3 other callers (9 keys) → total 12
        for i in range(3):
            await check_rate_limits(f"f-{i}", f"wf-{i}")

        # 3. Access A again — move_to_end protects it
        await check_rate_limits("victim", "w-v")         # count = 2

        # 4. Flood past bound with 2 more callers → eviction
        for i in range(2):
            await check_rate_limits(f"x-{i}", f"wx-{i}")

        assert len(_in_process_limits) <= 12

        # 5. Prove A's count survived: need 28 more calls to hit widget_ip limit of 30
        for _ in range(28):
            retry = await check_rate_limits("victim", "w-v")
            assert retry is None
        retry = await check_rate_limits("victim", "w-v")
        assert retry is not None, (
            "victim's widget_ip count survived eviction — "
            "move_to_end on every access provides true LRU protection"
        )

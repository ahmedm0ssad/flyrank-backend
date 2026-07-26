import pytest

from app.dependencies.leads import check_rate_limits, RATE_LIMIT_TIERS, RATE_LIMIT_WINDOW, _in_process_limits


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
        self._cmds.append(key)
        return self

    async def execute(self):
        results = []
        for key in self._cmds:
            val = int(self._strings.get(key, 0)) + 1
            self._strings[key] = str(val)
            results.append(val)
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
        assert retry_after is not None, "in-process limiter should block after exceeding limit"

    async def test_redis_down_in_process_per_ip_isolation(self, monkeypatch):
        monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: None)

        for _ in range(30):
            await check_rate_limits("1.2.3.4", "widget-1")
        retry_after = await check_rate_limits("5.6.7.8", "widget-1")
        assert retry_after is None, "different IP should not be blocked"

    async def test_redis_down_redis_error_falls_to_in_process(self, monkeypatch, monkey_redis):
        original_pipeline = monkey_redis.pipeline

        class BrokenRedis:
            def pipeline(self):
                raise Exception("Redis connection error")

        monkeypatch.setattr("app.dependencies.leads._get_redis", lambda: BrokenRedis())

        retry_after = await check_rate_limits("1.2.3.4", "widget-1")
        assert retry_after is None, "should fall back to in-process limiter on Redis error"

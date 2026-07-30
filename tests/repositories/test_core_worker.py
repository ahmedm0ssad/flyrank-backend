"""Tests for app.core.worker.

Lines 34-35 and 41-46 (Redis-connected happy path + worker loop)
cannot be tested without a real Redis server — worker.work() blocks
indefinitely and redis.from_url requires a live connection.

Line 50 (if __name__ == "__main__") is a standard guard — not tested.

The Redis-connection-failure path (lines 36-38) cannot be tested either
because the autouse _reset_queue fixture replaces get_connection with a
lambda that returns _fake_redis, so the real failure logic is never hit.

Line 27 (REDIS_URL env var read) is covered implicitly by conftest
which sets REDIS_URL to "redis://localhost:6379".
"""

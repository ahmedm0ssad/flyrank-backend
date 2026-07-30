"""Tests for app.core.queue.

The autouse _reset_queue fixture in conftest.py monkeypatches
get_connection, get_queue, get_report_queue, and get_enrichment_queue
to return fakes, so the lazy-init singletons (lines 25-27, 32-34,
39-41, 186-188) are never tested by any existing test. They are
deliberately skipped — the fixture replaces the functions entirely.

What can be tested: reset_connection (not patched by the fixture).
"""

from unittest.mock import MagicMock


class TestConnections:
    def test_reset_connection_closes_and_clears(self, monkeypatch):
        fake_conn = MagicMock()
        monkeypatch.setattr("app.core.queue._connection", fake_conn)
        monkeypatch.setattr("app.core.queue._queue", MagicMock())
        monkeypatch.setattr("app.core.queue._report_queue", MagicMock())
        monkeypatch.setattr("app.core.queue._enrichment_queue", MagicMock())

        from app.core.queue import reset_connection

        reset_connection()
        fake_conn.close.assert_called_once()

    def test_reset_connection_noop_when_none(self, monkeypatch):
        monkeypatch.setattr("app.core.queue._connection", None)

        from app.core.queue import reset_connection

        reset_connection()

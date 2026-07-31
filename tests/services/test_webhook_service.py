import asyncio
import logging

import httpx

from app.services import webhook_service


class _FakeClient:
    def __init__(self, response=None, error=None, delay=0.0):
        self.response = response
        self.error = error
        self.delay = delay
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, **kwargs):
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        self.posts.append((url, json))
        return self.response


def _patch_client(monkeypatch, client):
    monkeypatch.setattr(webhook_service.httpx, "AsyncClient", lambda *a, **k: client)


class TestDispatchWebhook:
    async def test_success_returns_true_and_posts_payload(self, monkeypatch):
        client = _FakeClient(response=httpx.Response(200, json={}))
        _patch_client(monkeypatch, client)

        result = await webhook_service.dispatch_webhook(
            "https://hooks.example.com/lead", {"lead_id": "abc-123"}
        )
        assert result is True
        assert client.posts == [
            ("https://hooks.example.com/lead", {"lead_id": "abc-123"})
        ]

    async def test_non_2xx_returns_false_and_logs(self, monkeypatch, caplog):
        client = _FakeClient(response=httpx.Response(500, json={}))
        _patch_client(monkeypatch, client)

        with caplog.at_level(logging.WARNING, logger="app.services.webhook_service"):
            result = await webhook_service.dispatch_webhook(
                "https://hooks.example.com/lead", {}
            )
        assert result is False
        assert "returned 500" in caplog.text

    async def test_timeout_returns_false_and_logs(self, monkeypatch, caplog):
        monkeypatch.setattr(webhook_service, "WEBHOOK_TIMEOUT", 0.05)
        client = _FakeClient(response=httpx.Response(200), delay=1.0)
        _patch_client(monkeypatch, client)

        with caplog.at_level(logging.WARNING, logger="app.services.webhook_service"):
            result = await webhook_service.dispatch_webhook(
                "https://hooks.example.com/lead", {}
            )
        assert result is False
        assert "timeout" in caplog.text

    async def test_request_error_returns_false_and_logs(self, monkeypatch, caplog):
        client = _FakeClient(error=httpx.ConnectError("connection refused"))
        _patch_client(monkeypatch, client)

        with caplog.at_level(logging.WARNING, logger="app.services.webhook_service"):
            result = await webhook_service.dispatch_webhook(
                "https://hooks.example.com/lead", {}
            )
        assert result is False
        assert "request error" in caplog.text
        assert "connection refused" in caplog.text

    async def test_unexpected_exception_returns_false_and_logs(
        self, monkeypatch, caplog
    ):
        client = _FakeClient(error=RuntimeError("boom"))
        _patch_client(monkeypatch, client)

        with caplog.at_level(logging.WARNING, logger="app.services.webhook_service"):
            result = await webhook_service.dispatch_webhook(
                "https://hooks.example.com/lead", {}
            )
        assert result is False
        assert "boom" in caplog.text

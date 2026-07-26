from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes: int = 50_000):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length and int(content_length) > self.max_bytes:
            response = JSONResponse({"detail": "Payload too large"}, status_code=413)
            return await response(scope, receive, send)

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                raise StarletteHTTPException(
                    status_code=413, detail="Payload too large"
                )
            return message

        return await self.app(scope, limited_receive, send)

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_BACKUP_BYTES = 72 * 1024 * 1024
MAX_AUTH_BYTES = 64 * 1024
MAX_API_BYTES = 16 * 1024 * 1024
MAX_IMPORT_BYTES = 16 * 1024 * 1024


class ApiBodyLimitMiddleware:
    """Enforce endpoint byte budgets before framework parsing or dependencies."""

    def __init__(self, app: ASGIApp, api_prefix: str) -> None:
        self.app = app
        self.api_prefix = api_prefix.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith(self.api_prefix + "/"):
            await self.app(scope, receive, send)
            return
        relative = path[len(self.api_prefix) :]
        backup = relative == "/setup/restore" or relative.startswith("/backup/")
        limit = (
            MAX_BACKUP_BYTES
            if backup
            else MAX_IMPORT_BYTES
            if relative.startswith("/imports/")
            else MAX_AUTH_BYTES
            if relative == "/setup" or relative.startswith("/auth/")
            else MAX_API_BYTES
        )
        error = (
            backup_too_large()
            if backup
            else HTTPException(
                413,
                detail={"code": "request_too_large", "message": "Request exceeds the byte limit"},
            )
        )
        lengths = [
            value for key, value in scope.get("headers", []) if key.lower() == b"content-length"
        ]
        try:
            declared = int(lengths[0]) if lengths else 0
            invalid = len(lengths) > 1 or declared < 0 or declared > limit
        except ValueError:
            invalid = True
        if invalid:
            await JSONResponse(status_code=413, content={"detail": error.detail})(
                scope, receive, send
            )
            return
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise error
            return message

        await self.app(scope, limited_receive, send)


class BackupBodyLimitRoute(APIRoute):
    """Reject oversized backup bodies before FastAPI buffers and parses JSON."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_handler = super().get_route_handler()

        async def limited_handler(request: Request) -> Response:
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = MAX_BACKUP_BYTES + 1
                if declared_size > MAX_BACKUP_BYTES:
                    raise backup_too_large()

            received = 0
            original_receive = request.receive

            async def limited_receive() -> Message:
                nonlocal received
                message = await original_receive()
                if message["type"] == "http.request":
                    received += len(message.get("body", b""))
                    if received > MAX_BACKUP_BYTES:
                        raise backup_too_large()
                return message

            return await original_handler(Request(request.scope, limited_receive))

        return limited_handler


def backup_too_large() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        detail={
            "code": "backup_too_large",
            "message": "Backup exceeds the 72 MiB request limit",
        },
    )


__all__ = ["BackupBodyLimitRoute", "MAX_BACKUP_BYTES", "backup_too_large"]

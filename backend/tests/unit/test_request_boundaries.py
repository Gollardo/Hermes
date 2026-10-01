import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.types import Message, Scope

from app.core.config import Settings
from app.core.database import get_database_session
from app.core.http_limits import (
    MAX_API_BYTES,
    MAX_AUTH_BYTES,
    MAX_BACKUP_BYTES,
    MAX_IMPORT_BYTES,
    ApiBodyLimitMiddleware,
)
from app.main import create_app
from app.modules.auth.client import login_client_key
from app.modules.funds.schemas import AllocationCreateRequest


def test_login_rejects_oversize_before_database_or_validation() -> None:
    app = create_app(Settings())

    def forbidden_dependency() -> None:
        pytest.fail("Database dependency must not execute for an oversized request")

    app.dependency_overrides[get_database_session] = forbidden_dependency
    with TestClient(app) as client:
        response = client.post("/api/v1/auth/login", content=b"x" * (MAX_AUTH_BYTES + 1))
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "request_too_large"


def body_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ApiBodyLimitMiddleware, api_prefix="/api/v1")

    @app.post("/api/v1/{path:path}")
    async def echo(payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    return app


@pytest.mark.parametrize("length", [None, b"1"])
def test_streaming_bound_counts_chunks_not_declared_length(length: bytes | None) -> None:
    async def run() -> list[Message]:
        messages: list[Message] = []
        chunks = iter(
            [
                {"type": "http.request", "body": b"x" * MAX_AUTH_BYTES, "more_body": True},
                {"type": "http.request", "body": b"x", "more_body": False},
            ]
        )

        async def receive() -> Message:
            return next(chunks)

        async def send(message: Message) -> None:
            messages.append(message)

        headers = [(b"content-type", b"application/json")]
        if length is not None:
            headers.append((b"content-length", length))
        scope: Scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": headers,
            "query_string": b"",
        }
        await body_app()(scope, receive, send)
        return messages

    messages = asyncio.run(run())
    assert messages[0]["status"] == 413
    assert b"request_too_large" in messages[1]["body"]


@pytest.mark.parametrize(
    "path,limit,code",
    [
        ("/auth/login", MAX_AUTH_BYTES, "request_too_large"),
        ("/setup", MAX_AUTH_BYTES, "request_too_large"),
        ("/funds/allocations", MAX_API_BYTES, "request_too_large"),
        ("/imports/commit", MAX_IMPORT_BYTES, "request_too_large"),
        ("/setup/restore", MAX_BACKUP_BYTES, "backup_too_large"),
        ("/backup/restore", MAX_BACKUP_BYTES, "backup_too_large"),
    ],
)
def test_endpoint_budgets_and_malformed_lengths(path: str, limit: int, code: str) -> None:
    with TestClient(body_app()) as client:
        assert (
            client.post(
                "/api/v1" + path, json={}, headers={"Content-Length": str(limit)}
            ).status_code
            == 200
        )
        for length in [str(limit + 1), "-1", "invalid"]:
            response = client.post("/api/v1" + path, json={}, headers={"Content-Length": length})
            assert response.status_code == 413
            assert response.json()["detail"]["code"] == code


def test_unicode_passwords_and_exact_byte_budget_remain_supported() -> None:
    content = json.dumps(
        {"current_password": "😀" * 1024, "new_master_password": "😀" * 1024}
    ).encode()
    content += b" " * (MAX_AUTH_BYTES - len(content))
    with TestClient(body_app()) as client:
        assert (
            client.post(
                "/api/v1/auth/password",
                content=content,
                headers={"Content-Type": "application/json"},
            ).status_code
            == 200
        )
        assert client.post("/api/v1/auth/login", content=b"{").status_code == 422


@pytest.mark.parametrize(
    "peer,forwarded,networks,expected",
    [
        ("192.0.2.1", "198.51.100.1", [], "192.0.2.1"),
        ("127.0.0.1", "198.51.100.1", [], "127.0.0.1"),
        ("127.0.0.1", "198.51.100.1", ["127.0.0.1/32"], "198.51.100.1"),
        ("127.0.0.1", "spoof, 192.0.2.1", ["127.0.0.1/32"], "127.0.0.1"),
        ("127.0.0.1", "203.0.113.1, 192.0.2.1", ["127.0.0.1/32"], "192.0.2.1"),
        ("::1", "2001:db8::1", ["::1/128"], "2001:db8::1"),
    ],
)
def test_only_explicitly_trusted_proxy_hops_define_login_source(
    peer: str, forwarded: str, networks: list[str], expected: str
) -> None:
    request = Request(
        {
            "type": "http",
            "client": (peer, 1234),
            "headers": [(b"x-forwarded-for", forwarded.encode())],
        }
    )
    assert login_client_key(request, Settings(trusted_proxy_networks=networks)) == expected


def test_proxy_configuration_rejects_trust_everyone() -> None:
    with pytest.raises(ValueError):
        Settings(trusted_proxy_networks=["0.0.0.0/0"])


def test_supported_large_financial_batch_does_not_use_small_auth_budget() -> None:
    payload = {
        "account_id": str(uuid4()),
        "amount": "1000",
        "occurred_on": "2026-10-01",
        "allocations": [
            {"fund_id": str(uuid4()), "amount": "1", "allocation_percentage": "0.1"}
            for _ in range(1000)
        ],
    }
    AllocationCreateRequest.model_validate(payload)
    content = json.dumps(payload).encode()
    assert MAX_AUTH_BYTES < len(content) < MAX_API_BYTES
    with TestClient(body_app()) as client:
        assert (
            client.post(
                "/api/v1/funds/allocations",
                content=content,
                headers={"Content-Type": "application/json"},
            ).status_code
            == 200
        )

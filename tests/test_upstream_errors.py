import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from dsystem.clients.service import RemoteServiceError
from dsystem.handlers import register_handlers

UPSTREAM = {
    "code": "partner.credit_limit_exceeded",
    "key": "partner.credit_limit_exceeded",
    "message": "Partner credit limit exceeded",
    "params": {"projected": "600"},
    "errors": [{"field": "lines.0.quantity", "code": "MIN_VALUE"}],
}


def _app() -> FastAPI:
    app = FastAPI()
    register_handlers(app)

    @app.get("/remote/{status_code}")
    async def remote(status_code: int) -> dict:
        raise RemoteServiceError("http://operations", status_code, UPSTREAM["message"], UPSTREAM)

    @app.get("/httpx")
    async def raw() -> dict:
        request = httpx.Request("POST", "http://operations/api/internal/x")
        response = httpx.Response(409, json=UPSTREAM, request=request)
        raise httpx.HTTPStatusError("conflict", request=request, response=response)

    @app.get("/plain")
    async def plain() -> dict:
        raise RemoteServiceError("http://operations", 422, "bad", None)

    return app


async def _get(path: str) -> httpx.Response:
    async with AsyncClient(transport=ASGITransport(app=_app(), raise_app_exceptions=False), base_url="http://t") as c:
        return await c.get(path)


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/remote/409", "/httpx"])
async def test_an_upstream_envelope_reaches_the_client_unchanged(path):
    response = await _get(path)
    body = response.json()
    assert response.status_code == 409
    assert body["code"] == "partner.credit_limit_exceeded" and body["key"] == "partner.credit_limit_exceeded"
    assert body["params"] == {"projected": "600"} and body["errors"] == UPSTREAM["errors"]
    assert body["message"] == "Partner credit limit exceeded"


@pytest.mark.asyncio
async def test_a_plain_upstream_error_keeps_the_generic_envelope():
    body = (await _get("/plain")).json()
    assert body["code"] == "HTTP_422" and body["message"]


@pytest.mark.asyncio
async def test_an_upstream_failure_is_a_502():
    response = await _get("/remote/500")
    assert response.status_code == 502 and response.json()["code"] == "UPSTREAM_UNAVAILABLE"

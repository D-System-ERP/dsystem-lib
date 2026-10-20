import asyncio
import os
import weakref
from typing import Any

import httpx

from dsystem.context import get_audit_context
from dsystem.dependencies.service_auth import get_service_secret


def _ambient_secret() -> str:
    return os.environ.get("SERVICE_SECRET_KEY") or get_service_secret()


KEEPALIVE_SECONDS = 4.0

_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient]" = weakref.WeakKeyDictionary()


def pooled_client() -> httpx.AsyncClient:
    """One client per event loop, its connections kept alive between calls. A client per call opened a new connection
    and looked the host up every time (2026-10-20 perf review, P12). Idle connections close before uvicorn's 5 s
    keep-alive does, so a reused one is never one the server is closing."""
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None or client.is_closed:
        limits = httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=KEEPALIVE_SECONDS)
        client = _clients[loop] = httpx.AsyncClient(limits=limits)
    return client


class RemoteServiceError(RuntimeError):
    def __init__(self, service: str, status_code: int | None, detail: str, body: dict | None = None) -> None:
        self.service = service
        self.status_code = status_code
        self.detail = detail
        self.body = body
        super().__init__(f"{service} responded {status_code}: {detail}")


class ServiceClient:
    def __init__(self, base_url: str, *, service_secret: str | None = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._secret = service_secret if service_secret is not None else _ambient_secret()

    def _headers(self) -> dict:
        headers = {"X-Service-Secret": self._secret}
        ctx = get_audit_context()
        if ctx.request_id is not None:
            headers["X-Request-ID"] = str(ctx.request_id)
        return headers

    def _raise(self, resp: "httpx.Response") -> None:
        if resp.status_code < 400:
            return
        body = None
        try:
            parsed = resp.json()
        except ValueError:
            detail = resp.text[:300]
        else:
            body = parsed if isinstance(parsed, dict) else None
            detail = (body or {}).get("message") or (body or {}).get("detail") or str(parsed)
        raise RemoteServiceError(self.base_url, resp.status_code, str(detail), body)

    async def get(self, path: str, params: dict | None = None) -> dict:
        resp = await pooled_client().get(
            f"{self.base_url}{path}", params=params, headers=self._headers(), timeout=self.timeout
        )
        self._raise(resp)
        return resp.json()

    async def post(self, path: str, json: Any = None) -> dict:
        resp = await pooled_client().post(
            f"{self.base_url}{path}", json=json, headers=self._headers(), timeout=self.timeout
        )
        self._raise(resp)
        return resp.json()

    async def patch(self, path: str, json: Any = None) -> dict:
        resp = await pooled_client().patch(
            f"{self.base_url}{path}", json=json, headers=self._headers(), timeout=self.timeout
        )
        self._raise(resp)
        return resp.json()

    async def delete(self, path: str) -> dict:
        resp = await pooled_client().delete(f"{self.base_url}{path}", headers=self._headers(), timeout=self.timeout)
        self._raise(resp)
        return resp.json()

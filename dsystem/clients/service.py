import os
from typing import Any

import httpx

from dsystem.context import get_audit_context


class RemoteServiceError(RuntimeError):
    def __init__(self, service: str, status_code: int | None, detail: str) -> None:
        self.service = service
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{service} responded {status_code}: {detail}")


class ServiceClient:
    def __init__(self, base_url: str, *, service_secret: str | None = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._secret = service_secret if service_secret is not None else os.environ.get("SERVICE_SECRET_KEY", "")

    def _headers(self) -> dict:
        headers = {"X-Service-Secret": self._secret}
        ctx = get_audit_context()
        if ctx.request_id is not None:
            headers["X-Request-ID"] = str(ctx.request_id)
        return headers

    def _raise(self, resp: "httpx.Response") -> None:
        if resp.status_code < 400:
            return
        try:
            body = resp.json()
            detail = body.get("message") or body.get("detail") or str(body)
        except ValueError:
            detail = resp.text[:300]
        raise RemoteServiceError(self.base_url, resp.status_code, str(detail))

    async def get(self, path: str, params: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.base_url}{path}", params=params, headers=self._headers())
            self._raise(resp)
            return resp.json()

    async def post(self, path: str, json: Any = None) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.base_url}{path}", json=json, headers=self._headers())
            self._raise(resp)
            return resp.json()

    async def patch(self, path: str, json: Any = None) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.patch(f"{self.base_url}{path}", json=json, headers=self._headers())
            self._raise(resp)
            return resp.json()

    async def delete(self, path: str) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.delete(f"{self.base_url}{path}", headers=self._headers())
            self._raise(resp)
            return resp.json()

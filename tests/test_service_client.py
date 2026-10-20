import asyncio

import httpx

from dsystem.clients import service
from dsystem.clients.service import ServiceClient
from dsystem.dependencies.service_auth import set_service_secret


def test_client_uses_the_secret_the_process_was_started_with(monkeypatch):
    monkeypatch.delenv("SERVICE_SECRET_KEY", raising=False)
    set_service_secret("from-settings")
    try:
        assert ServiceClient("http://auth")._headers()["X-Service-Secret"] == "from-settings"
    finally:
        set_service_secret("")


def test_environment_still_wins_for_scripts(monkeypatch):
    monkeypatch.setenv("SERVICE_SECRET_KEY", "from-env")
    set_service_secret("from-settings")
    try:
        assert ServiceClient("http://auth")._headers()["X-Service-Secret"] == "from-env"
    finally:
        set_service_secret("")


def test_explicit_secret_beats_both(monkeypatch):
    monkeypatch.setenv("SERVICE_SECRET_KEY", "from-env")
    set_service_secret("from-settings")
    try:
        assert ServiceClient("http://auth", service_secret="explicit")._headers()["X-Service-Secret"] == "explicit"
    finally:
        set_service_secret("")


def test_missing_secret_is_empty_not_a_crash(monkeypatch):
    monkeypatch.delenv("SERVICE_SECRET_KEY", raising=False)
    set_service_secret("")
    assert ServiceClient("http://auth")._headers()["X-Service-Secret"] == ""


async def test_calls_share_one_open_client_per_loop():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url), request.headers["X-Service-Secret"]))
        return httpx.Response(200, json={"ok": True})

    loop = asyncio.get_running_loop()
    mocked = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service._clients[loop] = mocked
    try:
        client = ServiceClient("http://auth/", service_secret="s")
        assert await client.get("/a", params={"x": 1}) == {"ok": True}
        assert await client.post("/b", json={}) == {"ok": True}
        assert service.pooled_client() is mocked and not mocked.is_closed
        assert seen == [("GET", "http://auth/a?x=1", "s"), ("POST", "http://auth/b", "s")]
        await mocked.aclose()
        assert service.pooled_client() is not mocked
    finally:
        await service._clients.pop(loop).aclose()

import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from dsystem.dependencies import _settings
from dsystem.middleware.idempotency import IdempotencyMiddleware


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


@pytest.fixture
def app(monkeypatch):
    fake = FakeRedis()

    async def _get_redis():
        return fake

    monkeypatch.setattr(_settings, "get_redis", _get_redis)
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)
    calls = {"n": 0}

    @app.post("/confirm")
    async def confirm(body: dict):
        calls["n"] += 1
        return {"n": calls["n"], "echo": body}

    @app.post("/fail")
    async def fail():
        calls["n"] += 1
        from fastapi import HTTPException

        raise HTTPException(500, "boom")

    app.state.calls = calls
    app.state.fake = fake
    return app


@pytest.mark.asyncio
async def test_same_key_replays_first_response(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        first = await client.post("/confirm", json={"a": 1}, headers={"Idempotency-Key": "k1"})
        second = await client.post("/confirm", json={"a": 1}, headers={"Idempotency-Key": "k1"})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    assert app.state.calls["n"] == 1


@pytest.mark.asyncio
async def test_same_key_different_body_is_refused(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        await client.post("/confirm", json={"a": 1}, headers={"Idempotency-Key": "k2"})
        clash = await client.post("/confirm", json={"a": 2}, headers={"Idempotency-Key": "k2"})
    assert clash.status_code == 422
    assert clash.json()["code"] == "idempotency.key_reused"


@pytest.mark.asyncio
async def test_without_key_every_call_runs(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        await client.post("/confirm", json={"a": 1})
        await client.post("/confirm", json={"a": 1})
    assert app.state.calls["n"] == 2


@pytest.mark.asyncio
async def test_server_error_is_not_cached(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        await client.post("/fail", headers={"Idempotency-Key": "k3"})
        await client.post("/fail", headers={"Idempotency-Key": "k3"})
    assert app.state.calls["n"] == 2
    assert not any(json.loads(v).get("status") == "done" for v in app.state.fake.store.values())

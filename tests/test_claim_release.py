"""A consumer that fails must release its ``claim_once`` key, or the redelivery is silently dropped."""

import pytest

from dsystem import cache
from dsystem.events import replica_sync, user_sync
from dsystem.events.envelope import build_envelope


class FakeRedis:
    def __init__(self):
        self.keys: set[str] = set()

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return False
        self.keys.add(key)
        return True

    async def delete(self, *keys):
        for key in keys:
            self.keys.discard(key)
        return len(keys)


@pytest.fixture
def redis(monkeypatch):
    fake = FakeRedis()

    async def _get_redis():
        return fake

    monkeypatch.setattr(cache, "get_redis", _get_redis)
    return fake


class FakeSessionFactory:
    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        return None


async def test_release_claim_lets_the_key_be_claimed_again(redis):
    assert await cache.claim_once("e1", namespace="q") is True
    assert await cache.claim_once("e1", namespace="q") is False
    await cache.release_claim("e1", namespace="q")
    assert await cache.claim_once("e1", namespace="q") is True


async def test_user_sync_retries_a_failed_event(redis, monkeypatch):
    calls = []

    async def flaky(session, data):
        calls.append(data["id"])
        if len(calls) == 1:
            raise RuntimeError("blip")

    monkeypatch.setitem(user_sync.HANDLERS, "user.updated", flaky)
    body = {**build_envelope({"id": "u1", "organization_id": "o1"}, organization_id="o1"), "event_id": "evt-1"}
    with pytest.raises(RuntimeError):
        await user_sync._dispatch(FakeSessionFactory(), "user.updated", body)
    await user_sync._dispatch(FakeSessionFactory(), "user.updated", body)
    await user_sync._dispatch(FakeSessionFactory(), "user.updated", body)
    assert calls == ["u1", "u1"]


async def test_replica_consumer_retries_a_failed_event(redis, monkeypatch):
    calls = []

    async def flaky(session, data):
        calls.append(data["id"])
        if len(calls) == 1:
            raise RuntimeError("blip")

    captured = {}

    async def fake_start_consumer(**kwargs):
        captured["handler"] = kwargs["handler"]

    monkeypatch.setattr(replica_sync, "start_consumer", fake_start_consumer)
    await replica_sync.run_replica_consumer(
        "amqp://x", FakeSessionFactory(), "svc-sync", {"legal_entity.updated": flaky}
    )
    dispatch = captured["handler"]
    body = {**build_envelope({"id": "le1", "organization_id": "o1"}, organization_id="o1"), "event_id": "evt-2"}
    with pytest.raises(RuntimeError):
        await dispatch("legal_entity.updated", body)
    await dispatch("legal_entity.updated", body)
    await dispatch("legal_entity.updated", body)
    assert calls == ["le1", "le1"]

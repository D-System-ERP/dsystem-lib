"""A consumer that fails must leave no claim behind, or the redelivery is silently dropped."""

import pytest

from dsystem import cache
from dsystem.events import inbox, replica_sync, user_sync
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


PROCESSED: set[tuple[str, str]] = set()


@pytest.fixture
def redis(monkeypatch):
    fake = FakeRedis()
    PROCESSED.clear()

    async def _get_redis():
        return fake

    async def _first_delivery(session, consumer, event_id):
        key = (consumer, str(event_id))
        if key in PROCESSED or key in session.pending:
            return False
        session.pending.add(key)
        return True

    monkeypatch.setattr(cache, "get_redis", _get_redis)
    monkeypatch.setattr(inbox, "first_delivery", _first_delivery)
    return fake


class FakeSession:
    def __init__(self):
        self.pending: set[tuple[str, str]] = set()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.pending.clear()
        return False

    async def commit(self):
        PROCESSED.update(self.pending)
        self.pending.clear()

    async def rollback(self):
        self.pending.clear()


class FakeSessionFactory:
    def __call__(self):
        return FakeSession()


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
        await user_sync._dispatch(FakeSessionFactory(), "user.updated", body, "crm-user-sync")
    await user_sync._dispatch(FakeSessionFactory(), "user.updated", body, "crm-user-sync")
    await user_sync._dispatch(FakeSessionFactory(), "user.updated", body, "crm-user-sync")
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

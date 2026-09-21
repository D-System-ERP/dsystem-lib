"""Every service keeps its own user replica, so each one must process every ``user.*`` event.

The dedupe claim is shared Redis state: a namespace common to all services lets the
first consumer to claim an event hide it from the others.
"""

from dsystem.events import user_sync
from dsystem.events.envelope import build_envelope
from tests.test_claim_release import FakeSessionFactory, redis  # noqa: F401


async def _dispatcher_for(service: str, monkeypatch) -> object:
    captured = {}

    async def fake_start_consumer(**kwargs):
        captured["handler"] = kwargs["handler"]

    monkeypatch.setattr(user_sync, "start_consumer", fake_start_consumer)
    await user_sync.start_user_sync_consumer("amqp://x", FakeSessionFactory(), service)
    return captured["handler"]


async def test_each_service_processes_the_same_user_event(redis, monkeypatch):  # noqa: F811
    seen = []

    async def record(session, data):
        seen.append(data["id"])

    monkeypatch.setitem(user_sync.HANDLERS, "user.created", record)
    crm = await _dispatcher_for("crm", monkeypatch)
    operations = await _dispatcher_for("operations", monkeypatch)
    body = {**build_envelope({"id": "u1", "organization_id": "o1"}, organization_id="o1"), "event_id": "evt-shared"}

    await crm("user.created", body)
    await operations("user.created", body)

    assert seen == ["u1", "u1"]


async def test_a_service_still_drops_its_own_redelivery(redis, monkeypatch):  # noqa: F811
    seen = []

    async def record(session, data):
        seen.append(data["id"])

    monkeypatch.setitem(user_sync.HANDLERS, "user.created", record)
    crm = await _dispatcher_for("crm", monkeypatch)
    body = {**build_envelope({"id": "u2", "organization_id": "o1"}, organization_id="o1"), "event_id": "evt-again"}

    await crm("user.created", body)
    await crm("user.created", body)

    assert seen == ["u2"]

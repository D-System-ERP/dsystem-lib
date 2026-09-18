from uuid import uuid4

from dsystem.events.envelope import EVENT_VERSION, build_envelope, is_envelope, unwrap


def test_build_and_unwrap_round_trip():
    org = uuid4()
    actor = uuid4()
    body = build_envelope({"id": "x", "name": "Acme"}, organization_id=org, actor_id=actor)
    body["event_id"] = "evt-1"

    assert is_envelope(body)
    data, meta = unwrap(body, "partner.created")
    assert data == {"id": "x", "name": "Acme"}
    assert meta.version == EVENT_VERSION
    assert meta.event_id == "evt-1"
    assert meta.organization_id == org
    assert meta.actor_id == actor
    assert meta.occurred_at is not None
    assert meta.routing_key == "partner.created"


def test_organization_defaults_to_payload_field():
    org = uuid4()
    body = build_envelope({"id": "x", "organization_id": str(org)})
    assert body["organization_id"] == str(org)


def test_bare_payload_is_tolerated():
    data, meta = unwrap({"id": "x", "organization_id": "not-a-uuid"})
    assert data == {"id": "x", "organization_id": "not-a-uuid"}
    assert meta.version == 0
    assert meta.organization_id is None

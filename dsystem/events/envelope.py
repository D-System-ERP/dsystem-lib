"""Event envelope shared by every dsystem publisher and consumer.

Every message on ``dsystem.events`` has the same outer shape so a consumer can
dedupe, attribute and version-check before it looks at the domain payload::

    {"v": 1, "event_id": "...", "organization_id": "...", "occurred_at": "...", "actor_id": "...", "data": {...}}

``event_id`` is stamped by the outbox at delivery time (it is the outbox row id,
identical on every redelivery), which is what makes ``claim_once`` reliable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from dsystem.utils.timezone import utc_now

EVENT_VERSION = 1
_ENVELOPE_KEYS = ("v", "data")


@dataclass(frozen=True)
class EventMeta:
    version: int
    event_id: str | None
    organization_id: UUID | None
    occurred_at: datetime | None
    actor_id: UUID | None
    routing_key: str | None = None


def _uuid(value: Any) -> UUID | None:
    if value is None or isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _iso(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def is_envelope(body: Any) -> bool:
    return isinstance(body, dict) and all(key in body for key in _ENVELOPE_KEYS)


def build_envelope(
    data: dict,
    *,
    organization_id: UUID | str | None = None,
    actor_id: UUID | str | None = None,
    occurred_at: datetime | None = None,
) -> dict:
    org = organization_id if organization_id is not None else data.get("organization_id")
    return {
        "v": EVENT_VERSION,
        "organization_id": str(org) if org is not None else None,
        "occurred_at": (occurred_at or utc_now()).isoformat(),
        "actor_id": str(actor_id) if actor_id is not None else None,
        "data": data,
    }


def unwrap(body: dict, routing_key: str | None = None) -> tuple[dict, EventMeta]:
    """Split a message into its domain payload and metadata.

    A bare payload (no envelope) is tolerated so hand-published test messages
    and older producers still reach the handler — the metadata is then derived
    from the payload itself.
    """
    if is_envelope(body):
        data = body.get("data") or {}
        return data, EventMeta(
            version=int(body.get("v") or 0),
            event_id=body.get("event_id"),
            organization_id=_uuid(body.get("organization_id")),
            occurred_at=_iso(body.get("occurred_at")),
            actor_id=_uuid(body.get("actor_id")),
            routing_key=routing_key,
        )
    return body, EventMeta(
        version=0,
        event_id=body.get("event_id"),
        organization_id=_uuid(body.get("organization_id")),
        occurred_at=_iso(body.get("occurred_at")),
        actor_id=None,
        routing_key=routing_key,
    )

"""Generic upsert/delete consumer for ``*_replicas`` tables.

Every replica follows the same contract: the source event's ``data.id`` is the
row id, listed fields are copied as-is, ``organization_id`` scopes the row, and a
``deleted`` event flips ``is_deleted`` (soft) or removes the row (hard). Services
instantiate ``ReplicaSync`` per replica model and register its handlers.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Numeric, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.sqltypes import Uuid

from dsystem.events.consumer import start_consumer
from dsystem.events.envelope import unwrap
from dsystem.events.inbox import event_time, run_once

logger = logging.getLogger(__name__)


def _stale(row, version: datetime | None) -> bool:
    current = getattr(row, "source_updated_at", None)
    return version is not None and current is not None and version < current


def _stamp(row, version: datetime | None) -> None:
    if version is not None and hasattr(row, "source_updated_at"):
        row.source_updated_at = version


class ReplicaSync:
    def __init__(self, model: type, fields: tuple[str, ...], *, soft_delete: bool = True):
        self.model = model
        self.fields = fields
        self.soft_delete = soft_delete
        self._columns = {col.key: col for col in model.__table__.columns}

    def _coerce(self, field: str, value: Any) -> Any:
        if value is None:
            return None
        column = self._columns.get(field)
        if column is None:
            return value
        if isinstance(column.type, Uuid) and not isinstance(value, UUID):
            return UUID(str(value))
        if isinstance(column.type, Numeric) and not isinstance(value, Decimal):
            return Decimal(str(value))
        return value

    def values(self, data: dict) -> dict:
        return {k: self._coerce(k, data.get(k)) for k in self.fields if k in data}

    async def upsert(self, session: AsyncSession, data: dict) -> None:
        if not data.get("id") or not data.get("organization_id"):
            return
        row_id = UUID(str(data["id"]))
        row = (
            await session.execute(select(self.model).where(self.model.id == row_id).with_for_update())
        ).scalar_one_or_none()
        values = self.values(data)
        version = event_time()
        if row is None:
            row = self.model(id=row_id, organization_id=UUID(str(data["organization_id"])), **values)
            _stamp(row, version)
            session.add(row)
            return
        if _stale(row, version):
            return
        for field, value in values.items():
            setattr(row, field, value)
        if self.soft_delete and hasattr(row, "is_deleted"):
            row.is_deleted = False
        _stamp(row, version)

    async def delete(self, session: AsyncSession, data: dict) -> None:
        if not data.get("id"):
            return
        row = (
            await session.execute(select(self.model).where(self.model.id == UUID(str(data["id"]))).with_for_update())
        ).scalar_one_or_none()
        if row is None or _stale(row, event_time()):
            return
        if self.soft_delete and hasattr(row, "is_deleted"):
            row.is_deleted = True
            _stamp(row, event_time())
        else:
            await session.delete(row)

    def handlers(self, prefix: str) -> dict[str, Callable[[AsyncSession, dict], Any]]:
        return {
            f"{prefix}.created": self.upsert,
            f"{prefix}.updated": self.upsert,
            f"{prefix}.deleted": self.delete,
        }


async def run_replica_consumer(
    rabbitmq_url: str,
    session_factory: async_sessionmaker,
    queue_name: str,
    handlers: dict[str, Callable[[AsyncSession, dict], Any]],
):
    """Start a consumer that routes each key to ``handler(session, data)`` inside one transaction."""

    async def dispatch(routing_key: str, body: dict):
        handler = handlers.get(routing_key)
        if handler is None:
            return
        data, meta = unwrap(body, routing_key)
        await run_once(session_factory, queue_name, meta.event_id, handler, data, occurred_at=meta.occurred_at)

    return await start_consumer(
        rabbitmq_url=rabbitmq_url,
        queue_name=queue_name,
        routing_keys=list(handlers),
        handler=dispatch,
    )

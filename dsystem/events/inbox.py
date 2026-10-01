"""Exactly-once effects for at-least-once delivery.

``run_once`` claims ``(consumer, event_id)`` in ``processed_events`` inside the handler's own transaction:
a crash before the commit leaves nothing behind, so the redelivery runs again; a duplicate delivered
while the first is still running waits on the primary key and then finds the row taken.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dsystem.models.processed_event import ProcessedEvent
from dsystem.utils.timezone import utc_now

INBOX_RETENTION_DAYS = 14

_event_time: ContextVar[datetime | None] = ContextVar("event_time", default=None)


def event_time() -> datetime | None:
    """``occurred_at`` of the event being handled — the version replicas compare against."""
    return _event_time.get()


async def first_delivery(session: AsyncSession, consumer: str, event_id: str) -> bool:
    claimed = await session.execute(
        insert(ProcessedEvent)
        .values(consumer=consumer, event_id=str(event_id))
        .on_conflict_do_nothing(index_elements=["consumer", "event_id"])
        .returning(ProcessedEvent.event_id)
    )
    return claimed.first() is not None


async def run_once(
    session_factory: async_sessionmaker,
    consumer: str,
    event_id: str | None,
    handler: Callable[..., Awaitable[Any]],
    *args,
    occurred_at: datetime | None = None,
) -> None:
    token = _event_time.set(occurred_at)
    try:
        async with session_factory() as session:
            if event_id and not await first_delivery(session, consumer, event_id):
                await session.rollback()
                return
            await handler(session, *args)
            await session.commit()
    finally:
        _event_time.reset(token)


async def prune_processed(session_factory: async_sessionmaker, older_than_days: int = INBOX_RETENTION_DAYS) -> int:
    cutoff = utc_now() - timedelta(days=older_than_days)
    async with session_factory() as session:
        result = await session.execute(delete(ProcessedEvent).where(ProcessedEvent.processed_at < cutoff))
        await session.commit()
        return result.rowcount or 0

"""Per-organization document/entity numbering (``P10001``, ``ABC-SA10001``).

Each service owns a ``sequences``-shaped table (``organization_id``, optional
``legal_entity_id``, ``kind``, ``prefix``, ``last_number``); ``next_code`` locks
the row with ``FOR UPDATE`` so concurrent requests never share a number.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from dsystem.models.base import BaseModel

START_NUMBER = 10000
TENANT_SCOPE = UUID("00000000-0000-0000-0000-000000000000")


class SequenceBase(BaseModel):
    __abstract__ = True

    organization_id: Mapped[UUID] = mapped_column(index=True)
    legal_entity_id: Mapped[UUID] = mapped_column(default=TENANT_SCOPE)
    kind: Mapped[str] = mapped_column(String(30))
    prefix: Mapped[str] = mapped_column(String(10))
    last_number: Mapped[int] = mapped_column(Integer, default=START_NUMBER)


def format_code(prefix: str, number: int, entity_prefix: str | None = None) -> str:
    code = f"{prefix}{number}"
    return f"{entity_prefix}-{code}" if entity_prefix else code


async def next_number(
    db: AsyncSession,
    model: type[SequenceBase],
    org_id: UUID,
    kind: str,
    prefix: str,
    legal_entity_id: UUID | None = None,
) -> int:
    scope = legal_entity_id or TENANT_SCOPE
    stmt = (
        select(model)
        .where(
            model.organization_id == org_id,
            model.legal_entity_id == scope,
            model.kind == kind,
            model.prefix == prefix,
        )
        .with_for_update()
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        row = model(organization_id=org_id, legal_entity_id=scope, kind=kind, prefix=prefix, last_number=START_NUMBER)
        db.add(row)
        await db.flush()
        row = (await db.execute(stmt)).scalar_one()
    row.last_number += 1
    await db.flush()
    return row.last_number


async def next_code(
    db: AsyncSession,
    model: type[SequenceBase],
    org_id: UUID,
    kind: str,
    prefix: str,
    legal_entity_id: UUID | None = None,
    entity_prefix: str | None = None,
) -> str:
    number = await next_number(db, model, org_id, kind, prefix, legal_entity_id)
    return format_code(prefix, number, entity_prefix)

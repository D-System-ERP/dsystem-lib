from datetime import datetime
from uuid import UUID

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from dsystem.repositories.base import TenantRepository
from dsystem.schemas.feed import FeedItem, FeedKind, FeedNote


class NoteRepository(TenantRepository):
    """The notes of one record kind, in the service's own `NoteMixin` table."""

    soft_delete = True

    def __init__(self, db: AsyncSession, org_id: UUID, model: type, target_type: str):
        super().__init__(db, org_id)
        self.model = model
        self.target_type = target_type

    def for_target(self, target_id: UUID) -> Select:
        return (
            self._base_query()
            .where(self.model.target_type == self.target_type, self.model.target_id == target_id)
            .order_by(self.model.created_at, self.model.id)
        )

    async def of_target(self, note_id: UUID, target_id: UUID):
        stmt = self._base_query().where(
            self.model.id == note_id, self.model.target_type == self.target_type, self.model.target_id == target_id
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def add(self, target_id: UUID, user_id: UUID | None, body: str, **refs):
        return await self.create(target_type=self.target_type, target_id=target_id, user_id=user_id, body=body, **refs)

    async def feed(self, target_id: UUID, before: datetime | None, limit: int) -> list[FeedItem]:
        stmt = self._base_query().where(self.model.target_type == self.target_type, self.model.target_id == target_id)
        if before is not None:
            stmt = stmt.where(self.model.created_at < before)
        stmt = stmt.order_by(self.model.created_at.desc(), self.model.id.desc()).limit(limit)
        return [note_item(row) for row in (await self.db.execute(stmt)).scalars()]


def note_item(row) -> FeedItem:
    return FeedItem(
        key=f"{FeedKind.NOTE.value}:{row.id}",
        kind=FeedKind.NOTE,
        at=row.created_at,
        actor_id=row.user_id,
        note=FeedNote(
            id=row.id,
            body=row.body,
            parent_id=row.parent_id,
            reply_to_id=row.reply_to_id,
            updated_at=row.updated_at,
        ),
    )

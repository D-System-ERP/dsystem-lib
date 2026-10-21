from collections.abc import Awaitable, Callable, Collection, Iterable, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, delete, func, select, union_all
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from dsystem.chat import QUOTE_LENGTH, REACTIONS, READ_EPOCH, Mentions
from dsystem.repositories.base import TenantRepository
from dsystem.schemas.feed import FeedItem, FeedKind, FeedNote, FeedReaction, FeedReader, NoteQuote
from dsystem.schemas.note import NoteRead
from dsystem.utils.timezone import utc_now

FileQuotes = Callable[[Collection[UUID]], Awaitable[dict[UUID, NoteQuote]]]


class NoteRepository(TenantRepository):
    """The notes of one record kind, in the service's own `NoteMixin` table; its reactions in `reactions`, a
    `NoteReactionMixin` table, when the service keeps them; `file_quotes` quotes the record's file rows a note answers
    (2026-10-21, khojiakbar's `2026-10-14-record-chat.md` § 11)."""

    soft_delete = True

    def __init__(
        self,
        db: AsyncSession,
        org_id: UUID,
        model: type,
        target_type: str,
        reactions: type | None = None,
        file_quotes: FileQuotes | None = None,
    ):
        super().__init__(db, org_id)
        self.model = model
        self.target_type = target_type
        self.reactions = reactions
        self.file_quotes = file_quotes

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
        return await self.create(
            target_type=self.target_type,
            target_id=target_id,
            user_id=user_id,
            body=body,
            mention_ids=list(Mentions.of(body).user_ids),
            **refs,
        )

    async def edit(self, note, body: str):
        return await self.update(note, body=body, mention_ids=list(Mentions.of(body).user_ids))

    async def pin(self, note, user_id: UUID | None):
        if note.pinned_at is not None:
            return note
        return await self.update(note, pinned_at=utc_now(), pinned_by_id=user_id)

    async def unpin(self, note):
        if note.pinned_at is None:
            return note
        return await self.update(note, pinned_at=None, pinned_by_id=None)

    async def react(self, note, user_id: UUID, emoji: str) -> None:
        stmt = insert(self.reactions).values(organization_id=self.org_id, note_id=note.id, user_id=user_id, emoji=emoji)
        await self.db.execute(stmt.on_conflict_do_nothing(index_elements=["note_id", "user_id", "emoji"]))
        await self.db.flush()

    async def unreact(self, note, user_id: UUID, emoji: str) -> None:
        await self.db.execute(
            delete(self.reactions).where(
                self.reactions.note_id == note.id, self.reactions.user_id == user_id, self.reactions.emoji == emoji
            )
        )
        await self.db.flush()

    async def feed(self, target_id: UUID, before: datetime | None, limit: int) -> list[FeedItem]:
        stmt = self._base_query().where(self.model.target_type == self.target_type, self.model.target_id == target_id)
        if before is not None:
            stmt = stmt.where(self.model.created_at < before)
        stmt = stmt.order_by(self.model.created_at.desc(), self.model.id.desc()).limit(limit)
        return await self.items(list((await self.db.execute(stmt)).scalars()))

    async def pinned(self, target_id: UUID) -> list[FeedItem]:
        """The pinned notes, the latest pin first."""
        stmt = (
            self._base_query()
            .where(
                self.model.target_type == self.target_type,
                self.model.target_id == target_id,
                self.model.pinned_at.is_not(None),
            )
            .order_by(self.model.pinned_at.desc(), self.model.id.desc())
        )
        return await self.items(list((await self.db.execute(stmt)).scalars()))

    async def items(self, rows: Sequence) -> list[FeedItem]:
        quotes, reactions = await self._extras(rows)
        return [note_item(row, quotes.get(replied(row)), reactions.get(row.id, [])) for row in rows]

    async def item(self, row) -> FeedItem:
        return (await self.items([row]))[0]

    async def reads(self, rows: Sequence, unreachable: Iterable[UUID] = ()) -> list[NoteRead]:
        """The rows as `NoteRead`s, each with its quote and reactions; `unreachable` goes on every one of them."""
        quotes, reactions = await self._extras(rows)
        return [
            NoteRead.model_validate(
                {
                    **{name: getattr(row, name) for name in _READ_COLUMNS},
                    "reply_to_id": replied(row),
                    "reply_to": quotes.get(replied(row)),
                    "reactions": reactions.get(row.id, []),
                    "unreachable_mention_ids": list(unreachable),
                }
            )
            for row in rows
        ]

    async def read(self, row, unreachable: Iterable[UUID] = ()) -> NoteRead:
        return (await self.reads([row], unreachable))[0]

    async def _extras(self, rows: Sequence) -> tuple[dict[UUID, NoteQuote], dict[UUID, list[FeedReaction]]]:
        quotes = await self.quotes({row.reply_to_id for row in rows} - {None})
        files = {row.reply_to_file_id for row in rows} - {None}
        if files and self.file_quotes is not None:
            quotes |= await self.file_quotes(files)
        return quotes, await self.reactions_of([row.id for row in rows])

    async def quote_of(self, row) -> NoteQuote | None:
        """What a note answers, a note or a file."""
        quotes, _ = await self._extras([row])
        return quotes.get(replied(row))

    async def quotes(self, note_ids: Collection[UUID]) -> dict[UUID, NoteQuote]:
        """The messages replied to, a deleted one too — it answers `deleted` and no words."""
        if not note_ids:
            return {}
        stmt = select(self.model).where(self.model.organization_id == self.org_id, self.model.id.in_(note_ids))
        return {row.id: quote(row) for row in (await self.db.execute(stmt)).scalars()}

    async def reactions_of(self, note_ids: Collection[UUID]) -> dict[UUID, list[FeedReaction]]:
        if self.reactions is None or not note_ids:
            return {}
        stmt = (
            select(self.reactions.note_id, self.reactions.emoji, self.reactions.user_id)
            .where(self.reactions.organization_id == self.org_id, self.reactions.note_id.in_(note_ids))
            .order_by(self.reactions.created_at, self.reactions.id)
        )
        given: dict[UUID, dict[str, list[UUID]]] = {}
        for note_id, emoji, user_id in (await self.db.execute(stmt)).all():
            given.setdefault(note_id, {}).setdefault(emoji, []).append(user_id)
        return {
            note_id: [
                FeedReaction(emoji=emoji, count=len(users[emoji]), user_ids=users[emoji])
                for emoji in sorted(users, key=_emoji_order)
            ]
            for note_id, users in given.items()
        }

    def unread_rows(self, target_ids: Collection[UUID]) -> Select:
        """`(record, at, author)` of the live notes on these records, for `count_unread`."""
        return select(
            self.model.target_id.label("record"), self.model.created_at.label("at"), self.model.user_id.label("author")
        ).where(
            self.model.organization_id == self.org_id,
            self.model.target_type == self.target_type,
            self.model.target_id.in_(target_ids),
            self.model.deleted_at.is_(None),
        )

    async def authors(self, target_id: UUID) -> set[UUID]:
        stmt = select(self.model.user_id).where(
            self.model.organization_id == self.org_id,
            self.model.target_type == self.target_type,
            self.model.target_id == target_id,
            self.model.deleted_at.is_(None),
            self.model.user_id.is_not(None),
        )
        return set((await self.db.execute(stmt.distinct())).scalars())


_READ_COLUMNS = (
    "id",
    "target_type",
    "target_id",
    "user_id",
    "parent_id",
    "reply_to_id",
    "body",
    "mention_ids",
    "pinned_at",
    "pinned_by_id",
    "created_at",
    "updated_at",
)


def _emoji_order(emoji: str) -> int:
    return REACTIONS.index(emoji) if emoji in REACTIONS else len(REACTIONS)


def replied(row) -> UUID | None:
    """The note or the file row a note answers."""
    return row.reply_to_id or getattr(row, "reply_to_file_id", None)


def file_quote(row_id: UUID, filename: str, user_id: UUID | None, *, deleted: bool) -> NoteQuote:
    """A file row of the record as a reply quotes it: its name and who put it on, `deleted` once taken off."""
    return NoteQuote(id=row_id, body=None, filename=None if deleted else filename, user_id=user_id, deleted=deleted)


def quote(row) -> NoteQuote:
    if row.deleted_at is not None:
        return NoteQuote(id=row.id, body=None, user_id=row.user_id, deleted=True)
    return NoteQuote(
        id=row.id, body=row.body[:QUOTE_LENGTH], user_id=row.user_id, mention_ids=list(row.mention_ids or ())
    )


def note_item(row, reply_to: NoteQuote | None = None, reactions: list[FeedReaction] | None = None) -> FeedItem:
    return FeedItem(
        key=note_key(row.id),
        kind=FeedKind.NOTE,
        at=row.created_at,
        actor_id=row.user_id,
        note=FeedNote(
            id=row.id,
            body=row.body,
            parent_id=row.parent_id,
            reply_to_id=replied(row),
            reply_to=reply_to,
            mention_ids=list(row.mention_ids or ()),
            reactions=reactions or [],
            pinned_at=row.pinned_at,
            pinned_by_id=row.pinned_by_id,
            updated_at=row.updated_at,
        ),
    )


def note_key(note_id: UUID) -> str:
    return f"{FeedKind.NOTE.value}:{note_id}"


class FeedReadRepository:
    """Who has read a record's feed how far, in the service's `FeedReadMixin` table."""

    def __init__(self, db: AsyncSession, org_id: UUID, model: type, target_type: str):
        self.db = db
        self.org_id = org_id
        self.model = model
        self.target_type = target_type

    async def last_read_at(self, target_id: UUID, user_id: UUID) -> datetime:
        stmt = select(self.model.last_read_at).where(
            self.model.organization_id == self.org_id,
            self.model.target_type == self.target_type,
            self.model.target_id == target_id,
            self.model.user_id == user_id,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none() or READ_EPOCH

    async def mark(self, target_id: UUID, user_id: UUID, at: datetime) -> datetime:
        """`last_read_at` becomes the later of the stored mark and `at` — it never moves back."""
        at = max(at, READ_EPOCH)
        stmt = insert(self.model).values(
            organization_id=self.org_id,
            target_type=self.target_type,
            target_id=target_id,
            user_id=user_id,
            last_read_at=at,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["organization_id", "target_type", "target_id", "user_id"],
            set_={"last_read_at": func.greatest(self.model.last_read_at, stmt.excluded.last_read_at)},
        ).returning(self.model.last_read_at)
        stored = (await self.db.execute(stmt)).scalar_one()
        await self.db.flush()
        return stored

    async def readers(self, target_id: UUID) -> list[FeedReader]:
        stmt = (
            select(self.model.user_id, self.model.last_read_at)
            .where(
                self.model.organization_id == self.org_id,
                self.model.target_type == self.target_type,
                self.model.target_id == target_id,
            )
            .order_by(self.model.last_read_at.desc())
        )
        return [
            FeedReader(user_id=user_id, last_read_at=last_read_at)
            for user_id, last_read_at in (await self.db.execute(stmt)).all()
        ]

    async def marks(self, target_ids: Collection[UUID], user_id: UUID) -> dict[UUID, datetime]:
        if not target_ids:
            return {}
        stmt = select(self.model.target_id, self.model.last_read_at).where(
            self.model.organization_id == self.org_id,
            self.model.target_type == self.target_type,
            self.model.target_id.in_(target_ids),
            self.model.user_id == user_id,
        )
        return dict((await self.db.execute(stmt)).all())


async def count_unread(
    db: AsyncSession,
    *,
    org_id: UUID,
    target_type: str,
    user_id: UUID,
    reads: type,
    rows: Sequence[Select],
) -> dict[UUID, int]:
    """Unread rows per record: `rows` are selects of `(record, at, author)` — a record's notes, its files — and a row
    counts when someone else put it there after the caller's mark (`READ_EPOCH` without one)."""
    if not rows:
        return {}
    every = (rows[0] if len(rows) == 1 else union_all(*rows)).subquery()
    mark = (
        select(reads.last_read_at)
        .where(
            reads.organization_id == org_id,
            reads.target_type == target_type,
            reads.user_id == user_id,
            reads.target_id == every.c.record,
        )
        .scalar_subquery()
    )
    stmt = (
        select(every.c.record, func.count())
        .where(every.c.author.is_distinct_from(user_id), every.c.at > func.coalesce(mark, READ_EPOCH))
        .group_by(every.c.record)
    )
    return {record: count for record, count in (await db.execute(stmt)).all()}

import logging
from collections.abc import Collection, Iterable
from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from dsystem.chat import (
    MENTION_ALL_KEY,
    MENTION_KEY,
    REACTIONS,
    TITLES,
    Mentions,
    excerpt,
    newly_named,
    readable,
    who_hears,
)
from dsystem.clients.auth import viewers
from dsystem.dependencies.auth import TokenPayload
from dsystem.exceptions import AppException
from dsystem.feed import ITEM_ADDED, ITEM_REMOVED, ITEM_UPDATED, publish_feed_change, publish_feed_read
from dsystem.models.user_replica import UserReplica
from dsystem.repositories.note import FeedReadRepository, NoteRepository, count_unread, note_key
from dsystem.schemas.feed import FeedItem, FeedPage, FeedReader, FeedReadState
from dsystem.utils.timezone import utc_now

logger = logging.getLogger(__name__)

NOTIFICATION_BODY_LENGTH = 500


class Told(dict[UUID, str]):
    """Each person a message tells, with the notification's `title_key`."""

    def by_key(self) -> dict[str, list[UUID]]:
        grouped: dict[str, list[UUID]] = {}
        for user_id, key in self.items():
            grouped.setdefault(key, []).append(user_id)
        return grouped


class RecordChat:
    """A record's notes as a chat between colleagues (2026-10-14, the owner after amoCRM's lead card; khojiakbar's
    request `2026-10-14-record-chat.md`): `<@id>`/`<@all>` in the body, a reply quoting its message, reactions, pins,
    how far each person has read, and every change on the record's live channel (`feed.*` events). A service gives it
    the record's people, who may see the record, and how its notifications are sent."""

    target_type: ClassVar[str]

    def __init__(self, db: AsyncSession, org_id: UUID, user: TokenPayload, notes: NoteRepository, reads: type):
        self.db = db
        self.org_id = org_id
        self.user = user
        self.notes = notes
        self.reads = FeedReadRepository(db, org_id, reads, notes.target_type)

    def people(self, record: Any) -> Iterable[UUID | None]:
        raise NotImplementedError

    async def can_view(self, record: Any, viewer: TokenPayload) -> bool:
        raise NotImplementedError

    async def tell(self, record: Any, told: Told, *, note: Any, params: dict, body: str) -> None:
        raise NotImplementedError

    def code(self, record: Any) -> str:
        return record.code

    def title(self, record: Any) -> str | None:
        return None

    async def heading(self, record: Any) -> str | None:
        """The record's title in «Чаты» — `title` unless it takes a read."""
        return self.title(record)

    def document_kind(self, record: Any) -> str | None:
        return None

    def unread_rows(self, target_ids: Collection[UUID]) -> list[Select]:
        return [self.notes.unread_rows(target_ids)]

    async def read_notifications(self, record: Any) -> None:
        return None

    async def check_mentions(self, body: str) -> Mentions:
        """Every `<@id>` must be a person of the organization — `422 note.mention_unknown` names the rest."""
        mentions = Mentions.of(body)
        if not mentions.user_ids:
            return mentions
        known = set(
            await self.db.scalars(
                select(UserReplica.id).where(
                    UserReplica.organization_id == self.org_id,
                    UserReplica.id.in_(mentions.user_ids),
                    UserReplica.deleted_at.is_(None),
                )
            )
        )
        unknown = [user_id for user_id in mentions.user_ids if user_id not in known]
        if unknown:
            raise AppException(
                422,
                code="note.mention_unknown",
                key="note.mention_unknown",
                message="The message names someone who is not a user of the organization",
                params={"loc": ["body"], "user_ids": [str(user_id) for user_id in unknown]},
            )
        return mentions

    async def reachable(self, record: Any, user_ids: Iterable[UUID]) -> set[UUID]:
        """Who of these may open the record: its people do; anyone else is asked of auth and checked as their own
        request would be. Nobody is reachable when auth cannot say — a message is never shown to someone it should
        not be."""
        user_ids = set(user_ids)
        people = {user_id for user_id in self.people(record) if user_id is not None}
        asked = {user_id for user_id in user_ids if user_id not in people and user_id != self.user.user_id}
        reachable = people | ({self.user.user_id} & user_ids)
        if not asked:
            return reachable
        try:
            tokens = await viewers(self.org_id, asked)
        except Exception as exc:
            logger.warning("chat_reach_unknown target=%s:%s err=%s", self.target_type, record.id, exc)
            return reachable
        for user_id, token in tokens.items():
            if await self.can_view(record, token):
                reachable.add(user_id)
        return reachable

    async def wrote(self, record: Any, note: Any) -> list[UUID]:
        """After a note is made: its people hear of it as `who_hears` says, the live channel gets the row. Answers the
        people it names who may not see the record — nobody told them."""
        mentions = Mentions.of(note.body)
        replied_to = await self._replied_author(note)
        people = list(self.people(record))
        reachable = await self.reachable(record, [*mentions.user_ids, *([replied_to] if replied_to else [])])
        told = Told(
            who_hears(
                writer=self.user.user_id,
                named=mentions.user_ids,
                everyone=mentions.everyone,
                replied_to=replied_to,
                people=people,
                reachable=reachable,
            )
        )
        await self._tell(record, note, told)
        await self._publish(record, note, ITEM_ADDED, people=people)
        return [user_id for user_id in mentions.user_ids if user_id != self.user.user_id and user_id not in reachable]

    async def edited(self, record: Any, note: Any, before: Mentions) -> list[UUID]:
        """An edit tells only whom it adds (`newly_named`); taking a name out tells nobody."""
        people = list(self.people(record))
        named, everyone = newly_named(before, Mentions.of(note.body), people)
        reachable = await self.reachable(record, named)
        told = Told()
        for user_id in named:
            if user_id in reachable and user_id != self.user.user_id:
                told[user_id] = MENTION_KEY
        for user_id in everyone:
            if user_id not in told and user_id != self.user.user_id:
                told[user_id] = MENTION_ALL_KEY
        await self._tell(record, note, told)
        await self._publish(record, note, ITEM_UPDATED, people=people)
        return [user_id for user_id in named if user_id != self.user.user_id and user_id not in reachable]

    async def removed(self, record: Any, note: Any) -> None:
        await publish_feed_change(
            self.db,
            ITEM_REMOVED,
            organization_id=self.org_id,
            target_type=self.target_type,
            target_id=record.id,
            key=note_key(note.id),
            actor_id=self.user.user_id,
            target_code=self.code(record),
            target_title=await self.heading(record),
            document_kind=self.document_kind(record),
        )

    async def react(self, record: Any, note: Any, emoji: str, *, on: bool) -> FeedItem:
        """One of the fixed set (`422 note.reaction_unknown` otherwise), once per person; no notification, the row
        again on the live channel."""
        emoji = check_reaction(emoji)
        if on:
            await self.notes.react(note, self.user.user_id, emoji)
        else:
            await self.notes.unreact(note, self.user.user_id, emoji)
        return await self._publish(record, note, ITEM_UPDATED)

    async def pin(self, record: Any, note: Any, *, on: bool) -> FeedItem:
        if on:
            await self.notes.pin(note, self.user.user_id)
        else:
            await self.notes.unpin(note)
        return await self._publish(record, note, ITEM_UPDATED)

    async def mark_read(self, record: Any, at: datetime) -> FeedReadState:
        """The caller has read the record up to `at` (never later than now, never back), its notifications of the
        record read with it, and the others on the channel see it."""
        stored = await self.reads.mark(record.id, self.user.user_id, min(at, utc_now()))
        await self.read_notifications(record)
        await publish_feed_read(
            self.db,
            organization_id=self.org_id,
            target_type=self.target_type,
            target_id=record.id,
            user_id=self.user.user_id,
            at=stored,
            document_kind=self.document_kind(record),
        )
        unread = await self.unread_counts([record.id])
        return FeedReadState(last_read_at=stored, unread_count=unread.get(record.id, 0))

    async def readers(self, record: Any) -> list[FeedReader]:
        return await self.reads.readers(record.id)

    async def pinned(self, record: Any) -> list[FeedItem]:
        return await self.notes.pinned(record.id)

    async def with_state(self, record: Any, page: FeedPage) -> FeedPage:
        page.last_read_at = await self.reads.last_read_at(record.id, self.user.user_id)
        page.unread_count = (await self.unread_counts([record.id])).get(record.id, 0)
        return page

    async def unread_counts(self, target_ids: Collection[UUID]) -> dict[UUID, int]:
        if not target_ids:
            return {}
        return await count_unread(
            self.db,
            org_id=self.org_id,
            target_type=self.target_type,
            user_id=self.user.user_id,
            reads=self.reads.model,
            rows=self.unread_rows(target_ids),
        )

    async def publish_row(self, record: Any, routing_key: str, item: FeedItem | None, key: str) -> None:
        """A row other than a note — a file, a linked task — put on, changed or taken off."""
        await publish_feed_change(
            self.db,
            routing_key,
            organization_id=self.org_id,
            target_type=self.target_type,
            target_id=record.id,
            key=key,
            item=item,
            actor_id=self.user.user_id,
            target_code=self.code(record),
            target_title=await self.heading(record),
            document_kind=self.document_kind(record),
            excerpt=item.file.filename if item is not None and item.file is not None else None,
            people=self.people(record),
        )

    async def _replied_author(self, note: Any) -> UUID | None:
        quote = await self.notes.quote_of(note)
        return quote.user_id if quote is not None and not quote.deleted else None

    async def _names(self, user_ids: Iterable[UUID | None]) -> dict[UUID, str]:
        wanted = {user_id for user_id in user_ids if user_id is not None}
        if not wanted:
            return {}
        rows = await self.db.scalars(
            select(UserReplica).where(UserReplica.organization_id == self.org_id, UserReplica.id.in_(wanted))
        )
        return {row.id: row.full_name for row in rows}

    async def _tell(self, record: Any, note: Any, told: Told) -> None:
        if not told:
            return
        names = await self._names([self.user.user_id, *(note.mention_ids or ())])
        params = {"name": self.code(record), "author": names.get(self.user.user_id, ""), "note_id": str(note.id)}
        body = readable(note.body, names)[:NOTIFICATION_BODY_LENGTH]
        await self.tell(record, told, note=note, params=params, body=body)

    async def _publish(self, record: Any, note: Any, routing_key: str, people: Iterable[UUID | None] = ()) -> FeedItem:
        item = await self.notes.item(note)
        names = await self._names(note.mention_ids or ())
        await publish_feed_change(
            self.db,
            routing_key,
            organization_id=self.org_id,
            target_type=self.target_type,
            target_id=record.id,
            key=item.key,
            item=item,
            actor_id=self.user.user_id,
            target_code=self.code(record),
            target_title=await self.heading(record),
            document_kind=self.document_kind(record),
            excerpt=excerpt(note.body, names),
            people=people or self.people(record),
            mention_ids=note.mention_ids or (),
        )
        return item


def check_reaction(emoji: str) -> str:
    emoji = "❤️" if emoji == "❤" else emoji
    if emoji not in REACTIONS:
        raise AppException(
            422,
            code="note.reaction_unknown",
            key="note.reaction_unknown",
            message="Only 👍 ✅ 👀 ❤️ 😂 🙏 are reactions",
            params={"emoji": emoji, "allowed": list(REACTIONS)},
        )
    return emoji


def title_of(key: str, params: dict) -> str:
    return TITLES[key].format(**params)

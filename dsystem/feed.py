from collections.abc import Awaitable, Callable, Iterable, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from dsystem.events.outbox import publish_event
from dsystem.events.schemas import FeedChangedV1, FeedReadV1, dump_payload
from dsystem.schemas.feed import FeedItem, FeedPage, FeedReader
from dsystem.schemas.refs import resolve_inline
from dsystem.utils.timezone import utc_now

FeedSource = Callable[[datetime | None, int], Awaitable[Sequence[FeedItem]]]

FEED_LIMIT_MAX = 100

ITEM_ADDED = "feed.item_added"
ITEM_UPDATED = "feed.item_updated"
ITEM_REMOVED = "feed.item_removed"
FEED_READ = "feed.read"


async def build_feed(sources: Iterable[FeedSource], *, before: datetime | None, limit: int) -> FeedPage:
    """Merge every source's newest rows older than `before` into one page, newest first.

    Each source is asked for `limit + 1` rows, so a source with more left is noticed. Rows sharing the page's oldest
    instant all stay on this page: the next one starts strictly before it and would otherwise skip them.
    """
    items: list[FeedItem] = []
    truncated = False
    for source in sources:
        rows = list(await source(before, limit + 1))
        truncated = truncated or len(rows) > limit
        items.extend(rows)
    items.sort(key=lambda item: (item.at, item.key), reverse=True)
    if len(items) <= limit:
        return FeedPage(items=items, next_before=None)
    edge = items[limit - 1].at
    page = [item for item in items if item.at >= edge]
    more = truncated or len(page) < len(items)
    return FeedPage(items=page, next_before=edge if more else None)


async def publish_feed_change(
    db: AsyncSession,
    routing_key: str,
    *,
    organization_id: UUID,
    target_type: str,
    target_id: UUID,
    key: str,
    item: FeedItem | None = None,
    actor_id: UUID | None = None,
    target_code: str | None = None,
    target_title: str | None = None,
    document_kind: str | None = None,
    excerpt: str | None = None,
    people: Iterable[UUID | None] = (),
    mention_ids: Iterable[UUID] = (),
) -> None:
    """Stage a `feed.*` event for the record's live channel (and crm's «Чаты»): the row as the app reads it, its
    people named in full."""
    if item is not None:
        await resolve_inline(db, item)
    payload = FeedChangedV1(
        organization_id=organization_id,
        target_type=target_type,
        target_id=target_id,
        target_code=target_code,
        target_title=target_title,
        document_kind=document_kind,
        key=key,
        item=item.model_dump(mode="json") if item is not None else None,
        actor_id=actor_id,
        at=item.at if item is not None else utc_now(),
        excerpt=excerpt,
        people=sorted({user_id for user_id in people if user_id is not None}, key=str),
        mention_ids=list(mention_ids),
    )
    publish_event(db, routing_key, dump_payload(payload), organization_id=organization_id, actor_id=actor_id)


async def publish_feed_read(
    db: AsyncSession,
    *,
    organization_id: UUID,
    target_type: str,
    target_id: UUID,
    user_id: UUID,
    at: datetime,
    document_kind: str | None = None,
) -> None:
    reader = FeedReader(user_id=user_id, last_read_at=at)
    await resolve_inline(db, reader)
    payload = FeedReadV1(
        organization_id=organization_id,
        target_type=target_type,
        target_id=target_id,
        document_kind=document_kind,
        user_id=user_id,
        user=reader.user.model_dump(mode="json") if reader.user is not None else None,
        at=at,
    )
    publish_event(db, FEED_READ, dump_payload(payload), organization_id=organization_id, actor_id=user_id)

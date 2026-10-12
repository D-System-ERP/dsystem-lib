from collections.abc import Awaitable, Callable, Iterable, Sequence
from datetime import datetime

from dsystem.schemas.feed import FeedItem, FeedPage

FeedSource = Callable[[datetime | None, int], Awaitable[Sequence[FeedItem]]]

FEED_LIMIT_MAX = 100


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

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from dsystem.feed import build_feed
from dsystem.repositories.note import note_item
from dsystem.schemas.feed import FeedEvent, FeedItem, FeedKind

START = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)


def event(minute: int, name: str = "x") -> FeedItem:
    return FeedItem(
        key=f"event:{name}{minute}",
        kind=FeedKind.EVENT,
        at=START + timedelta(minutes=minute),
        event=FeedEvent(type=name),
    )


def source(rows: list[FeedItem]):
    async def read(before, limit):
        kept = [row for row in rows if before is None or row.at < before]
        kept.sort(key=lambda row: row.at, reverse=True)
        return kept[:limit]

    return read


async def test_sources_merge_newest_first():
    page = await build_feed([source([event(1), event(5)]), source([event(3)])], before=None, limit=10)

    assert [item.at.minute for item in page.items] == [5, 3, 1]
    assert page.next_before is None


async def test_a_full_page_names_where_the_next_one_starts_and_nothing_is_read_twice():
    rows = [event(minute) for minute in range(1, 8)]
    first = await build_feed([source(rows)], before=None, limit=3)
    second = await build_feed([source(rows)], before=first.next_before, limit=3)
    third = await build_feed([source(rows)], before=second.next_before, limit=3)

    assert [item.at.minute for item in first.items] == [7, 6, 5]
    assert [item.at.minute for item in second.items] == [4, 3, 2]
    assert [item.at.minute for item in third.items] == [1]
    assert third.next_before is None


async def test_rows_sharing_the_page_edge_stay_together():
    rows = [event(5, "a"), event(4, "b"), event(4, "c"), event(1, "d")]
    first = await build_feed([source(rows[:2]), source(rows[2:])], before=None, limit=2)

    assert {item.key for item in first.items} == {"event:a5", "event:b4", "event:c4"}
    second = await build_feed([source(rows[:2]), source(rows[2:])], before=first.next_before, limit=2)
    assert [item.key for item in second.items] == ["event:d1"]


async def test_a_source_with_more_left_keeps_the_feed_open():
    page = await build_feed([source([event(minute) for minute in range(1, 5)])], before=None, limit=3)

    assert len(page.items) == 3
    assert page.next_before == START + timedelta(minutes=2)


def test_a_note_becomes_a_feed_row_by_its_author():
    author = uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        user_id=author,
        body="Ertaga yuboradi",
        parent_id=None,
        reply_to_id=None,
        created_at=START,
        updated_at=START,
    )

    item = note_item(row)

    assert item.kind == FeedKind.NOTE
    assert item.key == f"note:{row.id}"
    assert item.actor_id == author
    assert item.note.body == "Ertaga yuboradi"
    assert "actor_id" not in item.model_dump()

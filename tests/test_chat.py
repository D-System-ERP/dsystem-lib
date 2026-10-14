from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from dsystem.chat import (
    COMMENT_KEY,
    MENTION_ALL_KEY,
    MENTION_KEY,
    REPLY_KEY,
    Mentions,
    excerpt,
    newly_named,
    readable,
    who_hears,
)
from dsystem.events.schemas import FeedChangedV1, FeedReadV1, contract_for
from dsystem.exceptions import AppException
from dsystem.record_chat import Told, check_reaction
from dsystem.repositories.note import note_item, quote

AT = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)


def test_mentions_are_read_from_the_body_once_each_in_order():
    ali, vali = uuid4(), uuid4()
    body = f"<@{ali}> va <@{vali}>, <@{ali}> yana; <@all>! <@nobody> <@{str(vali).upper()}>"

    mentions = Mentions.of(body)

    assert mentions.user_ids == (ali, vali)
    assert mentions.everyone is True
    assert Mentions.of("oddiy xabar") == Mentions((), False)
    assert Mentions.of(None).user_ids == ()


def test_each_person_hears_once_and_the_first_reason_wins():
    writer, named, replied, member, outsider, other = (uuid4() for _ in range(6))

    told = who_hears(
        writer=writer,
        named=[named, writer, outsider],
        everyone=False,
        replied_to=replied,
        people=[writer, named, member, None],
        reachable={writer, named, replied, member},
    )

    assert told == {named: MENTION_KEY, replied: REPLY_KEY, member: COMMENT_KEY}
    assert outsider not in told and other not in told


def test_all_makes_every_person_of_the_record_loud():
    writer, named, member = uuid4(), uuid4(), uuid4()

    told = who_hears(
        writer=writer,
        named=[named],
        everyone=True,
        replied_to=None,
        people=[named, member, writer],
        reachable={named, member, writer},
    )

    assert told == {named: MENTION_KEY, member: MENTION_ALL_KEY}


def test_an_edit_tells_only_whom_it_adds():
    kept, added, member = uuid4(), uuid4(), uuid4()
    before = Mentions((kept,), False)

    named, everyone = newly_named(before, Mentions((kept, added), True), [kept, member, None])
    assert named == [added]
    assert everyone == [member]

    assert newly_named(Mentions((kept, added), True), Mentions((kept,), True), [member]) == ([], [])


def test_a_mention_reads_as_the_persons_name():
    ali = uuid4()
    body = f"<@{ali}>   ertaga\n<@all> <@{uuid4()}>"

    assert readable(body, {ali: "Valiyev Ali"}).startswith("@Valiyev Ali")
    assert excerpt(body, {ali: "Valiyev Ali"}) == "@Valiyev Ali ertaga @all @"
    assert len(excerpt("x" * 500)) == 200


def test_only_the_fixed_set_are_reactions():
    assert check_reaction("👍") == "👍"
    assert check_reaction("❤") == "❤️"
    with pytest.raises(AppException) as refused:
        check_reaction("🔥")
    assert refused.value.status_code == 422
    assert refused.value.code == "note.reaction_unknown"


def test_a_deleted_message_is_quoted_without_its_words():
    author = uuid4()
    named = uuid4()
    live = SimpleNamespace(id=uuid4(), user_id=author, body="a" * 300, mention_ids=[named], deleted_at=None)
    gone = SimpleNamespace(id=uuid4(), user_id=author, body="sir", mention_ids=[], deleted_at=AT)

    assert len(quote(live).body) == 200 and quote(live).deleted is False and quote(live).mention_ids == [named]
    assert quote(gone).body is None and quote(gone).deleted is True and quote(gone).user_id == author


def test_a_note_row_carries_its_quote_reactions_mentions_and_pin():
    pinner, named = uuid4(), uuid4()
    row = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        body=f"<@{named}> qarang",
        parent_id=None,
        reply_to_id=uuid4(),
        mention_ids=[named],
        pinned_at=AT,
        pinned_by_id=pinner,
        created_at=AT,
        updated_at=AT,
    )
    replied = SimpleNamespace(id=row.reply_to_id, user_id=uuid4(), body="savol", mention_ids=[], deleted_at=None)

    item = note_item(row, quote(replied), [])

    assert item.note.reply_to.body == "savol"
    assert item.note.mention_ids == [named]
    assert item.note.pinned_by_id == pinner
    dumped = item.model_dump(mode="json")
    assert "mention_ids" not in dumped["note"] and dumped["note"]["mentions"] == []
    assert dumped["note"]["reply_to"]["deleted"] is False


def test_told_groups_people_by_their_title_key():
    a, b, c = uuid4(), uuid4(), uuid4()
    told = Told({a: MENTION_KEY, b: COMMENT_KEY, c: MENTION_KEY})

    assert told.by_key() == {MENTION_KEY: [a, c], COMMENT_KEY: [b]}


def test_feed_events_are_registered_contracts():
    for key in ("feed.item_added", "feed.item_updated", "feed.item_removed"):
        assert contract_for(key) is FeedChangedV1
    assert contract_for("feed.read") is FeedReadV1
    payload = FeedChangedV1(
        organization_id=uuid4(), target_type="task", target_id=uuid4(), key="note:x", at=AT
    ).model_dump(mode="json")
    assert payload["item"] is None and payload["people"] == [] and payload["excluded_session_ids"] == []

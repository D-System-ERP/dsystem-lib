import re
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

MENTION = re.compile(r"<@(all|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})>")

REACTIONS: tuple[str, ...] = ("👍", "✅", "👀", "❤️", "😂", "🙏")

READ_EPOCH = datetime(2026, 10, 13, 19, 0, tzinfo=UTC)
"""Where a person who never opened a record has read it up to: the day the chat came (2026-10-14, Tashkent).
Without it every record written on before would open as unread."""

QUOTE_LENGTH = 200
EXCERPT_LENGTH = 200

MENTION_KEY = "notification.mention"
REPLY_KEY = "notification.reply"
MENTION_ALL_KEY = "notification.mention_all"
COMMENT_KEY = "notification.new_comment"

TITLES = {
    MENTION_KEY: "{author} mentioned you in {name}",
    REPLY_KEY: "{author} replied to you in {name}",
    MENTION_ALL_KEY: "{author} wrote to everyone in {name}",
    COMMENT_KEY: "{name}: new comment",
}


@dataclass(frozen=True)
class Mentions:
    """Who a message's body names: `<@{user_id}>` each, `<@all>` the record's people."""

    user_ids: tuple[UUID, ...]
    everyone: bool

    @classmethod
    def of(cls, body: str | None) -> "Mentions":
        named: list[UUID] = []
        everyone = False
        for token in MENTION.findall(body or ""):
            if token == "all":
                everyone = True
                continue
            user_id = UUID(token)
            if user_id not in named:
                named.append(user_id)
        return cls(tuple(named), everyone)


def readable(body: str | None, names: Mapping[UUID, str]) -> str:
    """The body with each mention as `@Name` — for a notification's text and an inbox line."""

    def name(match: re.Match) -> str:
        token = match.group(1)
        if token == "all":
            return "@all"
        return f"@{names.get(UUID(token)) or ''}".rstrip()

    return MENTION.sub(name, body or "")


def excerpt(body: str | None, names: Mapping[UUID, str] | None = None, length: int = EXCERPT_LENGTH) -> str:
    return " ".join(readable(body, names or {}).split())[:length]


def who_hears(
    *,
    writer: UUID | None,
    named: Iterable[UUID],
    everyone: bool,
    replied_to: UUID | None,
    people: Iterable[UUID | None],
    reachable: Collection[UUID],
) -> dict[UUID, str]:
    """Each person a message tells, with the notification's `title_key` — one per person, the first that fits wins:
    named, then the author of the message answered, then everyone with `<@all>`, then the record's other people
    quietly. The writer is never told, and nobody outside `reachable`."""
    told: dict[UUID, str] = {}

    def tell(user_id: UUID | None, key: str) -> None:
        if user_id is None or user_id == writer or user_id in told or user_id not in reachable:
            return
        told[user_id] = key

    for user_id in named:
        tell(user_id, MENTION_KEY)
    tell(replied_to, REPLY_KEY)
    people = [user_id for user_id in people if user_id is not None]
    if everyone:
        for user_id in people:
            tell(user_id, MENTION_ALL_KEY)
    for user_id in people:
        tell(user_id, COMMENT_KEY)
    return told


def newly_named(before: Mentions, after: Mentions, people: Iterable[UUID | None]) -> tuple[list[UUID], list[UUID]]:
    """An edit tells only whom it adds: the people its new body names that the old one did not, and with a new
    `<@all>` the record's people the old body did not reach. Taking a name out tells nobody."""
    named = [user_id for user_id in after.user_ids if user_id not in before.user_ids]
    everyone: list[UUID] = []
    if after.everyone and not before.everyone:
        everyone = [user_id for user_id in people if user_id is not None and user_id not in before.user_ids]
    return named, everyone

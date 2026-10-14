from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field

from dsystem.schemas.base import AppSchema
from dsystem.schemas.refs import Inline, UserBrief


class FeedKind(StrEnum):
    NOTE = "note"
    FILE = "file"
    EVENT = "event"
    LINK = "link"
    ACTIVITY = "activity"
    TASK = "task"


UNREAD_KINDS = frozenset({FeedKind.NOTE, FeedKind.FILE})


class NoteQuote(AppSchema):
    """The message a reply answers, as the reply quotes it — there even when it is pages back in the feed."""

    id: UUID
    body: str | None = Field(None, description="Its first 200 characters; null once it was deleted")
    user_id: UUID | None = Field(None, exclude=True)
    user: Annotated[UserBrief | None, Inline("user_id")] = None
    mention_ids: list[UUID] = Field(default_factory=list, exclude=True)
    mentions: Annotated[list[UserBrief], Inline("mention_ids")] = Field(
        default_factory=list, description="The people its body names"
    )
    deleted: bool = False


class FeedReaction(AppSchema):
    emoji: str
    count: int
    user_ids: list[UUID] = Field(default_factory=list, exclude=True)
    users: Annotated[list[UserBrief], Inline("user_ids")] = Field(
        default_factory=list, description="Who gave it, the first first"
    )


class FeedNote(AppSchema):
    id: UUID
    body: str = Field(..., description="`<@{user_id}>` names a person, `<@all>` the record's people")
    parent_id: UUID | None = None
    reply_to_id: UUID | None = None
    reply_to: NoteQuote | None = Field(None, description="The message this one answers")
    mention_ids: list[UUID] = Field(default_factory=list, exclude=True)
    mentions: Annotated[list[UserBrief], Inline("mention_ids")] = Field(
        default_factory=list, description="The people the body names, by their current names"
    )
    reactions: list[FeedReaction] = Field(default_factory=list, description="In the fixed order of the emoji set")
    pinned_at: datetime | None = None
    pinned_by_id: UUID | None = Field(None, exclude=True)
    pinned_by: Annotated[UserBrief | None, Inline("pinned_by_id")] = None
    updated_at: datetime


class FeedFile(AppSchema):
    id: UUID = Field(..., description="The record's attachment row — what a detach takes")
    file_id: UUID
    filename: str
    url: str = Field(..., description="Signed download link, valid for one hour")
    content_type: str | None = None
    size_bytes: int | None = None


class FeedEvent(AppSchema):
    type: str = Field(..., description="The owning service's event type, e.g. a document's `confirmed`")
    from_value: str | None = None
    to_value: str | None = None
    payload: dict | None = None


class FeedLink(AppSchema):
    target_type: str
    target_id: UUID
    target_code: str | None = None
    target_kind: str | None = None
    target_stage: str | None = None
    target_direction: str | None = None
    note: str | None = None


class FeedActivity(AppSchema):
    """An activity tied to the record — a call, a meeting made from its chat."""

    id: UUID
    code: str
    kind: str
    activity_type: str | None = Field(None, description="The organization's own activity type, by name")
    subject: str | None = None
    scheduled_at: datetime
    status: str
    assignee_id: UUID | None = Field(None, exclude=True)
    assignee: Annotated[UserBrief | None, Inline("assignee_id")] = None


class FeedBoard(AppSchema):
    id: UUID
    name: str
    color: str | None = None


class FeedTask(AppSchema):
    """A board task tied to the record."""

    id: UUID
    code: str | None = None
    title: str
    status: str
    board: FeedBoard | None = None
    ends_at: datetime | None = None
    assignee_ids: list[UUID] = Field(default_factory=list, exclude=True)
    assignees: Annotated[list[UserBrief], Inline("assignee_ids")] = Field(default_factory=list)


class FeedItem(AppSchema):
    """One row of a record's feed; exactly the part named by `kind` is filled."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "note:d6e7f809-192a-4b3c-8d4e-5f6071829304",
                "kind": "note",
                "at": "2026-10-12T09:00:00Z",
                "note": {
                    "id": "d6e7f809-192a-4b3c-8d4e-5f6071829304",
                    "body": "<@1c2d3e4f-5061-4728-893a-4b5c6d7e8f90> yetkazib beruvchi ertaga yuboradi",
                    "parent_id": None,
                    "reply_to_id": None,
                    "reply_to": None,
                    "mentions": [
                        {
                            "id": "1c2d3e4f-5061-4728-893a-4b5c6d7e8f90",
                            "first_name": "Ali",
                            "last_name": "Valiyev",
                            "username": "ali",
                            "email": None,
                            "picture_url": None,
                        }
                    ],
                    "reactions": [{"emoji": "👍", "count": 1, "users": []}],
                    "pinned_at": None,
                    "pinned_by": None,
                    "updated_at": "2026-10-12T09:00:00Z",
                },
            }
        }
    )

    key: str = Field(..., description="Unique across the feed: `<kind>:<id>`")
    kind: FeedKind
    at: datetime
    actor_id: UUID | None = Field(None, exclude=True)
    actor: Annotated[UserBrief | None, Inline("actor_id")] = Field(None, description="Who did it; null for the system")
    note: FeedNote | None = None
    file: FeedFile | None = None
    event: FeedEvent | None = None
    link: FeedLink | None = None
    activity: FeedActivity | None = None
    task: FeedTask | None = None


class FeedPage(AppSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "key": "event:60718293-a4b5-4c6d-813b-5d6e7f809192",
                        "kind": "event",
                        "at": "2026-10-12T09:30:00Z",
                        "event": {"type": "confirmed", "from_value": "draft", "to_value": "confirmed", "payload": None},
                    },
                    {
                        "key": "note:d6e7f809-192a-4b3c-8d4e-5f6071829304",
                        "kind": "note",
                        "at": "2026-10-12T09:00:00Z",
                        "note": {
                            "id": "d6e7f809-192a-4b3c-8d4e-5f6071829304",
                            "body": "Yetkazib beruvchi ertaga yuboradi",
                            "parent_id": None,
                            "reply_to_id": None,
                            "reply_to": None,
                            "mentions": [],
                            "reactions": [],
                            "pinned_at": None,
                            "pinned_by": None,
                            "updated_at": "2026-10-12T09:00:00Z",
                        },
                    },
                ],
                "next_before": "2026-10-12T09:00:00Z",
                "last_read_at": "2026-10-12T08:00:00Z",
                "unread_count": 1,
            }
        }
    )

    items: list[FeedItem] = Field(..., description="Newest first")
    next_before: datetime | None = Field(None, description="Pass as `before` for older rows; null when none are left")
    last_read_at: datetime | None = Field(
        None, description="How far the caller has read this record — notes and files by others after it are unread"
    )
    unread_count: int = Field(0, description="Notes and files by others after `last_read_at`, over the whole record")


class FeedReadBody(AppSchema):
    model_config = ConfigDict(json_schema_extra={"example": {"at": "2026-10-14T09:00:00Z"}})

    at: datetime = Field(..., description="The newest row on screen; the stored mark never moves back")


class FeedReadState(AppSchema):
    model_config = ConfigDict(
        json_schema_extra={"example": {"last_read_at": "2026-10-14T09:00:00Z", "unread_count": 0}}
    )

    last_read_at: datetime
    unread_count: int


class FeedReader(AppSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user": {
                    "id": "1c2d3e4f-5061-4728-893a-4b5c6d7e8f90",
                    "first_name": "Ali",
                    "last_name": "Valiyev",
                    "username": "ali",
                    "email": None,
                    "picture_url": None,
                },
                "last_read_at": "2026-10-14T09:00:00Z",
            }
        }
    )

    user_id: UUID | None = Field(None, exclude=True)
    user: Annotated[UserBrief | None, Inline("user_id")] = None
    last_read_at: datetime

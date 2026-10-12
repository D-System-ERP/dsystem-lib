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


class FeedNote(AppSchema):
    id: UUID
    body: str
    parent_id: UUID | None = None
    reply_to_id: UUID | None = None
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
                    "body": "Yetkazib beruvchi ertaga yuboradi",
                    "parent_id": None,
                    "reply_to_id": None,
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


class FeedPage(AppSchema):
    items: list[FeedItem] = Field(..., description="Newest first")
    next_before: datetime | None = Field(None, description="Pass as `before` for older rows; null when none are left")

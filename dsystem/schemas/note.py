from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import ConfigDict, Field

from dsystem.schemas.base import AppSchema
from dsystem.schemas.refs import Inline, UserBrief


class NoteCreate(AppSchema):
    model_config = ConfigDict(json_schema_extra={"example": {"body": "Yetkazib beruvchi ertaga yuboradi"}})

    body: str = Field(..., min_length=1, max_length=10000)
    parent_id: UUID | None = Field(None, description="The note this one is nested under")
    reply_to_id: UUID | None = Field(None, description="The note this one answers")


class NoteUpdate(AppSchema):
    model_config = ConfigDict(json_schema_extra={"example": {"body": "Yetkazib beruvchi dushanba yuboradi"}})

    body: str = Field(..., min_length=1, max_length=10000)


class NoteRead(AppSchema):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "d6e7f809-192a-4b3c-8d4e-5f6071829304",
                "target_type": "document",
                "target_id": "e7f80919-2a3b-4c4d-9e5f-60718293a4b5",
                "parent_id": None,
                "reply_to_id": None,
                "body": "Yetkazib beruvchi ertaga yuboradi",
                "created_at": "2026-10-12T09:00:00Z",
                "updated_at": "2026-10-12T09:00:00Z",
            }
        }
    )

    id: UUID
    target_type: str
    target_id: UUID
    user_id: UUID | None = Field(None, exclude=True)
    user: Annotated[UserBrief | None, Inline("user_id")] = None
    parent_id: UUID | None
    reply_to_id: UUID | None
    body: str
    created_at: datetime
    updated_at: datetime

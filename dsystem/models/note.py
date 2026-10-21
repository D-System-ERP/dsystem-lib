from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class NoteMixin:
    """A message left on any record of the service, found by `target_type` + `target_id`.

    One table per service holds the notes of all its records: a task's, a document's, a payment's. The record itself
    is never touched, so nothing about the record's version, status or history changes when somebody writes.
    """

    organization_id: Mapped[UUID]
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[UUID]
    user_id: Mapped[UUID | None]
    body: Mapped[str] = mapped_column(Text)
    mention_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), default=list, server_default=text("'{}'::uuid[]")
    )
    pinned_at: Mapped[datetime | None]
    pinned_by_id: Mapped[UUID | None]
    reply_to_file_id: Mapped[UUID | None]

    @declared_attr
    def parent_id(cls) -> Mapped[UUID | None]:
        return mapped_column(ForeignKey(f"{cls.__tablename__}.id", ondelete="CASCADE"))

    @declared_attr
    def reply_to_id(cls) -> Mapped[UUID | None]:
        return mapped_column(ForeignKey(f"{cls.__tablename__}.id", ondelete="SET NULL"))

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            Index(
                f"ix_{cls.__tablename__}_target_created", "organization_id", "target_type", "target_id", "created_at"
            ),
        )


class NoteReactionMixin:
    """One person's emoji on a note: each person gives one of each emoji, several different ones if they like."""

    __note_table__: str = "notes"

    organization_id: Mapped[UUID]
    user_id: Mapped[UUID]
    emoji: Mapped[str] = mapped_column(String(16))

    @declared_attr
    def note_id(cls) -> Mapped[UUID]:
        return mapped_column(ForeignKey(f"{cls.__note_table__}.id", ondelete="CASCADE"), index=True)

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (UniqueConstraint("note_id", "user_id", "emoji", name=f"uq_{cls.__tablename__}_note_user_emoji"),)


class FeedReadMixin:
    """How far a person has read a record's feed. A missing row means "up to `dsystem.chat.READ_EPOCH`"."""

    organization_id: Mapped[UUID]
    user_id: Mapped[UUID]
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[UUID]
    last_read_at: Mapped[datetime]

    @declared_attr.directive
    def __table_args__(cls) -> tuple:
        return (
            UniqueConstraint(
                "organization_id", "target_type", "target_id", "user_id", name=f"uq_{cls.__tablename__}_target_user"
            ),
            Index(f"ix_{cls.__tablename__}_user", "organization_id", "user_id", "target_type"),
        )

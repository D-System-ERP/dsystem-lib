from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
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

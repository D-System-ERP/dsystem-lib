from uuid import UUID

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from dsystem.models.base import SoftDeleteModel


class LookupBase(SoftDeleteModel):
    """Name-only reference lists (``kind`` + ``name``) shared by every service.

    Each service declares ``class Lookup(LookupBase): __tablename__ = "lookups"``
    and its own ``kind`` vocabulary; FK columns point at ``lookups.id`` and the
    repository checks the ``kind`` matches (``lookup.kind_mismatch``).
    """

    __abstract__ = True

    organization_id: Mapped[UUID] = mapped_column(index=True)
    kind: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[UUID | None] = mapped_column(index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    @declared_attr.directive
    def __table_args__(cls):
        table = cls.__tablename__
        return (
            Index(
                f"uq_{table}_org_kind_name",
                "organization_id",
                "kind",
                "name",
                unique=True,
                postgresql_where="deleted_at IS NULL",
            ),
            Index(f"ix_{table}_org_kind_position", "organization_id", "kind", "position"),
        )

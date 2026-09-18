from uuid import UUID

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from dsystem.models.base import ReferenceModel


class UserReplica(ReferenceModel):
    __tablename__ = "user_replicas"

    organization_id: Mapped[UUID] = mapped_column(index=True)
    email: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(150))
    last_name: Mapped[str | None] = mapped_column(String(150))
    middle_name: Mapped[str | None] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(20))
    picture_url: Mapped[str | None] = mapped_column(String(1000))
    role_id: Mapped[UUID | None] = mapped_column(index=True)
    team_id: Mapped[UUID | None] = mapped_column(index=True)
    default_legal_entity_id: Mapped[UUID | None]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.last_name, self.first_name, self.middle_name) if p) or self.email

from uuid import UUID

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dsystem.models.base import ReferenceModel


class LegalEntityReplica(ReferenceModel):
    """``auth.legal_entities`` mirror — the firm a document or payment is issued by.

    ``code_prefix`` feeds document numbering (``ABC-SA10001``); ``is_default``
    is the tenant fallback when the user has no default legal entity.
    """

    __tablename__ = "legal_entity_replicas"

    organization_id: Mapped[UUID] = mapped_column(index=True)
    code: Mapped[str] = mapped_column(String(20))
    code_prefix: Mapped[str | None] = mapped_column(String(10))
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str | None] = mapped_column(String(100))
    inn: Mapped[str | None] = mapped_column(String(64))
    currency_code: Mapped[str] = mapped_column(String(3), default="UZS")
    country: Mapped[str] = mapped_column(String(2), default="UZ")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    bank_accounts: Mapped[list | None] = mapped_column(JSONB)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


LEGAL_ENTITY_REPLICA_FIELDS: tuple[str, ...] = (
    "code",
    "code_prefix",
    "name",
    "short_name",
    "inn",
    "currency_code",
    "country",
    "is_default",
    "is_active",
    "bank_accounts",
)

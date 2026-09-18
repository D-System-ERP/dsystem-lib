from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from dsystem.models.base import ReferenceModel


class PartnerReplica(ReferenceModel):
    """``crm.partners`` as other services see it — kept in sync by ``partner.*`` events.

    Only what documents and payments need to validate and display; the full
    partner (contacts, notes) lives in crm. ``is_deleted`` rather than a hard
    delete so historical documents still resolve their partner.
    """

    __tablename__ = "partner_replicas"

    organization_id: Mapped[UUID] = mapped_column(index=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    is_company: Mapped[bool] = mapped_column(Boolean, default=True)
    is_customer: Mapped[bool] = mapped_column(Boolean, default=True)
    is_vendor: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(10), default="active")
    inn: Mapped[str | None] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str | None] = mapped_column(String(2))
    currency_code: Mapped[str | None] = mapped_column(String(3))
    price_list_id: Mapped[UUID | None]
    customer_payment_term_id: Mapped[UUID | None]
    vendor_payment_term_id: Mapped[UUID | None]
    payment_terms: Mapped[list | None] = mapped_column(JSONB)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    balance_base: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"))
    addresses: Mapped[list | None] = mapped_column(JSONB)
    bank_accounts: Mapped[list | None] = mapped_column(JSONB)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)


PARTNER_REPLICA_FIELDS: tuple[str, ...] = (
    "code",
    "name",
    "is_company",
    "is_customer",
    "is_vendor",
    "status",
    "inn",
    "phone",
    "email",
    "language",
    "currency_code",
    "price_list_id",
    "customer_payment_term_id",
    "vendor_payment_term_id",
    "payment_terms",
    "credit_limit",
    "addresses",
    "bank_accounts",
)

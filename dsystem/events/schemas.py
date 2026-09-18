"""Event payload contracts (``data`` inside the envelope), version 1.

Publishers build payloads with these models (``model_dump(mode="json")``) and
consumers validate with ``validate_payload``; the contract test in each service
asserts both sides use the same model. Unknown fields are ignored so a newer
producer never breaks an older consumer.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventPayload(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True)


class UserV1(EventPayload):
    id: UUID
    organization_id: UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    phone: str | None = None
    picture_url: str | None = None
    role_id: UUID | None = None
    team_id: UUID | None = None
    default_legal_entity_id: UUID | None = None
    is_active: bool = True
    is_superuser: bool = False


class UserDeletedV1(EventPayload):
    id: UUID
    organization_id: UUID | None = None


class UserSessionRevokedV1(EventPayload):
    recipient_user_ids: list[UUID]
    reason: str


class OrganizationV1(EventPayload):
    id: UUID
    name: str
    slug: str
    timezone: str
    base_currency_code: str = "UZS"
    fiscal_year_start_month: int = 1
    price_decimal_places: int = 2
    qty_decimal_places: int = 3
    lot_strategy: str = "manual"
    costing_method: str = "average"
    require_barcode_scan: bool = False
    enforce_min_price: bool = False
    enforce_credit_limit: bool = False
    settings: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class BankAccountV1(EventPayload):
    id: UUID
    bank_name: str
    bank_code: str
    account: str
    correspondent_account: str | None = None
    account_holder_name: str | None = None
    currency_code: str = "UZS"
    is_primary: bool = False
    is_active: bool = True


class LegalEntityV1(EventPayload):
    id: UUID
    organization_id: UUID
    code: str
    code_prefix: str | None = None
    name: str
    short_name: str | None = None
    legal_form: str = "llc"
    inn: str | None = None
    requisites: dict[str, Any] | None = None
    currency_code: str = "UZS"
    country: str = "UZ"
    is_default: bool = False
    is_active: bool = True
    parent_id: UUID | None = None
    bank_accounts: list[BankAccountV1] = Field(default_factory=list)


class LegalEntityDeletedV1(EventPayload):
    id: UUID
    organization_id: UUID | None = None


class PaymentTermLineV1(EventPayload):
    position: int
    portion_percent: Decimal
    days: int = 0
    trigger: str = "invoice_date"


class PaymentTermV1(EventPayload):
    id: UUID
    name: str
    days: int = 0
    penalty_percent_per_day: Decimal = Decimal("0")
    lines: list[PaymentTermLineV1] = Field(default_factory=list)


class PartnerAddressV1(EventPayload):
    id: UUID
    type: str
    label: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    zip: str | None = None
    is_default: bool = False


class PartnerContactV1(EventPayload):
    id: UUID
    name: str
    phone: str | None = None
    email: str | None = None
    is_primary: bool = False


class PartnerV1(EventPayload):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    is_company: bool = True
    is_customer: bool = True
    is_vendor: bool = False
    status: str = "active"
    inn: str | None = None
    requisites: dict[str, Any] | None = None
    language: str | None = None
    phone: str | None = None
    phone2: str | None = None
    email: str | None = None
    telegram: str | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    zip: str | None = None
    currency_code: str | None = None
    price_list_id: UUID | None = None
    credit_limit: Decimal | None = None
    group_id: UUID | None = None
    group_name: str | None = None
    industry_id: UUID | None = None
    industry_name: str | None = None
    customer_payment_term_id: UUID | None = None
    vendor_payment_term_id: UUID | None = None
    payment_terms: list[PaymentTermV1] = Field(default_factory=list)
    bank_accounts: list[BankAccountV1] = Field(default_factory=list)
    addresses: list[PartnerAddressV1] = Field(default_factory=list)
    contacts: list[PartnerContactV1] = Field(default_factory=list)
    is_deleted: bool = False


class PartnerDeletedV1(EventPayload):
    id: UUID
    organization_id: UUID | None = None


class NotificationCreatedV1(EventPayload):
    id: UUID
    organization_id: UUID
    title: str
    body: str | None = None
    kind: str
    target_type: str | None = None
    target_id: UUID | None = None
    target_code: str | None = None
    action: str | None = None
    actor_id: UUID | None = None
    audience: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class CurrencyRateUpdatedV1(EventPayload):
    organization_id: UUID
    code: str
    rate_date: date
    rate: Decimal
    source: str | None = None
    is_base: bool = False


CONTRACTS: dict[str, type[EventPayload]] = {
    "user.created": UserV1,
    "user.updated": UserV1,
    "user.deleted": UserDeletedV1,
    "user.session_revoked": UserSessionRevokedV1,
    "organization.created": OrganizationV1,
    "organization.updated": OrganizationV1,
    "legal_entity.created": LegalEntityV1,
    "legal_entity.updated": LegalEntityV1,
    "legal_entity.deleted": LegalEntityDeletedV1,
    "partner.created": PartnerV1,
    "partner.updated": PartnerV1,
    "partner.deleted": PartnerDeletedV1,
    "notification.created": NotificationCreatedV1,
    "currency_rate.updated": CurrencyRateUpdatedV1,
}


def contract_for(routing_key: str) -> type[EventPayload] | None:
    return CONTRACTS.get(routing_key)


def validate_payload(routing_key: str, data: dict) -> EventPayload | dict:
    """Validate ``data`` against the contract for ``routing_key``; unknown keys pass through untouched."""
    model = CONTRACTS.get(routing_key)
    if model is None:
        return data
    return model.model_validate(data)


def dump_payload(model: EventPayload) -> dict:
    return model.model_dump(mode="json")

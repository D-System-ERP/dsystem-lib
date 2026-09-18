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


class PaymentTermUpdatedV1(EventPayload):
    id: UUID
    organization_id: UUID
    name: str
    days: int = 0
    penalty_percent_per_day: Decimal = Decimal("0")
    lines: list[PaymentTermLineV1] = Field(default_factory=list)
    partner_ids: list[UUID] = Field(default_factory=list)


class ProductV1(EventPayload):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    type: str
    sku: str | None = None
    barcode: str | None = None
    category_id: UUID | None = None
    category_name: str | None = None
    uom_id: UUID
    uom_name: str
    tracking: str = "lot"
    has_expiry: bool = False
    unit_price: Decimal = Decimal("0")
    currency_code: str | None = None
    cost_price: Decimal = Decimal("0")
    is_active: bool = True


class ProductDeletedV1(EventPayload):
    id: UUID
    organization_id: UUID | None = None


class WarehouseV1(EventPayload):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    parent_id: UUID | None = None
    is_group: bool = False
    is_active: bool = True


class WarehouseDeletedV1(EventPayload):
    id: UUID
    organization_id: UUID | None = None


class UomV1(EventPayload):
    id: UUID
    organization_id: UUID
    name: str
    short_name: str
    category_id: UUID
    type: str
    factor: Decimal
    rounding: Decimal


class PriceListV1(EventPayload):
    id: UUID
    organization_id: UUID
    name: str
    currency_code: str
    kind: str
    is_active: bool = True


class StockMovedV1(EventPayload):
    id: UUID
    organization_id: UUID
    product_id: UUID
    product_name: str
    warehouse_id: UUID
    warehouse_name: str
    lot_id: UUID | None = None
    lot_number: str | None = None
    document_id: UUID
    document_code: str | None = None
    document_kind: str
    document_stage: str
    line_id: UUID | None = None
    direction: str
    reason: str
    quantity: Decimal
    unit_cost: Decimal
    value: Decimal
    occurred_at: datetime
    document_date: datetime
    reverses_id: UUID | None = None
    reversed_by_id: UUID | None = None


class StockReservedV1(EventPayload):
    organization_id: UUID
    product_id: UUID
    warehouse_id: UUID
    document_id: UUID
    quantity: Decimal


class StockRevaluedV1(EventPayload):
    organization_id: UUID
    product_id: UUID
    warehouse_id: UUID
    lot_id: UUID
    old_unit_cost: Decimal
    new_unit_cost: Decimal
    delta_value: Decimal
    sold_share_delta: Decimal = Decimal("0")
    document_id: UUID


class StockSnapshotItemV1(EventPayload):
    product_id: UUID
    warehouse_id: UUID
    quantity: Decimal
    reserved_quantity: Decimal
    cost_price: Decimal
    value: Decimal


class StockSnapshotTakenV1(EventPayload):
    organization_id: UUID
    snapshot_date: date
    part: int = 1
    of: int = 1
    items: list[StockSnapshotItemV1] = Field(default_factory=list)


class CostPriceChangedV1(EventPayload):
    organization_id: UUID
    product_id: UUID
    warehouse_id: UUID | None = None
    old: Decimal
    new: Decimal
    document_id: UUID | None = None


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
    "payment_term.updated": PaymentTermUpdatedV1,
    "product.created": ProductV1,
    "product.updated": ProductV1,
    "product.deleted": ProductDeletedV1,
    "warehouse.created": WarehouseV1,
    "warehouse.updated": WarehouseV1,
    "warehouse.deleted": WarehouseDeletedV1,
    "uom.created": UomV1,
    "uom.updated": UomV1,
    "price_list.updated": PriceListV1,
    "stock.moved": StockMovedV1,
    "stock.reserved": StockReservedV1,
    "stock.unreserved": StockReservedV1,
    "stock.revalued": StockRevaluedV1,
    "stock.snapshot_taken": StockSnapshotTakenV1,
    "cost_price.changed": CostPriceChangedV1,
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

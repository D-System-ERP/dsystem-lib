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
    currency_codes: list[str] = Field(default_factory=lambda: ["UZS"])
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


class OpportunityWonItemV1(EventPayload):
    product_id: UUID
    product_name: str | None = None
    quantity: Decimal
    uom_id: UUID | None = None
    uom_name: str | None = None
    unit_price: Decimal | None = None


class OpportunityV1(EventPayload):
    opportunity_id: UUID
    organization_id: UUID
    code: str
    name: str | None = None
    partner_id: UUID | None = None
    partner_name: str | None = None
    contact: dict[str, Any] | None = None
    stage_id: UUID | None = None
    stage_name: str | None = None
    stage_position: int = 0
    probability_percent: Decimal = Decimal("0")
    currency_code: str | None = None
    expected_amount: Decimal = Decimal("0")
    expected_amount_base: Decimal = Decimal("0")
    expected_close_date: date | None = None
    priority: int = 0
    assignee_id: UUID | None = None
    team_id: UUID | None = None
    source_id: UUID | None = None
    source_name: str | None = None
    status: str = "open"


class OpportunityWonV1(OpportunityV1):
    won_at: datetime | None = None
    items: list[OpportunityWonItemV1] = Field(default_factory=list)


class OpportunityLostV1(OpportunityV1):
    lost_at: datetime | None = None
    lost_reason_id: UUID | None = None
    lost_reason_name: str | None = None
    lost_note: str | None = None


class DocumentLineV1(EventPayload):
    id: UUID
    role: str
    line_no: int
    product_id: UUID
    product_name: str
    uom_id: UUID
    uom_name: str
    warehouse_id: UUID | None = None
    warehouse_name: str | None = None
    to_warehouse_id: UUID | None = None
    quantity: Decimal
    base_quantity: Decimal
    fulfilled_quantity: Decimal = Decimal("0")
    unit_price: Decimal = Decimal("0")
    unit_price_base: Decimal = Decimal("0")
    discount_percent: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    tax_id: UUID | None = None
    tax_percent: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    total_base: Decimal = Decimal("0")
    cost_price: Decimal = Decimal("0")
    logistics_cost: Decimal = Decimal("0")
    parent_line_id: UUID | None = None
    lot_id: UUID | None = None
    lot_number: str | None = None
    declaration: str | None = None


class DocumentTaxV1(EventPayload):
    id: UUID
    position: int
    tax_id: UUID
    tax_name: str | None = None
    product_id: UUID | None = None
    amount_type: str
    base_amount: Decimal
    rate_percent: Decimal = Decimal("0")
    fixed_amount: Decimal = Decimal("0")
    tax_amount: Decimal
    affects_next_base: bool = False
    add_to_cost_price: bool = False
    add_to_total: bool = False


class DocumentChargeV1(EventPayload):
    id: UUID
    vendor_id: UUID | None = None
    vendor_name: str | None = None
    amount: Decimal
    currency_code: str | None = None
    amount_base: Decimal
    split_method: str
    include_in_total: bool = False
    add_to_cost_price: bool = False
    create_payment: bool = False


class DocumentHeaderV1(EventPayload):
    id: UUID
    organization_id: UUID
    code: str
    kind: str
    stage: str
    status: str
    version: int
    fulfilment: str = "none"
    legal_entity_id: UUID
    partner_id: UUID | None = None
    partner_name: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    source_document_id: UUID | None = None
    currency_code: str
    total: Decimal = Decimal("0")
    total_base: Decimal = Decimal("0")
    document_date: datetime
    assignee_id: UUID | None = None
    created_by_id: UUID | None = None
    from_stage: str | None = None
    to_stage: str | None = None
    cancel_reason: str | None = None
    lines_changed: list[dict[str, Any]] = Field(default_factory=list)


class DocumentConfirmedV1(DocumentHeaderV1):
    legal_entity_name: str | None = None
    contract_id: UUID | None = None
    contract_code: str | None = None
    price_list_id: UUID | None = None
    shipping_address: dict[str, Any] | None = None
    payment_term_id: UUID | None = None
    payment_schedule: list[dict[str, Any]] | None = None
    exchange_rate: Decimal = Decimal("1")
    subtotal: Decimal = Decimal("0")
    discount_amount: Decimal = Decimal("0")
    tax_amount: Decimal = Decimal("0")
    shipping_amount: Decimal = Decimal("0")
    rounding_adjustment: Decimal = Decimal("0")
    partner_amount: Decimal = Decimal("0")
    due_date: date | None = None
    expected_date: date | None = None
    external_ref: str | None = None
    confirmed_at: datetime | None = None
    confirmed_by_id: UUID | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)
    lines: list[DocumentLineV1] = Field(default_factory=list)
    taxes: list[DocumentTaxV1] = Field(default_factory=list)
    charges: list[DocumentChargeV1] = Field(default_factory=list)
    links: list[UUID] = Field(default_factory=list)


class DocumentShippedLineV1(EventPayload):
    parent_line_id: UUID
    line_id: UUID
    quantity: Decimal


class DocumentShippedV1(EventPayload):
    organization_id: UUID
    parent_id: UUID
    parent_code: str
    child_id: UUID
    child_code: str
    lines: list[DocumentShippedLineV1] = Field(default_factory=list)


class DocumentFulfilmentChangedV1(EventPayload):
    id: UUID
    organization_id: UUID
    code: str
    kind: str
    stage: str
    fulfilment: str


class PaymentAllocationV1(EventPayload):
    id: UUID
    document_id: UUID
    document_code: str | None = None
    amount: Decimal
    document_amount: Decimal
    exchange_rate: Decimal = Decimal("1")
    amount_base: Decimal
    allocated_at: datetime | None = None
    schedule_position: int | None = None


class PaymentConfirmedV1(EventPayload):
    id: UUID
    organization_id: UUID
    code: str
    version: int = 1
    direction: str
    partner_id: UUID | None = None
    partner_name: str | None = None
    partner_role: str | None = None
    legal_entity_id: UUID | None = None
    contract_id: UUID | None = None
    method: str | None = None
    category_id: UUID | None = None
    currency_code: str
    exchange_rate: Decimal = Decimal("1")
    amount: Decimal
    amount_base: Decimal
    allocated_amount: Decimal = Decimal("0")
    unallocated_amount: Decimal = Decimal("0")
    exchange_diff_base: Decimal = Decimal("0")
    rounding_adjustment: Decimal = Decimal("0")
    status: str = "confirmed"
    payment_date: date | None = None
    reference_number: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    allocations: list[PaymentAllocationV1] = Field(default_factory=list)


class PaymentOverAllocatedV1(EventPayload):
    organization_id: UUID
    payment_id: UUID
    document_id: UUID
    excess: Decimal


class BalanceChangedV1(EventPayload):
    id: UUID
    organization_id: UUID
    partner_id: UUID
    partner_name: str | None = None
    role: str
    entry_type: str
    source_type: str | None = None
    source_id: UUID | None = None
    source_code: str | None = None
    amount_base: Decimal
    occurred_at: datetime | None = None
    reverses_id: UUID | None = None


class DocumentInvoicedV1(EventPayload):
    organization_id: UUID
    source_document_id: UUID
    source_code: str
    invoice_id: UUID
    invoice_code: str
    direction: str = "out"


class EfakturaStatusChangedV1(EventPayload):
    organization_id: UUID
    invoice_id: UUID
    invoice_code: str
    status: str
    roaming_id: str | None = None
    error: str | None = None


class BalanceSnapshotItemV1(EventPayload):
    partner_id: UUID
    receivable_base: Decimal
    payable_base: Decimal


class BalanceSnapshotTakenV1(EventPayload):
    organization_id: UUID
    snapshot_date: date
    part: int = 1
    of: int = 1
    items: list[BalanceSnapshotItemV1] = Field(default_factory=list)


class ContractV1(EventPayload):
    id: UUID
    organization_id: UUID
    code: str
    type: str
    partner_id: UUID
    legal_entity_id: UUID | None = None
    number: str | None = None
    signed_at: date | None = None
    starts_at: date | None = None
    ends_at: date | None = None
    currency_code: str | None = None
    status: str


class ManualEntryV1(EventPayload):
    id: UUID
    organization_id: UUID
    code: str
    kind: str
    category_id: UUID
    category_name: str | None = None
    title: str
    entry_date: date
    legal_entity_id: UUID | None = None
    currency_code: str
    exchange_rate: Decimal = Decimal("1")
    amount: Decimal
    amount_base: Decimal
    payment_id: UUID | None = None
    status: str


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
    "opportunity.created": OpportunityV1,
    "opportunity.updated": OpportunityV1,
    "opportunity.won": OpportunityWonV1,
    "opportunity.lost": OpportunityLostV1,
    "document.created": DocumentHeaderV1,
    "document.updated": DocumentHeaderV1,
    "document.stage_advanced": DocumentHeaderV1,
    "document.cancelled": DocumentHeaderV1,
    "document.closed": DocumentHeaderV1,
    "document.amended": DocumentHeaderV1,
    "document.confirmed": DocumentConfirmedV1,
    "document.shipped": DocumentShippedV1,
    "document.received": DocumentShippedV1,
    "document.fulfilment_changed": DocumentFulfilmentChangedV1,
    "payment.confirmed": PaymentConfirmedV1,
    "payment.cancelled": PaymentConfirmedV1,
    "payment.over_allocated": PaymentOverAllocatedV1,
    "balance.changed": BalanceChangedV1,
    "balance.snapshot_taken": BalanceSnapshotTakenV1,
    "document.invoiced": DocumentInvoicedV1,
    "efaktura.status_changed": EfakturaStatusChangedV1,
    "contract.created": ContractV1,
    "contract.updated": ContractV1,
    "contract.expired": ContractV1,
    "manual_entry.confirmed": ManualEntryV1,
    "manual_entry.cancelled": ManualEntryV1,
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

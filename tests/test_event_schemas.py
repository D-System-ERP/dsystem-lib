from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from dsystem.events.schemas import CONTRACTS, PartnerV1, UserV1, dump_payload, validate_payload


def test_every_contract_has_a_versioned_model():
    for key, model in CONTRACTS.items():
        assert model.__name__.endswith("V1"), key


def test_unknown_fields_are_ignored_and_types_coerced():
    payload = validate_payload(
        "user.created",
        {"id": str(uuid4()), "organization_id": str(uuid4()), "email": "a@b.uz", "future_field": 1},
    )
    assert isinstance(payload, UserV1)
    assert not hasattr(payload, "future_field")


def test_missing_required_field_fails():
    with pytest.raises(ValidationError):
        validate_payload("user.created", {"id": str(uuid4())})


def test_dump_is_json_safe():
    partner = PartnerV1(id=uuid4(), organization_id=uuid4(), code="P10001", name="Acme", credit_limit="1000.5")
    dumped = dump_payload(partner)
    assert dumped["credit_limit"] == "1000.5"
    assert isinstance(dumped["id"], str)


def test_unknown_routing_key_passes_through():
    assert validate_payload("something.else", {"a": 1}) == {"a": 1}


def test_operations_contracts_registered():
    for key in (
        "product.created",
        "product.updated",
        "product.deleted",
        "warehouse.created",
        "warehouse.updated",
        "warehouse.deleted",
        "uom.created",
        "uom.updated",
        "price_list.updated",
        "stock.moved",
        "stock.reserved",
        "stock.unreserved",
        "stock.revalued",
        "stock.snapshot_taken",
        "cost_price.changed",
        "payment_term.updated",
        "opportunity.won",
        "document.created",
        "document.confirmed",
        "document.shipped",
        "document.fulfilment_changed",
        "payment.confirmed",
        "payment.cancelled",
        "payment.over_allocated",
        "balance.changed",
        "balance.snapshot_taken",
        "document.invoiced",
        "efaktura.status_changed",
        "currency.updated",
        "contract.created",
        "manual_entry.confirmed",
    ):
        assert key in CONTRACTS, key


def test_stock_moved_decimals_survive_round_trip():
    from dsystem.events.schemas import StockMovedV1

    org, product, warehouse, document = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(tz=timezone.utc)
    payload = dump_payload(
        StockMovedV1(
            id=uuid4(),
            organization_id=org,
            product_id=product,
            product_name="Bolt",
            warehouse_id=warehouse,
            warehouse_name="Main",
            document_id=document,
            document_kind="purchase",
            document_stage="receipt",
            direction="in",
            reason="document",
            quantity=Decimal("10.5"),
            unit_cost=Decimal("2.333333"),
            value=Decimal("24.5"),
            occurred_at=now,
            document_date=now,
        )
    )
    checked = validate_payload("stock.moved", payload)
    assert checked.quantity == Decimal("10.5") and checked.unit_cost == Decimal("2.333333")

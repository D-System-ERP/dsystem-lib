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

from decimal import Decimal

import pytest
from pydantic import ValidationError

from dsystem.schemas.values import Address, Money, Requisites


def test_money_keeps_decimal_and_uppercases_code():
    money = Money(amount="12.50", currency_code="uzs")
    assert money.amount == Decimal("12.50")
    assert money.currency_code == "UZS"


def test_money_refuses_float():
    with pytest.raises(ValidationError):
        Money(amount=12.5, currency_code="UZS")


def test_requisites_strip_blanks_to_null():
    req = Requisites(kpp=" 123 ", ogrn="")
    assert req.kpp == "123"
    assert req.ogrn is None


def test_address_one_line():
    assert Address(address="Amir Temur 1", city="Tashkent", zip="100000").one_line() == "Amir Temur 1, Tashkent, 100000"

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

import pytest

from dsystem.uom import UomCategoryMismatch, base_quantity, convert, from_base, to_base


@dataclass
class Uom:
    id: object
    category_id: object
    factor: Decimal
    rounding: Decimal


WEIGHT = uuid4()
LENGTH = uuid4()
KG = Uom(uuid4(), WEIGHT, Decimal("1"), Decimal("0.001"))
T = Uom(uuid4(), WEIGHT, Decimal("1000"), Decimal("0.001"))
G = Uom(uuid4(), WEIGHT, Decimal("0.001"), Decimal("1"))
M = Uom(uuid4(), LENGTH, Decimal("1"), Decimal("0.01"))


def test_bigger_and_smaller_units_convert_through_the_reference():
    assert convert("1", T, KG) == Decimal("1000.000")
    assert convert("1", G, KG) == Decimal("0.001")
    assert convert("2500", KG, T) == Decimal("2.500")


def test_same_unit_only_rounds():
    assert convert("1.23456", KG, KG) == Decimal("1.235")


def test_cross_category_is_refused():
    with pytest.raises(UomCategoryMismatch):
        convert("1", KG, M)


def test_base_helpers():
    assert to_base("2", T) == Decimal("2000")
    assert from_base("2000", T) == Decimal("2.000")
    assert base_quantity("3", T, KG) == Decimal("3000.000")

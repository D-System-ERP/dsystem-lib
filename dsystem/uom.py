"""Unit-of-measure conversion (Odoo model: category + reference + factor).

``factor`` is Odoo's ``factor_inv``: 1 unit of this uom = ``factor`` × reference
unit (т = 1000 кг, г = 0.001 кг). Quantities in stock are always in the product's
base uom; conversion is only legal inside one category.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from dsystem.money import to_decimal


class UomLike(Protocol):
    id: object
    category_id: object
    factor: Decimal
    rounding: Decimal


class UomCategoryMismatch(ValueError):
    def __init__(self, from_uom: UomLike, to_uom: UomLike) -> None:
        self.from_uom = from_uom
        self.to_uom = to_uom
        super().__init__("units belong to different categories")


def round_quantity(value: Decimal, rounding: Decimal | None) -> Decimal:
    step = to_decimal(rounding) if rounding else Decimal("0.000001")
    if step <= 0:
        step = Decimal("0.000001")
    return (value / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step


def to_base(quantity, uom: UomLike) -> Decimal:
    return to_decimal(quantity) * to_decimal(uom.factor)


def from_base(quantity_base, uom: UomLike) -> Decimal:
    return round_quantity(to_decimal(quantity_base) / to_decimal(uom.factor), uom.rounding)


def convert(quantity, from_uom: UomLike, to_uom: UomLike) -> Decimal:
    if from_uom.category_id != to_uom.category_id:
        raise UomCategoryMismatch(from_uom, to_uom)
    if from_uom.id == to_uom.id:
        return round_quantity(to_decimal(quantity), to_uom.rounding)
    value = to_decimal(quantity) * to_decimal(from_uom.factor) / to_decimal(to_uom.factor)
    return round_quantity(value, to_uom.rounding)


def base_quantity(quantity, line_uom: UomLike, product_uom: UomLike) -> Decimal:
    """``document_lines.base_quantity`` — the line quantity in the product's base uom."""
    return convert(quantity, line_uom, product_uom)

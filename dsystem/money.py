"""Decimal-only money arithmetic. ``float`` never touches an amount.

Storage precision is ``Numeric(20, 6)``; presentation rounding uses the
organization's ``price_decimal_places``. Every rounding is ``ROUND_HALF_UP`` so
documents, ledgers and reports agree to the tiyin.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

STORAGE_PLACES = 6
ZERO = Decimal("0")


def to_decimal(value: Any) -> Decimal:
    """Coerce ints, strings and Decimals; floats are refused to keep binary noise out."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not an amount")
    if isinstance(value, float):
        raise TypeError("float amounts are not allowed; send a string or Decimal")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"not a decimal amount: {value!r}") from exc


def round_money(value: Any, places: int = STORAGE_PLACES) -> Decimal:
    quant = Decimal(1).scaleb(-places) if places > 0 else Decimal(1)
    return to_decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def convert(amount: Any, rate: Any, places: int = STORAGE_PLACES) -> Decimal:
    """``amount`` in a currency → base currency, where ``1 currency = rate × base``."""
    return round_money(to_decimal(amount) * to_decimal(rate), places)


def to_base(amount: Any, rate: Any, places: int = STORAGE_PLACES) -> Decimal:
    return convert(amount, rate, places)


def from_base(amount_base: Any, rate: Any, places: int = STORAGE_PLACES) -> Decimal:
    rate_dec = to_decimal(rate)
    if rate_dec == 0:
        raise ValueError("exchange rate must be non-zero")
    return round_money(to_decimal(amount_base) / rate_dec, places)


def percent_of(amount: Any, percent: Any, places: int = STORAGE_PLACES) -> Decimal:
    return round_money(to_decimal(amount) * to_decimal(percent) / Decimal(100), places)


def split_amount(total: Any, weights: list[Any], places: int = STORAGE_PLACES) -> list[Decimal]:
    """Distribute ``total`` by ``weights``; the last share absorbs rounding so parts sum exactly."""
    total_dec = to_decimal(total)
    weight_decs = [to_decimal(w) for w in weights]
    weight_sum = sum(weight_decs, ZERO)
    if not weight_decs:
        return []
    if weight_sum == 0:
        equal = round_money(total_dec / len(weight_decs), places)
        shares = [equal] * len(weight_decs)
    else:
        shares = [round_money(total_dec * w / weight_sum, places) for w in weight_decs]
    shares[-1] = round_money(total_dec - sum(shares[:-1], ZERO), places)
    return shares

from decimal import Decimal

import pytest

from dsystem.money import convert, from_base, percent_of, round_money, split_amount, to_decimal


def test_round_half_up_at_storage_precision():
    assert round_money("1.0000005") == Decimal("1.000001")
    assert round_money("2.5", 0) == Decimal("3")
    assert round_money(Decimal("12.345"), 2) == Decimal("12.35")


def test_floats_are_refused():
    with pytest.raises(TypeError):
        to_decimal(0.1)


def test_convert_and_back():
    assert convert("100", "12650") == Decimal("1265000.000000")
    assert from_base("1265000", "12650") == Decimal("100.000000")


def test_percent_of():
    assert percent_of("1000", "12") == Decimal("120.000000")


def test_split_sums_exactly():
    shares = split_amount("100", ["1", "1", "1"], places=2)
    assert shares == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert sum(shares) == Decimal("100.00")


def test_split_with_zero_weights_is_equal():
    assert split_amount("9", ["0", "0", "0"], places=2) == [Decimal("3.00"), Decimal("3.00"), Decimal("3.00")]

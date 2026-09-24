import pytest

from dsystem.currencies import (
    CURRENCIES,
    enabled_codes,
    ensure_enabled,
    get_currency,
    is_currency,
    normalize_code,
    normalize_codes,
)
from dsystem.exceptions import AppException


def test_catalog_is_keyed_by_upper_iso_code():
    assert all(code == c.code and len(code) == 3 and code.isupper() for code, c in CURRENCIES.items())


def test_minor_units_follow_iso():
    assert get_currency("uzs").decimal_places == 2
    assert get_currency("JPY").decimal_places == 0
    assert get_currency("KWD").decimal_places == 3


def test_is_currency():
    assert is_currency("usd")
    assert not is_currency("XXX")
    assert not is_currency(None)


def test_normalize_codes_dedupes_and_keeps_order():
    assert normalize_codes(["usd", "UZS", "USD"]) == ["USD", "UZS"]


def test_normalize_code_rejects_unknown():
    with pytest.raises(ValueError):
        normalize_code("ABC")


def test_enabled_codes_always_contains_base():
    assert enabled_codes({"base_currency_code": "uzs", "currency_codes": ["USD"]}) == ["UZS", "USD"]
    assert enabled_codes({}) == ["UZS"]


def test_ensure_enabled():
    assert ensure_enabled("usd", ["UZS", "USD"]) == "USD"
    with pytest.raises(AppException) as exc:
        ensure_enabled("EUR", ["UZS"])
    assert exc.value.status_code == 422 and exc.value.key == "currency.not_enabled"


async def test_ensure_org_currency_reads_organization_settings(monkeypatch):
    import dsystem.currencies as currencies

    async def _settings(organization_id):
        return {"base_currency_code": "UZS", "currency_codes": ["UZS", "USD"]}

    monkeypatch.setattr(currencies, "organization_settings", _settings)
    assert await currencies.ensure_org_currency("org", "usd") == "USD"
    assert await currencies.ensure_org_currency("org", None) is None
    with pytest.raises(AppException):
        await currencies.ensure_org_currency("org", "EUR")

import pytest

from dsystem.utils.phone import InvalidPhoneError, normalize_phone


def test_uz_local_number_becomes_e164():
    assert normalize_phone("90 123 45 67") == "+998901234567"
    assert normalize_phone("+998 (90) 123-45-67") == "+998901234567"


def test_foreign_number_keeps_its_country():
    assert normalize_phone("+7 999 123 45 67") == "+79991234567"


def test_blank_is_none_and_garbage_raises():
    assert normalize_phone("  ") is None
    with pytest.raises(InvalidPhoneError):
        normalize_phone("abc")

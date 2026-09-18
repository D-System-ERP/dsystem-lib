from __future__ import annotations

import phonenumbers

DEFAULT_REGION = "UZ"


class InvalidPhoneError(ValueError):
    pass


def normalize_phone(value: str | None, region: str = DEFAULT_REGION) -> str | None:
    """Return the number in E.164 (``+998901234567``) or raise ``InvalidPhoneError``.

    Empty input passes through as ``None`` so optional fields stay optional.
    """
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException as exc:
        raise InvalidPhoneError(f"invalid phone number: {value!r}") from exc
    if not phonenumbers.is_possible_number(parsed):
        raise InvalidPhoneError(f"invalid phone number: {value!r}")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


def normalize_account(value: str | None) -> str | None:
    """Bank account numbers compare without spaces, dashes or case (``UZ..`` IBAN or 20-digit)."""
    if value is None:
        return None
    cleaned = "".join(ch for ch in value if ch.isalnum())
    return cleaned.upper() or None


class BankAccountMixin:
    """Columns shared by ``partner_bank_accounts`` (crm) and ``legal_entity_bank_accounts`` (auth)."""

    bank_name: Mapped[str] = mapped_column(String(100))
    bank_code: Mapped[str] = mapped_column(String(20))
    account: Mapped[str] = mapped_column(String(34))
    correspondent_account: Mapped[str | None] = mapped_column(String(34))
    account_holder_name: Mapped[str | None] = mapped_column(String(200))
    currency_code: Mapped[str] = mapped_column(String(3), default="UZS")
    is_primary: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

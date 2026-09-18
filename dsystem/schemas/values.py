"""Value objects shared across services (DDD): validated once in the lib, stored as jsonb or columns."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from dsystem.money import to_decimal
from dsystem.schemas.base import AppSchema


def _amount(value):
    try:
        return to_decimal(value)
    except TypeError as exc:
        raise ValueError(str(exc)) from exc


class Money(AppSchema):
    amount: Decimal = Field(..., description="Amount in `currency_code`")
    currency_code: str = Field(..., min_length=3, max_length=3, description="ISO 4217 code, e.g. `UZS`")

    @field_validator("amount", mode="before")
    @classmethod
    def _decimal(cls, value):
        return _amount(value)

    @field_validator("currency_code")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class Address(AppSchema):
    address: str | None = Field(None, max_length=255, description="Street, house, building — one line")
    city: str | None = Field(None, max_length=100)
    region: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    zip: str | None = Field(None, max_length=20)

    def one_line(self) -> str:
        return ", ".join(p for p in (self.address, self.city, self.region, self.country, self.zip) if p)


class Requisites(AppSchema):
    """Country-specific registration codes kept as jsonb — never filtered, only printed."""

    kpp: str | None = Field(None, max_length=20)
    ogrn: str | None = Field(None, max_length=20)
    ogrnip: str | None = Field(None, max_length=20)
    okpo: str | None = Field(None, max_length=20)
    oked: str | None = Field(None, max_length=20)
    vat_code: str | None = Field(None, max_length=20, description="UZ НДС ro'yxat kodi")

    @model_validator(mode="after")
    def _strip(self):
        for name in type(self).model_fields:
            value = getattr(self, name)
            if isinstance(value, str):
                setattr(self, name, value.strip() or None)
        return self


class Dimensions(AppSchema):
    length: Decimal | None = Field(None, ge=0)
    width: Decimal | None = Field(None, ge=0)
    height: Decimal | None = Field(None, ge=0)
    unit: Literal["mm", "cm", "m"] = "cm"

    @field_validator("length", "width", "height", mode="before")
    @classmethod
    def _decimal(cls, value):
        return None if value is None else _amount(value)


class Quantity(AppSchema):
    value: Decimal = Field(..., gt=0)
    uom_id: UUID

    @field_validator("value", mode="before")
    @classmethod
    def _decimal(cls, value):
        return _amount(value)

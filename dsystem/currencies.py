"""ISO 4217 currency catalog.

Currencies are reference data, not tenant data: every organization sees the same
code, name, symbol and minor units. An organization only chooses which codes it
works with (``organizations.currency_codes``) and which one is its base.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from dsystem.clients.auth import organization_settings
from dsystem.exceptions import AppException


@dataclass(frozen=True)
class Currency:
    code: str
    name: str
    symbol: str
    decimal_places: int


_CATALOG: tuple[Currency, ...] = (
    Currency("AED", "United Arab Emirates Dirham", "AED", 2),
    Currency("AFN", "Afghan Afghani", "Af", 2),
    Currency("ALL", "Albanian Lek", "ALL", 2),
    Currency("AMD", "Armenian Dram", "֏", 2),
    Currency("ARS", "Argentine Peso", "AR$", 2),
    Currency("AUD", "Australian Dollar", "AU$", 2),
    Currency("AZN", "Azerbaijani Manat", "₼", 2),
    Currency("BAM", "Bosnia-Herzegovina Convertible Mark", "KM", 2),
    Currency("BDT", "Bangladeshi Taka", "৳", 2),
    Currency("BGN", "Bulgarian Lev", "BGN", 2),
    Currency("BHD", "Bahraini Dinar", "BD", 3),
    Currency("BIF", "Burundian Franc", "FBu", 0),
    Currency("BND", "Brunei Dollar", "BN$", 2),
    Currency("BOB", "Bolivian Boliviano", "Bs", 2),
    Currency("BRL", "Brazilian Real", "R$", 2),
    Currency("BWP", "Botswanan Pula", "BWP", 2),
    Currency("BYN", "Belarusian Ruble", "Br", 2),
    Currency("BZD", "Belize Dollar", "BZ$", 2),
    Currency("CAD", "Canadian Dollar", "CA$", 2),
    Currency("CDF", "Congolese Franc", "CDF", 2),
    Currency("CHF", "Swiss Franc", "CHF", 2),
    Currency("CLP", "Chilean Peso", "CL$", 0),
    Currency("CNY", "Chinese Yuan", "CN¥", 2),
    Currency("COP", "Colombian Peso", "CO$", 2),
    Currency("CRC", "Costa Rican Colón", "₡", 2),
    Currency("CVE", "Cape Verdean Escudo", "CV$", 2),
    Currency("CZK", "Czech Koruna", "Kč", 2),
    Currency("DJF", "Djiboutian Franc", "Fdj", 0),
    Currency("DKK", "Danish Krone", "kr", 2),
    Currency("DOP", "Dominican Peso", "RD$", 2),
    Currency("DZD", "Algerian Dinar", "DA", 2),
    Currency("EGP", "Egyptian Pound", "E£", 2),
    Currency("ERN", "Eritrean Nakfa", "Nfk", 2),
    Currency("ETB", "Ethiopian Birr", "Br", 2),
    Currency("EUR", "Euro", "€", 2),
    Currency("GBP", "British Pound Sterling", "£", 2),
    Currency("GEL", "Georgian Lari", "₾", 2),
    Currency("GHS", "Ghanaian Cedi", "GH₵", 2),
    Currency("GNF", "Guinean Franc", "FG", 0),
    Currency("GTQ", "Guatemalan Quetzal", "Q", 2),
    Currency("HKD", "Hong Kong Dollar", "HK$", 2),
    Currency("HNL", "Honduran Lempira", "HNL", 2),
    Currency("HUF", "Hungarian Forint", "Ft", 2),
    Currency("IDR", "Indonesian Rupiah", "Rp", 2),
    Currency("ILS", "Israeli New Shekel", "₪", 2),
    Currency("INR", "Indian Rupee", "₹", 2),
    Currency("IQD", "Iraqi Dinar", "IQD", 3),
    Currency("IRR", "Iranian Rial", "IRR", 2),
    Currency("ISK", "Icelandic Króna", "kr", 0),
    Currency("JMD", "Jamaican Dollar", "J$", 2),
    Currency("JOD", "Jordanian Dinar", "JD", 3),
    Currency("JPY", "Japanese Yen", "¥", 0),
    Currency("KES", "Kenyan Shilling", "Ksh", 2),
    Currency("KGS", "Kyrgystani Som", "сом", 2),
    Currency("KHR", "Cambodian Riel", "៛", 2),
    Currency("KMF", "Comorian Franc", "CF", 0),
    Currency("KRW", "South Korean Won", "₩", 0),
    Currency("KWD", "Kuwaiti Dinar", "KD", 3),
    Currency("KZT", "Kazakhstani Tenge", "₸", 2),
    Currency("LBP", "Lebanese Pound", "L.L.", 2),
    Currency("LKR", "Sri Lankan Rupee", "Rs", 2),
    Currency("LYD", "Libyan Dinar", "LD", 3),
    Currency("MAD", "Moroccan Dirham", "MAD", 2),
    Currency("MDL", "Moldovan Leu", "MDL", 2),
    Currency("MGA", "Malagasy Ariary", "Ar", 2),
    Currency("MKD", "Macedonian Denar", "MKD", 2),
    Currency("MMK", "Myanmar Kyat", "K", 2),
    Currency("MNT", "Mongolian Tugrik", "₮", 2),
    Currency("MOP", "Macanese Pataca", "MOP$", 2),
    Currency("MUR", "Mauritian Rupee", "Rs", 2),
    Currency("MXN", "Mexican Peso", "MX$", 2),
    Currency("MYR", "Malaysian Ringgit", "RM", 2),
    Currency("MZN", "Mozambican Metical", "MTn", 2),
    Currency("NAD", "Namibian Dollar", "N$", 2),
    Currency("NGN", "Nigerian Naira", "₦", 2),
    Currency("NIO", "Nicaraguan Córdoba", "C$", 2),
    Currency("NOK", "Norwegian Krone", "kr", 2),
    Currency("NPR", "Nepalese Rupee", "Rs", 2),
    Currency("NZD", "New Zealand Dollar", "NZ$", 2),
    Currency("OMR", "Omani Rial", "OMR", 3),
    Currency("PAB", "Panamanian Balboa", "B/.", 2),
    Currency("PEN", "Peruvian Sol", "S/", 2),
    Currency("PHP", "Philippine Peso", "₱", 2),
    Currency("PKR", "Pakistani Rupee", "Rs", 2),
    Currency("PLN", "Polish Zloty", "zł", 2),
    Currency("PYG", "Paraguayan Guarani", "₲", 0),
    Currency("QAR", "Qatari Riyal", "QR", 2),
    Currency("RON", "Romanian Leu", "lei", 2),
    Currency("RSD", "Serbian Dinar", "din.", 2),
    Currency("RUB", "Russian Ruble", "₽", 2),
    Currency("RWF", "Rwandan Franc", "RF", 0),
    Currency("SAR", "Saudi Riyal", "SR", 2),
    Currency("SDG", "Sudanese Pound", "SDG", 2),
    Currency("SEK", "Swedish Krona", "kr", 2),
    Currency("SGD", "Singapore Dollar", "S$", 2),
    Currency("SOS", "Somali Shilling", "Sh", 2),
    Currency("SYP", "Syrian Pound", "SY£", 2),
    Currency("THB", "Thai Baht", "฿", 2),
    Currency("TJS", "Tajikistani Somoni", "SM", 2),
    Currency("TMT", "Turkmenistani Manat", "m", 2),
    Currency("TND", "Tunisian Dinar", "DT", 3),
    Currency("TOP", "Tongan Paʻanga", "T$", 2),
    Currency("TRY", "Turkish Lira", "₺", 2),
    Currency("TTD", "Trinidad and Tobago Dollar", "TT$", 2),
    Currency("TWD", "New Taiwan Dollar", "NT$", 2),
    Currency("TZS", "Tanzanian Shilling", "TSh", 2),
    Currency("UAH", "Ukrainian Hryvnia", "₴", 2),
    Currency("UGX", "Ugandan Shilling", "USh", 0),
    Currency("USD", "US Dollar", "$", 2),
    Currency("UYU", "Uruguayan Peso", "$U", 2),
    Currency("UZS", "Uzbekistani Som", "so'm", 2),
    Currency("VES", "Venezuelan Bolívar", "Bs.", 2),
    Currency("VND", "Vietnamese Dong", "₫", 0),
    Currency("XAF", "CFA Franc BEAC", "FCFA", 0),
    Currency("XOF", "CFA Franc BCEAO", "CFA", 0),
    Currency("YER", "Yemeni Rial", "YR", 2),
    Currency("ZAR", "South African Rand", "R", 2),
    Currency("ZMW", "Zambian Kwacha", "ZK", 2),
)

CURRENCIES: dict[str, Currency] = {currency.code: currency for currency in _CATALOG}

DEFAULT_CURRENCY_CODE = "UZS"


def is_currency(code: str | None) -> bool:
    return bool(code) and code.upper() in CURRENCIES


def get_currency(code: str) -> Currency:
    return CURRENCIES[code.upper()]


def normalize_code(code: str) -> str:
    value = code.strip().upper()
    if value not in CURRENCIES:
        raise ValueError(f"unknown currency code: {code}")
    return value


def normalize_codes(codes: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for code in codes:
        seen[normalize_code(code)] = None
    return list(seen)


def enabled_codes(organization: Mapping[str, Any]) -> list[str]:
    base = str(organization.get("base_currency_code") or DEFAULT_CURRENCY_CODE).upper()
    codes = [str(code).upper() for code in organization.get("currency_codes") or []]
    return codes if base in codes else [base, *codes]


def ensure_enabled(code: str, enabled: Iterable[str], *, field: str = "currency_code") -> str:
    value = code.upper()
    if value not in set(enabled):
        raise AppException(
            422,
            code="currency.not_enabled",
            key="currency.not_enabled",
            message="The currency is not enabled for the organization",
            params={"currency_code": value, "field": field},
        )
    return value


async def ensure_org_currency(organization_id: Any, code: str | None, *, field: str = "currency_code") -> str | None:
    if not code:
        return code
    return ensure_enabled(code, enabled_codes(await organization_settings(organization_id)), field=field)

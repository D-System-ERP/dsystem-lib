from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, tzinfo

from dsystem.export.columns import Column, label

XLSX_ROW_LIMIT = 50_000
PDF_ROW_LIMIT = 5_000


@dataclass(frozen=True, slots=True)
class Sheet:
    title: str
    columns: Sequence[Column]
    rows: Iterable[Sequence]
    lang: str
    zone: tzinfo
    generated_at: datetime
    date_from: date | None = None
    date_to: date | None = None
    truncated: bool = False
    row_limit: int = XLSX_ROW_LIMIT


def within_limit(rows: Sequence, limit: int = XLSX_ROW_LIMIT) -> tuple[Sequence, bool]:
    return (rows[:limit], True) if len(rows) > limit else (rows, False)


def title_text(sheet: Sheet) -> str:
    if sheet.date_from is None and sheet.date_to is None:
        return sheet.title
    start = sheet.date_from.strftime("%d.%m.%Y") if sheet.date_from else "…"
    end = sheet.date_to.strftime("%d.%m.%Y") if sheet.date_to else "…"
    return f"{sheet.title} · {start} – {end}"


def meta_text(sheet: Sheet) -> str:
    at = sheet.generated_at.astimezone(sheet.zone).strftime("%d.%m.%Y %H:%M")
    text = label("report.generated_at", sheet.lang, {"at": at})
    if sheet.truncated:
        limit = f"{sheet.row_limit:,}".replace(",", " ")
        text = f"{text} · {label('report.truncated', sheet.lang, {'limit': limit})}"
    return text

from dataclasses import dataclass

from dsystem.i18n import translate

MONEY = "#,##0.00"
QUANTITY = "#,##0.###"
DATE = "yyyy-mm-dd hh:mm"
DAY = "yyyy-mm-dd"


@dataclass(frozen=True, slots=True)
class Column:
    key: str
    width: int
    format: str | None = None
    total: bool = False
    title: str | None = None

    @property
    def numeric(self) -> bool:
        return self.format in (MONEY, QUANTITY)


def label(key: str, lang: str, params: dict | None = None) -> str:
    return translate(key, lang, params) or key.rsplit(".", 1)[-1]


def column_heading(column: Column, lang: str) -> str:
    return column.title if column.title is not None else label(f"report.column.{column.key}", lang)

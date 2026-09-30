from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from pypdf import PdfReader

from dsystem.export.columns import DATE, DAY, MONEY, QUANTITY, Column
from dsystem.export.pdf import cell_text, render_table_pdf, table_pdf
from dsystem.export.sheet import PDF_ROW_LIMIT, Sheet
from dsystem.i18n import bind_locale_dir

TASHKENT = ZoneInfo("Asia/Tashkent")
COLUMNS = (
    Column("document_code", 18),
    Column("partner", 32),
    Column("quantity", 12, QUANTITY),
    Column("total", 16, MONEY, total=True),
)


@pytest.fixture(autouse=True)
def _locale():
    bind_locale_dir(Path(__file__).resolve().parents[1] / "dsystem" / "locale")


def _sheet(rows, **overrides) -> Sheet:
    fields = {
        "title": "Продажи",
        "columns": COLUMNS,
        "rows": rows,
        "lang": "ru",
        "zone": TASHKENT,
        "generated_at": datetime(2026, 10, 1, 9, 30, tzinfo=timezone.utc),
        "row_limit": PDF_ROW_LIMIT,
    }
    return Sheet(**(fields | overrides))


def _pages(content: bytes) -> list[str]:
    return [page.extract_text() for page in PdfReader(BytesIO(content)).pages]


def _rows(count: int):
    return [(f"SO-{i}", "«Ўзбекистон Савдо» МЧЖ", Decimal("1.5"), Decimal("100.25")) for i in range(count)]


def test_pdf_carries_title_cyrillic_rows_and_total():
    content = table_pdf(_sheet(_rows(3)))
    text = _pages(content)[0]

    assert content.startswith(b"%PDF")
    assert "Продажи" in text and "«Ўзбекистон Савдо» МЧЖ" in text
    assert "Итого" in text and "300.75" in text
    assert "Выгружено 01.10.2026 14:30" in text


def test_long_list_breaks_pages_repeats_the_heading_and_numbers_them():
    pages = _pages(table_pdf(_sheet(_rows(120))))

    assert len(pages) > 1
    assert all("document_code" in page for page in pages)
    assert f"Стр. 1 из {len(pages)}" in pages[0] and f"Стр. {len(pages)} из {len(pages)}" in pages[-1]


def test_wide_sheets_turn_landscape():
    wide = COLUMNS + tuple(Column(f"extra_{i}", 20) for i in range(4))
    rows = [row + ("", "", "", "") for row in _rows(1)]
    page = PdfReader(BytesIO(table_pdf(_sheet(rows, columns=wide)))).pages[0]

    assert page.mediabox.width > page.mediabox.height


def test_text_wider_than_its_column_is_cut_with_an_ellipsis():
    name = "Очень длинное название контрагента " * 8
    text = _pages(table_pdf(_sheet([("SO-1", name, 1, 1)])))[0]

    assert "…" in text and name.strip() not in text


def test_money_dates_and_short_codes_are_never_cut_in_a_crowded_table():
    columns = (
        Column("document_code", 18),
        Column("document_date", 18, DATE),
        Column("status", 14),
        Column("partner", 32),
        Column("product_name", 36),
        Column("quantity", 12, QUANTITY),
        Column("unit_price", 14, MONEY),
        Column("total", 16, MONEY),
        Column("total_base", 16, MONEY, total=True),
        Column("cost_price", 14, MONEY),
        Column("warehouse", 24),
    )
    at = datetime(2026, 9, 25, 10, 40, tzinfo=timezone.utc)
    rows = [
        (
            "DEMO-OF10001",
            at,
            "Подтверждён",
            "Almaty Pack Trade TOO",
            "PET preforma 42 g (1,5 l uchun)",
            3,
            Decimal("890000"),
            Decimal("62000000"),
            Decimal("784300000000"),
            Decimal("4807000"),
            "Tayyor mahsulot ombori",
        )
    ] * 3
    text = _pages(table_pdf(_sheet(rows, columns=columns)))[0]

    for whole in (
        "DEMO-OF10001",
        "25.09.2026 15:40",
        "890 000.00",
        "62 000 000.00",
        "784 300 000 000.00",
        "2 352 900 000 000.00",
        "4 807 000.00",
    ):
        assert whole in text, whole


def test_truncated_pdf_says_so():
    text = _pages(table_pdf(_sheet(_rows(1), truncated=True)))[0]

    assert "только первые 5 000 строк" in text


def test_cell_text_formats_by_column():
    assert cell_text(Decimal("1234567.5"), Column("x", 1, MONEY), TASHKENT) == "1 234 567.50"
    assert cell_text(Decimal("2.500"), Column("x", 1, QUANTITY), TASHKENT) == "2.5"
    assert cell_text(Decimal("1000"), Column("x", 1, QUANTITY), TASHKENT) == "1 000"
    at = datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc)
    assert cell_text(at, Column("x", 1, DATE), TASHKENT) == "01.10.2026 01:00"
    assert cell_text(at, Column("x", 1, DAY), TASHKENT) == "01.10.2026"
    assert cell_text(date(2026, 9, 1), Column("x", 1), TASHKENT) == "01.09.2026"
    assert cell_text(None, Column("x", 1, MONEY), TASHKENT) == ""


async def test_render_runs_off_the_event_loop():
    content = await render_table_pdf(_sheet(row for row in _rows(2)))

    assert "SO-1" in _pages(content)[0]

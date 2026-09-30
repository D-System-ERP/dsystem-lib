import asyncio
from dataclasses import replace
from datetime import date, datetime, tzinfo
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

from dsystem.export.columns import DAY, MONEY, QUANTITY, Column, label
from dsystem.export.sheet import Sheet, meta_text, title_text

PDF_MEDIA_TYPE = "application/pdf"
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
FAMILY = "Inter"
SEMIBOLD = "InterSemiBold"

_INK = (17, 19, 28)
_MUTED = (110, 107, 123)
_RULE = (225, 225, 232)
_HEAD_FILL = (115, 103, 240)
_ZEBRA = (247, 247, 251)
_LANDSCAPE_FROM = 120
_MARGIN = 10
_FONT_SIZE = 7.5
_ROW_HEIGHT = 5
_HEAD_LINE = 3.4
_PADDING = 1.2
_BOTTOM = _MARGIN + 6


class ReportPdf(FPDF):
    def __init__(self, lang: str, footer_text: str, orientation: str = "P"):
        super().__init__(orientation=orientation, unit="mm", format="A4")
        self.lang = lang
        self.footer_text = footer_text
        register_fonts(self)
        self.set_margins(_MARGIN, _MARGIN, _MARGIN)
        self.set_auto_page_break(False)
        self.c_margin = _PADDING

    def footer(self) -> None:
        self.set_y(-_MARGIN)
        self.set_font(FAMILY, "", 7)
        self.set_text_color(*_MUTED)
        self.cell(self.epw / 2, 4, self.footer_text)
        self.cell(
            self.epw / 2, 4, label("report.page", self.lang, {"page": self.page_no(), "pages": "{nb}"}), align="R"
        )


def register_fonts(pdf: FPDF) -> None:
    pdf.add_font(FAMILY, "", str(FONTS_DIR / "Inter-Regular.ttf"))
    pdf.add_font(FAMILY, "B", str(FONTS_DIR / "Inter-Bold.ttf"))
    pdf.add_font(SEMIBOLD, "", str(FONTS_DIR / "Inter-SemiBold.ttf"))


async def render_table_pdf(sheet: Sheet) -> bytes:
    return await asyncio.to_thread(table_pdf, replace(sheet, rows=list(sheet.rows)))


def table_pdf(sheet: Sheet) -> bytes:
    landscape = sum(column.width for column in sheet.columns) > _LANDSCAPE_FROM
    pdf = ReportPdf(sheet.lang, meta_text(sheet), "L" if landscape else "P")
    pdf.add_page()
    pdf.set_font(FAMILY, "B", 13)
    pdf.set_text_color(*_INK)
    pdf.multi_cell(0, 6, title_text(sheet), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(FAMILY, "", 7.5)
    pdf.set_text_color(*_MUTED)
    pdf.multi_cell(0, 4, meta_text(sheet), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    _draw_table(pdf, sheet)
    return bytes(pdf.output())


def _draw_table(pdf: ReportPdf, sheet: Sheet) -> None:
    columns = sheet.columns
    scale = pdf.epw / sum(column.width for column in columns)
    widths = [column.width * scale for column in columns]
    aligns = ["R" if column.numeric else "L" for column in columns]
    headings = [label(f"report.column.{column.key}", sheet.lang) for column in columns]
    bottom = pdf.h - _BOTTOM
    pdf.set_draw_color(*_RULE)
    pdf.set_line_width(0.1)

    def heading() -> float:
        pdf.set_font(SEMIBOLD, "", _FONT_SIZE)
        lines = max(
            len(pdf.multi_cell(w, _HEAD_LINE, text, dry_run=True, output="LINES")) for w, text in zip(widths, headings)
        )
        height = lines * _HEAD_LINE + 2 * _PADDING
        top = pdf.get_y()
        pdf.set_fill_color(*_HEAD_FILL)
        pdf.rect(pdf.l_margin, top, pdf.epw, height, style="F")
        pdf.set_text_color(255, 255, 255)
        x = pdf.l_margin
        for w, text, align in zip(widths, headings, aligns):
            pdf.set_xy(x, top + _PADDING)
            pdf.multi_cell(w, _HEAD_LINE, text, align=align)
            x += w
        pdf.set_font(FAMILY, "", _FONT_SIZE)
        pdf.set_text_color(*_INK)
        return top + height

    def row(values: list[str], y: float, zebra: bool) -> float:
        if zebra:
            pdf.set_fill_color(*_ZEBRA)
            pdf.rect(pdf.l_margin, y, pdf.epw, _ROW_HEIGHT, style="F")
        x = pdf.l_margin
        for w, text, align in zip(widths, values, aligns):
            pdf.set_xy(x, y)
            pdf.cell(w, _ROW_HEIGHT, _fit(pdf, text, w - 2 * _PADDING), align=align)
            x += w
        pdf.line(pdf.l_margin, y + _ROW_HEIGHT, pdf.l_margin + pdf.epw, y + _ROW_HEIGHT)
        return y + _ROW_HEIGHT

    y = heading()
    sums = {index: Decimal(0) for index, column in enumerate(columns) if column.total}
    for number, values in enumerate(sheet.rows):
        if y + _ROW_HEIGHT > bottom:
            pdf.add_page()
            y = heading()
        y = row(
            [cell_text(value, column, sheet.zone) for column, value in zip(columns, values, strict=True)],
            y,
            number % 2 == 1,
        )
        for index in sums:
            value = values[index]
            if isinstance(value, (Decimal, int, float)) and not isinstance(value, bool):
                sums[index] += Decimal(str(value))
    if sums:
        if y + _ROW_HEIGHT > bottom:
            pdf.add_page()
            y = heading()
        pdf.set_font(FAMILY, "B", _FONT_SIZE)
        totals = [
            cell_text(sums[index], column, sheet.zone)
            if index in sums
            else (label("report.total", sheet.lang) if index == 0 else "")
            for index, column in enumerate(columns)
        ]
        row(totals, y, False)
        pdf.set_font(FAMILY, "", _FONT_SIZE)


def _fit(pdf: FPDF, text: str, width: float) -> str:
    if not text or pdf.get_string_width(text) <= width:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if pdf.get_string_width(text[:middle] + "…") <= width:
            low = middle
        else:
            high = middle - 1
    return text[:low].rstrip() + "…"


def cell_text(value, column: Column, zone: tzinfo) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, datetime):
        local = value.astimezone(zone) if value.tzinfo is not None else value
        return local.strftime("%d.%m.%Y" if column.format == DAY else "%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, (Decimal, int, float)):
        return _number(Decimal(str(value)), column.format)
    return str(value)


def _number(value: Decimal, fmt: str | None) -> str:
    if fmt == MONEY:
        return f"{value:,.2f}".replace(",", " ")
    if fmt == QUANTITY:
        text = f"{value.quantize(Decimal('0.001')):,f}".replace(",", " ")
        return text.rstrip("0").rstrip(".") if "." in text else text
    return str(value)

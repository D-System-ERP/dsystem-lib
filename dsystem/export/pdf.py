import asyncio
from dataclasses import replace
from datetime import date, datetime, tzinfo
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF

from dsystem.export.columns import DATE, DAY, MONEY, QUANTITY, Column, label
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
_FONT_SIZES = (7.5, 7.0, 6.5, 6.0, 5.5)
_FLEX_MIN = 24
_SLACK = 0.3
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
    aligns = ["R" if column.numeric else "L" for column in columns]
    rigid = [_rigid(column) for column in columns]
    headings = [label(f"report.column.{column.key}", sheet.lang) for column in columns]
    sums = {index: Decimal(0) for index, column in enumerate(columns) if column.total}
    body = []
    for values in sheet.rows:
        body.append([cell_text(value, column, sheet.zone) for column, value in zip(columns, values, strict=True)])
        for index in sums:
            value = values[index]
            if isinstance(value, (Decimal, int, float)) and not isinstance(value, bool):
                sums[index] += Decimal(str(value))
    totals = None
    if sums:
        totals = [
            cell_text(sums[index], column, sheet.zone)
            if index in sums
            else (label("report.total", sheet.lang) if index == 0 else "")
            for index, column in enumerate(columns)
        ]
    size, widths = _layout(pdf, columns, headings, body, totals)
    row_height = _ROW_HEIGHT * size / _FONT_SIZE
    head_line = _HEAD_LINE * size / _FONT_SIZE
    bottom = pdf.h - _BOTTOM
    pdf.set_draw_color(*_RULE)
    pdf.set_line_width(0.1)

    def heading() -> float:
        pdf.set_font(SEMIBOLD, "", size)
        lines = max(
            len(pdf.multi_cell(w, head_line, text, dry_run=True, output="LINES")) for w, text in zip(widths, headings)
        )
        height = lines * head_line + 2 * _PADDING
        top = pdf.get_y()
        pdf.set_fill_color(*_HEAD_FILL)
        pdf.rect(pdf.l_margin, top, pdf.epw, height, style="F")
        pdf.set_text_color(255, 255, 255)
        x = pdf.l_margin
        for w, text, align in zip(widths, headings, aligns):
            pdf.set_xy(x, top + _PADDING)
            pdf.multi_cell(w, head_line, text, align=align)
            x += w
        pdf.set_font(FAMILY, "", size)
        pdf.set_text_color(*_INK)
        return top + height

    def row(values: list[str], y: float, zebra: bool) -> float:
        if y + row_height > bottom:
            pdf.add_page()
            y = heading()
        if zebra:
            pdf.set_fill_color(*_ZEBRA)
            pdf.rect(pdf.l_margin, y, pdf.epw, row_height, style="F")
        x = pdf.l_margin
        for w, text, align, whole in zip(widths, values, aligns, rigid):
            pdf.set_xy(x, y)
            pdf.cell(w, row_height, text if whole else _fit(pdf, text, w - 2 * _PADDING), align=align)
            x += w
        pdf.line(pdf.l_margin, y + row_height, pdf.l_margin + pdf.epw, y + row_height)
        return y + row_height

    y = heading()
    for number, values in enumerate(body):
        y = row(values, y, number % 2 == 1)
    if totals is not None:
        pdf.set_font(FAMILY, "B", size)
        row(totals, y, False)
        pdf.set_font(FAMILY, "", size)


def _layout(
    pdf: FPDF, columns, headings: list[str], body: list[list[str]], totals: list[str] | None
) -> tuple[float, list[float]]:
    pdf.set_font(FAMILY, "", _FONT_SIZE)
    natural = [max((pdf.get_string_width(values[i]) for values in body), default=0.0) for i in range(len(columns))]
    if totals is not None:
        pdf.set_font(FAMILY, "B", _FONT_SIZE)
        natural = [max(width, pdf.get_string_width(text)) for width, text in zip(natural, totals)]
    pdf.set_font(SEMIBOLD, "", _FONT_SIZE)
    words = [max(pdf.get_string_width(word) for word in (text.split() or [""])) for text in headings]
    rigid = [_rigid(column) for column in columns]

    for size in _FONT_SIZES:
        ratio = size / _FONT_SIZE
        need = [max(n, w) * ratio + 2 * _PADDING + _SLACK for n, w in zip(natural, words)]
        floor = [
            need[i] if rigid[i] else max(words[i] * ratio + 2 * _PADDING, min(need[i], _FLEX_MIN))
            for i in range(len(columns))
        ]
        if sum(floor) <= pdf.epw or size == _FONT_SIZES[-1]:
            return size, _spread(pdf.epw, floor, need, rigid)
    raise AssertionError


def _rigid(column: Column) -> bool:
    return column.numeric or column.format in (DATE, DAY)


def _spread(total: float, floor: list[float], need: list[float], rigid: list[bool]) -> list[float]:
    if sum(floor) > total:
        scale = total / sum(floor)
        return [width * scale for width in floor]
    widths = list(floor)
    extra = total - sum(widths)
    pending = [i for i, fixed in enumerate(rigid) if not fixed and need[i] > widths[i]]
    while extra > 0.01 and pending:
        share = extra / len(pending)
        still = []
        for i in pending:
            add = min(share, need[i] - widths[i])
            widths[i] += add
            extra -= add
            if need[i] - widths[i] > 0.01:
                still.append(i)
        pending = still
    if extra > 0.01:
        grown = sum(widths)
        widths = [width + extra * width / grown for width in widths]
    return widths


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

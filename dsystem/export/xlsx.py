import asyncio
import re
from dataclasses import replace
from datetime import date, datetime, tzinfo
from decimal import Decimal
from io import BytesIO

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name
from xlsxwriter.worksheet import Worksheet

from dsystem.export.columns import DAY, MONEY, QUANTITY, Column, label
from dsystem.export.sheet import Sheet, meta_text, title_text

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_TITLE_ROW = 0
_META_ROW = 1
_HEADER_ROW = 2
_FIRST_DATA_ROW = 3
_SHEET_NAME_FORBIDDEN = re.compile(r"[\[\]:*?/\\]")
_BOOK_OPTIONS = {
    "constant_memory": True,
    "strings_to_formulas": False,
    "strings_to_urls": False,
    "strings_to_numbers": False,
}
_TITLE = {"bold": True, "font_size": 14}
_META = {"font_color": "#6E6B7B", "font_size": 9}
_HEADER = {
    "bold": True,
    "font_color": "#FFFFFF",
    "bg_color": "#7367F0",
    "border": 1,
    "text_wrap": True,
    "valign": "vcenter",
}
_TOTAL = {"bold": True, "top": 2}
_PADDING = 2
_MAX_TEXT_WIDTH = 60


async def render_xlsx(sheet: Sheet) -> bytes:
    return await asyncio.to_thread(workbook_bytes, replace(sheet, rows=list(sheet.rows)))


def workbook_bytes(sheet: Sheet) -> bytes:
    buffer = BytesIO()
    book = xlsxwriter.Workbook(buffer, _BOOK_OPTIONS)
    ws = book.add_worksheet(_sheet_name(sheet.title))
    columns = sheet.columns
    last_col = len(columns) - 1
    cell_formats = [book.add_format({"num_format": c.format}) if c.format else None for c in columns]
    total_formats = [book.add_format({**_TOTAL, "num_format": c.format} if c.format else _TOTAL) for c in columns]

    widths = [float(column.width) for column in columns]
    _write_title(ws, book, sheet, last_col)
    ws.write_string(_META_ROW, 0, meta_text(sheet), book.add_format(_META))
    header = book.add_format(_HEADER)
    for index, column in enumerate(columns):
        ws.write_string(_HEADER_ROW, index, label(f"report.column.{column.key}", sheet.lang), header)

    sums: dict[int, Decimal] = {index: Decimal(0) for index, column in enumerate(columns) if column.total}
    row_index = _FIRST_DATA_ROW
    for row in sheet.rows:
        for index, value in enumerate(row):
            _write(ws, row_index, index, value, cell_formats[index], sheet.zone)
            widths[index] = max(widths[index], _display_width(value, columns[index]))
            if index in sums and isinstance(value, (Decimal, int, float)) and not isinstance(value, bool):
                sums[index] += Decimal(str(value))
        row_index += 1

    last_data_row = row_index - 1
    if sums:
        _write_totals(ws, sheet, sums, total_formats, row_index, last_data_row)
        for index, value in sums.items():
            widths[index] = max(widths[index], _display_width(value, columns[index]) + 1)
    for index, width in enumerate(widths):
        ws.set_column(index, index, width)
    ws.freeze_panes(_FIRST_DATA_ROW, 0)
    ws.autofilter(_HEADER_ROW, 0, max(last_data_row, _HEADER_ROW), last_col)
    book.close()
    return buffer.getvalue()


def _write_title(ws: Worksheet, book, sheet: Sheet, last_col: int) -> None:
    text = title_text(sheet)
    fmt = book.add_format(_TITLE)
    if last_col > 0:
        ws.merge_range(_TITLE_ROW, 0, _TITLE_ROW, last_col, text, fmt)
    else:
        ws.write_string(_TITLE_ROW, 0, text, fmt)


def _write_totals(
    ws: Worksheet, sheet: Sheet, sums: dict[int, Decimal], formats: list, row_index: int, last_data_row: int
) -> None:
    for index in range(len(sheet.columns)):
        if index in sums:
            if last_data_row < _FIRST_DATA_ROW:
                ws.write_number(row_index, index, 0, formats[index])
                continue
            col = xl_col_to_name(index)
            formula = f"=SUBTOTAL(9,{col}{_FIRST_DATA_ROW + 1}:{col}{last_data_row + 1})"
            ws.write_formula(row_index, index, formula, formats[index], float(sums[index]))
        elif index == 0:
            ws.write_string(row_index, 0, label("report.total", sheet.lang), formats[0])
        else:
            ws.write_blank(row_index, index, None, formats[index])


def _write(ws: Worksheet, row: int, col: int, value, fmt, zone: tzinfo) -> None:
    if value is None or value == "":
        ws.write_blank(row, col, None, fmt)
    elif isinstance(value, bool):
        ws.write_boolean(row, col, value, fmt)
    elif isinstance(value, (Decimal, int, float)):
        ws.write_number(row, col, float(value), fmt)
    elif isinstance(value, datetime):
        local = value.astimezone(zone) if value.tzinfo is not None else value
        ws.write_datetime(row, col, local.replace(tzinfo=None), fmt)
    elif isinstance(value, date):
        ws.write_datetime(row, col, datetime(value.year, value.month, value.day), fmt)
    else:
        ws.write_string(row, col, str(value), fmt)


def _display_width(value, column: Column) -> float:
    if value is None or value == "" or isinstance(value, bool):
        return 0
    if isinstance(value, (Decimal, int, float)):
        decimals = 2 if column.format == MONEY else 3 if column.format == QUANTITY else 0
        return len(f"{Decimal(str(value)):,.{decimals}f}") + _PADDING
    if isinstance(value, datetime):
        return (10 if column.format == DAY else 16) + _PADDING
    if isinstance(value, date):
        return 10 + _PADDING
    return min(len(str(value)) + _PADDING, _MAX_TEXT_WIDTH)


def _sheet_name(title: str) -> str:
    return _SHEET_NAME_FORBIDDEN.sub(" ", title).strip()[:31] or "Report"

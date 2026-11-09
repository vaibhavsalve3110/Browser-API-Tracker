"""openpyxl helpers: consistent header styling and safe text cells."""
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .common import clean_text

CELL_LIMIT = 32000  # Excel's hard cap is 32767 characters per cell

_HEADER_FONT = Font(bold=True, color='FFFFFFFF')
_HEADER_FILL = PatternFill('solid', fgColor='FF1C1E21')
_BODY_ALIGN = Alignment(vertical='top', wrap_text=True)


def new_workbook():
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.creator = 'Browser API Tracker'
    wb.properties.created = datetime.now()
    return wb


def add_sheet(wb, title, columns):
    """columns: list of (header, key, width). Returns the worksheet with a styled header row."""
    ws = wb.create_sheet(title)
    for i, (header, _key, width) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=i, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(vertical='center')
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = 'A2'
    return ws


def add_row(ws, columns, data):
    """Append one row; text is stripped of illegal characters and never treated as a formula."""
    row = ws.max_row + 1
    for i, (_header, key, _width) in enumerate(columns, start=1):
        value = data.get(key, '')
        cell = ws.cell(row=row, column=i)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cell.value = value
        else:
            text = clean_text(value, CELL_LIMIT)
            cell.value = text
            if text.startswith('='):
                cell.data_type = 's'  # keep response bodies like "=..." as plain text
        cell.alignment = _BODY_ALIGN


def finish_sheet(ws, column_count):
    ws.auto_filter.ref = f'A1:{get_column_letter(column_count)}1'

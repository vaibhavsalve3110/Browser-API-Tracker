"""api-list.xlsx: Page Name / Event Name / Method / API URL / Status / Repeats, one row per call."""
from io import BytesIO

from .common import event_name
from .xlsx_helpers import add_row, add_sheet, finish_sheet, new_workbook

COLUMNS = [
    ('Page Name', 'page', 35),
    ('Event Name', 'event', 35),
    ('Method', 'method', 10),
    ('API URL', 'url', 65),
    ('Status', 'status', 10),
    ('Repeats', 'repeats', 10),
]


def build_api_list_xlsx(events, calls_by_event):
    wb = new_workbook()
    ws = add_sheet(wb, 'API List', COLUMNS)
    for ev in events:
        for call in calls_by_event.get(ev['id'], []):
            add_row(ws, COLUMNS, {
                'page': ev.get('title') or ev['url'],
                'event': event_name(ev),
                'method': call['method'],
                'url': call['url'],
                'status': call['status'] if call.get('status') is not None else 'FAILED',
                'repeats': call['count'] if call.get('count', 1) > 1 else 1,
            })
    finish_sheet(ws, len(COLUMNS))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()

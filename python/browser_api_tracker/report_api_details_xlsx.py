"""api-details.xlsx: no screenshots. API calls with headers/payloads, hardcoded keys found in
page JavaScript, client signature/auth values, and where client JS sets auth."""
from io import BytesIO

from .api_details_data import (build_screen_lookup, collect_call_rows, collect_key_rows,
                               collect_signature_rows)
from .xlsx_helpers import add_row, add_sheet, finish_sheet, new_workbook

DETAILS = [
    ('Screen Name', 'screen', 30), ('Event Name', 'event', 30), ('Method', 'method', 9),
    ('API URL', 'url', 55), ('Status', 'status', 8), ('Repeats', 'repeats', 8),
    ('Request Headers', 'reqHeaders', 50), ('Request Payload', 'reqBody', 50),
    ('Response Headers', 'resHeaders', 50), ('Response Body', 'resBody', 60),
]
KEYS = [
    ('Screen Name', 'screen', 30), ('Type', 'type', 28), ('Name', 'name', 28), ('Value', 'value', 50),
    ('Script URL', 'script', 55), ('Context in code', 'context', 70),
]
SIGNATURE = [
    ('Screen Name', 'screen', 30), ('Event Name', 'event', 30), ('API URL', 'apiUrl', 50),
    ('Found In', 'where', 18), ('Type', 'type', 26), ('Name', 'name', 26),
    ('Value / Code snippet', 'value', 60), ('Hardcoded in JS?', 'hardcoded', 16),
    ('Script URL', 'script', 55), ('Seen On (calls)', 'seen', 10),
]
AUTH_JS = [
    ('Screen Name', 'screen', 30), ('Header / Field', 'name', 28),
    ('Set To (expression in code)', 'expression', 50), ('Source', 'source', 26),
    ('Script URL', 'script', 55), ('Context in code', 'context', 70),
]


def build_api_details_xlsx(events, calls_by_event, scanner):
    wb = new_workbook()
    call_rows = collect_call_rows(events, calls_by_event)
    sig_rows = collect_signature_rows(call_rows, scanner)
    key_rows, logic_rows, auth_rows = collect_key_rows(scanner, build_screen_lookup(events))

    ws = add_sheet(wb, 'API Details', DETAILS)
    for r in call_rows:
        add_row(ws, DETAILS, r)
    finish_sheet(ws, len(DETAILS))

    ws = add_sheet(wb, 'Hardcoded Keys (JS)', KEYS)
    for r in key_rows:
        add_row(ws, KEYS, r)
    finish_sheet(ws, len(KEYS))

    ws = add_sheet(wb, 'Client Signature & Auth', SIGNATURE)
    for r in sig_rows + logic_rows:
        add_row(ws, SIGNATURE, r)
    finish_sheet(ws, len(SIGNATURE))

    ws = add_sheet(wb, 'Auth in Client JS', AUTH_JS)
    for r in auth_rows:
        add_row(ws, AUTH_JS, r)
    if not auth_rows:
        add_row(ws, AUTH_JS, {'name': 'None found'})
    finish_sheet(ws, len(AUTH_JS))

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()

"""api-details.docx: no screenshots. Same content as api-details.xlsx, as a Word document."""
from io import BytesIO

from .api_details_data import (build_screen_lookup, collect_call_rows, collect_key_rows,
                               collect_signature_rows)
from .common import clean_text, fmt_datetime
from .docx_helpers import add_code_block, add_heading, add_table, add_text, new_document

BLOCK_LIMIT = 4000  # Word gets slow with huge text blocks, so bodies are capped below Excel's


def _code(doc, label, text):
    if text:
        add_heading(doc, label, 4)
        add_code_block(doc, clean_text(text, BLOCK_LIMIT))


def build_api_details_docx(start_url, started_at, finished_at, events, calls_by_event, scanner):
    call_rows = collect_call_rows(events, calls_by_event)
    sig_rows = collect_signature_rows(call_rows, scanner)
    key_rows, logic_rows, auth_rows = collect_key_rows(scanner, build_screen_lookup(events))

    doc = new_document(landscape=True)
    add_heading(doc, 'API Details', 0)
    add_text(doc, f'Start URL: {start_url}')
    add_text(doc, f'{fmt_datetime(started_at)} - {fmt_datetime(finished_at)} | {len(call_rows)} API calls')
    add_text(doc, 'Contains real request headers, tokens and keys captured from the browser. '
                  'Do not share outside the team.', italic=True, size=9, color='B91C1C')

    add_heading(doc, '1. API calls by screen and event', 1)
    last_group = None
    for r in call_rows:
        group = (r['screen'], r['event'], r['ev']['id'])
        if group != last_group:
            last_group = group
            add_heading(doc, f'Screen: {clean_text(r["screen"], 200)}', 2)
            add_text(doc, f'Event: {r["event"]}', bold=True, size=10)
        add_table(doc, ['Method', 'Status', 'API URL', 'Repeats'], [12, 10, 66, 12],
                  [[r['method'], r['status'], r['url'], f'x{r["repeats"]}' if r['repeats'] > 1 else '1']])
        _code(doc, 'Request Headers', r['reqHeaders'])
        _code(doc, 'Request Payload', r['reqBody'])
        _code(doc, 'Response Headers', r['resHeaders'])
        _code(doc, 'Response Body', r['resBody'])
        doc.add_paragraph()
    if not call_rows:
        add_text(doc, 'No API calls captured.')

    add_heading(doc, '2. Hardcoded keys found in browser JavaScript', 1)
    add_table(doc, ['Screen', 'Type', 'Name', 'Value', 'Script URL'], [18, 16, 16, 24, 26],
              [[k['screen'], k['type'], k['name'], k['value'], k['script']] for k in key_rows])

    add_heading(doc, '3. Client signature and auth values', 1)
    add_table(doc, ['Screen / Event', 'Found In', 'Name', 'Value', 'Hardcoded in JS?', 'API URL'],
              [18, 12, 14, 26, 12, 18],
              [[f'{s["screen"]} / {s["event"]}', f'{s["where"]} ({s["type"]})', s['name'], s['value'],
                s['hardcoded'], s['apiUrl']] for s in sig_rows])

    if logic_rows:
        add_heading(doc, 'Signature / encryption logic in page JavaScript', 2)
        add_table(doc, ['Screen', 'Pattern', 'Code snippet', 'Script URL'], [18, 18, 40, 24],
                  [[l['screen'], l['name'], l['value'], l['script']] for l in logic_rows])

    add_heading(doc, '4. How client JavaScript sets auth', 1)
    if auth_rows:
        add_table(doc, ['Screen', 'Header / Field', 'Set to (code)', 'Source', 'Script URL'],
                  [16, 18, 30, 16, 20],
                  [[a['screen'], a['name'], a['expression'], a['source'], a['script']] for a in auth_rows])
    else:
        add_text(doc, 'None found in the scanned scripts.')

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()

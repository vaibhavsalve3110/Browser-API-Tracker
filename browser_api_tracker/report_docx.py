"""report.docx: technical report as a Word document (screenshots + API calls per event)."""
from io import BytesIO

from .common import (event_value, fmt_datetime, fmt_time, has_value, js_str, pretty, selector_of,
                     status_text, target_text)
from .docx_helpers import (add_code_block, add_heading, add_screenshot, add_table, add_text,
                           new_document)


def build_docx_report(start_url, started_at, finished_at, events, calls_by_event):
    doc = new_document()
    add_heading(doc, 'Browser Session Report', 0)
    add_text(doc, f'Start URL: {start_url}')
    add_text(doc, f'{fmt_datetime(started_at)} - {fmt_datetime(finished_at)} | {len(events)} events')

    for ev in events:
        add_heading(doc, f'#{ev["id"]} {ev["type"]} ({fmt_time(ev["timestamp"])})', 1)
        add_text(doc, f'Page: {ev["url"]}')
        if selector_of(ev):
            text = f' — "{target_text(ev)}"' if target_text(ev) else ''
            add_text(doc, f'Element: {selector_of(ev)}{text}')
        if has_value(ev):
            add_text(doc, f'Value: {js_str(event_value(ev))}')
        add_screenshot(doc, ev.get('screenshot'))

        calls = calls_by_event.get(ev['id'], [])
        add_heading(doc, f'API Calls Triggered ({len(calls)})', 2)
        if not calls:
            add_text(doc, 'No API calls captured for this event.')
        for c in calls:
            count = c.get('count', 1)
            add_table(doc, ['Method', 'Status', 'URL', 'Repeats'], [18, 12, 55, 15],
                      [[c['method'], status_text(c), c['url'], f'x{count}' if count > 1 else '1']],
                      font_size=9)
            if count > 1:
                add_text(doc, f'Sent {count} times in a row (identical method, URL, payload & status) '
                              f'— last at {fmt_time(c["lastTimestamp"])}.', italic=True, size=9)
            if c.get('postData'):
                add_heading(doc, 'Request Payload', 3)
                add_code_block(doc, _cap(pretty(c['postData'])), size=8)
            if c.get('responseBody'):
                add_heading(doc, 'Response Body', 3)
                add_code_block(doc, _cap(pretty(c['responseBody'])), size=8)
            doc.add_paragraph()

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _cap(text, limit=4000):
    return text if len(text) <= limit else f'{text[:limit]}\n...[truncated, {len(text)} chars total]'

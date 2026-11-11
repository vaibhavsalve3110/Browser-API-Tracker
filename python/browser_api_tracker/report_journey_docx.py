"""journey.docx: readable, step-by-step User Journey narrative (Word)."""
from io import BytesIO

from .common import event_value, fmt_datetime, fmt_time, has_value, js_str, selector_of, target_text
from .docx_helpers import add_heading, add_screenshot, add_text, new_document

# Intermediate "started typing" moments are skipped: only the completed action per field shows.
SKIP_TYPES = {'input_start'}


def _describe_step(ev):
    label = selector_of(ev) or 'element'
    text = target_text(ev)
    value = js_str(event_value(ev)) if has_value(ev) else None
    t = ev['type']
    if t == 'page_load':
        return f'Opened the page: {ev["url"]}'
    if t == 'click':
        return f'Clicked "{text or label}" ({label})'
    if t == 'input_end':
        return f'Entered "{value if value is not None else ""}" into {label}'
    if t == 'change':
        return f'Selected/changed {label}' + (f' to "{value}"' if value is not None else '')
    if t == 'submit':
        return f'Submitted the form ({label})'
    return f'{t} on {label}'


def build_journey_docx(start_url, started_at, finished_at, events):
    steps = [ev for ev in events if ev['type'] not in SKIP_TYPES]
    doc = new_document()
    add_heading(doc, 'User Journey', 0)
    add_text(doc, f'Start URL: {start_url}')
    add_text(doc, f'{fmt_datetime(started_at)} - {fmt_datetime(finished_at)} | {len(steps)} steps')
    doc.add_paragraph()

    for i, ev in enumerate(steps, start=1):
        add_heading(doc, f'Step {i}: {_describe_step(ev)}', 1)
        add_text(doc, f'Page: {ev["url"]}  •  {fmt_time(ev["timestamp"])}',
                 italic=True, size=9, color='666666')
        add_screenshot(doc, ev.get('screenshot'))
        doc.add_paragraph()

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()

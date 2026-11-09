"""testcases.xlsx: Excel test cases derived from the captured screens / interactions."""
import os
from io import BytesIO

from .common import event_value, has_value, js_str, selector_of, target_text
from .xlsx_helpers import add_row, add_sheet, finish_sheet, new_workbook

# input_start is an intermediate "began typing" marker, not a completed action.
SKIP_TYPES = {'input_start'}

COLUMNS = [
    ('Test Case ID', 'id', 14),
    ('Test Scenario', 'scenario', 45),
    ('Precondition', 'precondition', 30),
    ('Test Steps', 'steps', 45),
    ('Related API Call(s)', 'apis', 45),
    ('Expected Result', 'expected', 45),
    ('Screenshot', 'screenshot', 35),
]


def _scenario_for(ev):
    label = selector_of(ev) or 'the page'
    text = f' ("{target_text(ev)}")' if target_text(ev) else ''
    t = ev['type']
    if t == 'page_load':
        return 'Verify the page loads successfully'
    if t == 'click':
        return f'Verify clicking {label}{text} performs the expected action'
    if t == 'input_end':
        return f'Verify entering a value into {label}{text} is accepted'
    if t == 'change':
        return f'Verify selecting/changing {label}{text} updates the state correctly'
    if t == 'submit':
        return f'Verify submitting the form ({label}) completes the expected workflow'
    return f'Verify {t} on {label}{text} behaves as expected'


def _steps_for(ev):
    label = selector_of(ev) or 'the page'
    t = ev['type']
    lines = [f'1. Navigate to {ev["url"]}']
    if t == 'page_load':
        lines[0] = f'1. Navigate to {ev["url"]} and wait for it to finish loading'
    elif t == 'click':
        lines.append(f'2. Click on {label}')
    elif t == 'input_end':
        lines.append(f'2. Enter a value into {label}')
        lines.append('3. Move focus away from the field (blur) or proceed to the next field')
    elif t == 'change':
        lines.append(f'2. Change the value of {label}')
    elif t == 'submit':
        lines.append('2. Fill in the required fields')
        lines.append(f'3. Submit the form ({label})')
    else:
        lines.append(f'2. Perform "{t}" on {label}')
    if has_value(ev):
        value = event_value(ev)
        if value != '' and t != 'change':
            lines.append(f'Test data: {js_str(value)}')
    return '\n'.join(lines)


def _expected_result_for(calls):
    if not calls:
        return 'UI updates as expected (no backend API call was triggered by this action).'
    failed = [c for c in calls if c.get('status') is None or c['status'] >= 400]
    if failed:
        codes = ', '.join(str(c['status']) if c.get('status') is not None else 'FAILED' for c in failed)
        return f'Verify error handling — one or more API calls returned a non-success status ({codes}).'
    statuses = []
    for c in calls:
        if c['status'] not in statuses:
            statuses.append(c['status'])
    return f'All triggered API call(s) return a success status ({", ".join(str(s) for s in statuses)}).'


def _relative(path, start):
    try:
        return os.path.relpath(path, start)
    except ValueError:  # different drive on Windows: keep the absolute path
        return path


def _api_line(c):
    repeat = f" (x{c['count']})" if c.get('count', 1) > 1 else ''
    status = c['status'] if c.get('status') is not None else 'FAILED'
    return f"{c['method']} {c['url']}{repeat} -> {status}"


def build_xlsx_report(start_url, events, calls_by_event, session_dir):
    wb = new_workbook()
    ws = add_sheet(wb, 'Test Cases', COLUMNS)
    number = 1
    for ev in (e for e in events if e['type'] not in SKIP_TYPES):
        calls = calls_by_event.get(ev['id'], [])
        api_text = '\n'.join(_api_line(c) for c in calls) if calls else 'None'
        shot = _relative(ev['screenshot'], session_dir) if ev.get('screenshot') else ''
        add_row(ws, COLUMNS, {
            'id': f'TC-{number:03d}',
            'scenario': _scenario_for(ev),
            'precondition': f'User is on: {ev["url"]}',
            'steps': _steps_for(ev),
            'apis': api_text,
            'expected': _expected_result_for(calls),
            'screenshot': shot,
        })
        number += 1
    finish_sheet(ws, len(COLUMNS))
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()

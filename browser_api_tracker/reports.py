"""Correlates API calls with events and writes every report into the session folder."""
import json
import os

from .report_api_details_docx import build_api_details_docx
from .report_api_details_xlsx import build_api_details_xlsx
from .report_api_html import build_api_html_report
from .report_api_list_xlsx import build_api_list_xlsx
from .report_docx import build_docx_report
from .report_html import build_html_report
from .report_journey_docx import build_journey_docx
from .report_xlsx import build_xlsx_report


def _call_key(c):
    return json.dumps([c['method'], c['url'], c.get('postData') or '', c.get('status')])


def collapse_consecutive_duplicates(calls):
    """Collapse an API call repeated back-to-back (same method, URL, payload, status) into one
    row with a repeat count."""
    result = []
    for c in calls:
        if result and _call_key(result[-1]) == _call_key(c):
            result[-1]['count'] += 1
            result[-1]['lastTimestamp'] = c['timestamp']
        else:
            result.append({**c, 'count': 1, 'lastTimestamp': c['timestamp']})
    return result


def assign_calls_to_events(events, network_calls):
    """Each call belongs to the latest event whose timestamp is <= the call's timestamp."""
    ordered = sorted(events, key=lambda e: e['timestamp'])
    calls_by_event = {ev['id']: [] for ev in ordered}
    for call in network_calls:
        assigned = None
        for ev in ordered:
            if ev['timestamp'] <= call['timestamp']:
                assigned = ev
            else:
                break
        if assigned is not None:
            calls_by_event[assigned['id']].append(call)
    return {eid: collapse_consecutive_duplicates(calls) for eid, calls in calls_by_event.items()}


def _generate_one(label, fn):
    """Runs one report step in isolation: a failure here must not stop the other reports."""
    print(f'  - {label} ... ', end='', flush=True)
    try:
        fn()
        print('done')
        return True
    except Exception as e:  # noqa: BLE001 - report the failure, keep going
        print('FAILED')
        print(f'    {type(e).__name__}: {e}')
        return False


def _write(path, data):
    mode = 'w' if isinstance(data, str) else 'wb'
    with open(path, mode, **({'encoding': 'utf-8'} if mode == 'w' else {})) as fh:
        fh.write(data)


def generate_reports(session_dir, start_url, started_at, finished_at, events, network_calls,
                     calls_by_event, scanner, api_host, write_data=True):
    def out(name):
        return os.path.join(session_dir, name)

    def save_data():
        payload = {'startUrl': start_url, 'startedAt': started_at, 'finishedAt': finished_at,
                   'events': events, 'networkCalls': network_calls, 'jsFindings': scanner.get_results()}
        _write(out('data.json'), json.dumps(payload, indent=2, ensure_ascii=False))

    steps = [
        ('raw data (data.json)', save_data) if write_data else None,
        ('HTML report (report.html)', lambda: _write(out('report.html'), build_html_report(
            start_url, started_at, finished_at, events, calls_by_event))),
        ('API report, no screenshots (api-report.html)', lambda: _write(out('api-report.html'), build_api_html_report(
            start_url, started_at, finished_at, events, calls_by_event, api_host))),
        # Lighter outputs first, so they are on disk even if something interrupts the process
        # before it reaches the larger, image-heavy Word reports below.
        ('API list (api-list.xlsx)', lambda: _write(out('api-list.xlsx'), build_api_list_xlsx(
            events, calls_by_event))),
        ('API details + keys/signatures (api-details.xlsx)', lambda: _write(out('api-details.xlsx'), build_api_details_xlsx(
            events, calls_by_event, scanner))),
        ('API details Word (api-details.docx)', lambda: _write(out('api-details.docx'), build_api_details_docx(
            start_url, started_at, finished_at, events, calls_by_event, scanner))),
        ('test cases (testcases.xlsx)', lambda: _write(out('testcases.xlsx'), build_xlsx_report(
            start_url, events, calls_by_event, session_dir))),
        ('User Journey (journey.docx)', lambda: _write(out('journey.docx'), build_journey_docx(
            start_url, started_at, finished_at, events))),
        ('Word technical report (report.docx)', lambda: _write(out('report.docx'), build_docx_report(
            start_url, started_at, finished_at, events, calls_by_event))),
    ]
    return [_generate_one(label, fn) for label, fn in filter(None, steps)]

"""Shared data shaping for api-details.xlsx and api-details.docx so both always agree."""
import re

from .common import event_name, headers_text, pretty
from .secret_scanner import scan_call


def build_screen_lookup(events):
    by_url = {}
    for ev in events:
        if ev.get('title') and ev['url'] not in by_url:
            by_url[ev['url']] = ev['title']
    return lambda url: by_url.get(url) or url


def collect_call_rows(events, calls_by_event):
    """One row per API call, flattened, in event order."""
    rows = []
    for ev in events:
        for call in calls_by_event.get(ev['id'], []):
            rows.append({
                'screen': ev.get('title') or ev['url'],
                'event': event_name(ev),
                'method': call['method'],
                'url': call['url'],
                'status': call['status'] if call.get('status') is not None else 'FAILED',
                'repeats': call['count'] if call.get('count', 1) > 1 else 1,
                'reqHeaders': headers_text(call.get('requestHeaders')),
                'reqBody': pretty(call.get('postData')),
                'resHeaders': headers_text(call.get('responseHeaders')),
                'resBody': pretty(call.get('responseBody')),
                'call': call,
                'ev': ev,
            })
    return rows


def collect_signature_rows(call_rows, scanner):
    """Unique auth/signature values sent with requests, flagged if they appear in page JS."""
    unique = {}
    for r in call_rows:
        for f in scan_call(r['call']):
            ident = (f['name'], f['value'])
            existing = unique.get(ident)
            if existing:
                existing['seen'] += r['call'].get('count') or 1
                continue
            unique[ident] = {**f, 'screen': r['screen'], 'event': r['event'],
                             'apiUrl': r['url'], 'seen': r['call'].get('count') or 1}
    rows = []
    for f in unique.values():
        script = scanner.find_script_containing(re.sub(r'^Bearer\s+', '', f['value'], flags=re.I))
        rows.append({
            'screen': f['screen'], 'event': f['event'], 'apiUrl': f['apiUrl'], 'where': f['location'],
            'type': f['type'], 'name': f['name'], 'value': f['value'],
            'hardcoded': 'Yes' if script else 'No (runtime value)', 'script': script or '', 'seen': f['seen'],
        })
    return rows


def collect_key_rows(scanner, screen_name):
    results = scanner.get_results()
    rows = [{
        'screen': screen_name(k['screenUrl']), 'type': k['type'], 'name': k['name'],
        'value': k['value'], 'script': k['scriptUrl'], 'context': k['context'],
    } for k in results['keyFindings']]
    if not rows:
        rows.append({'screen': '', 'type': 'None found', 'name': '', 'value': '', 'script': '',
                     'context': f"{results['scriptsScanned']} script(s)/page(s) scanned"})
    logic_rows = [{
        'screen': screen_name(c['screenUrl']), 'event': '', 'apiUrl': '', 'where': 'JS code',
        'type': 'Signature/encryption logic', 'name': c['pattern'], 'value': c['context'],
        'hardcoded': '', 'script': c['scriptUrl'], 'seen': 1,
    } for c in results['cryptoFindings']]
    auth_usage_rows = [{
        'screen': screen_name(a['screenUrl']), 'name': a['name'], 'expression': a['expression'],
        'source': a['source'], 'script': a['scriptUrl'], 'context': a['context'],
    } for a in results.get('authFindings', [])]
    return rows, logic_rows, auth_usage_rows

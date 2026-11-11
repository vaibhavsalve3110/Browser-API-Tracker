"""api-report.html: HTML report with NO screenshots, limited to API calls to one API origin
(default https://pnservices.bandhanmutual.com). Per call: page name, page URL, event name,
request URL, request headers, response headers, request payload and response body."""
import json

from .common import esc, event_name, fmt_datetime, fmt_time, headers_text, origin_of, pretty

DEFAULT_API_HOST = 'https://pnservices.bandhanmutual.com'

_CSS = """
  body { font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 0; background: #f5f6f8; color: #1c1e21; }
  header { background: #1c1e21; color: #fff; padding: 24px 32px; }
  header h1 { margin: 0 0 8px; font-size: 20px; }
  header .sub { color: #b6b9bd; font-size: 13px; line-height: 1.6; }
  header .warn { margin-top: 8px; color: #fca5a5; font-size: 12px; }
  main { max-width: 1100px; margin: 24px auto; padding: 0 16px; }
  .toolbar { margin-bottom: 16px; font-size: 13px; }
  .toolbar button { padding: 5px 12px; margin-right: 6px; border: 1px solid #ccd0d5; background: #fff; border-radius: 6px; cursor: pointer; }
  section.event { background: #fff; border: 1px solid #e1e3e6; border-radius: 8px; padding: 18px 22px; margin-bottom: 18px; }
  section.event h2 { margin: 0 0 10px; font-size: 16px; }
  dl.meta { display: grid; grid-template-columns: 110px 1fr; gap: 4px 12px; margin: 0 0 14px; font-size: 13px; }
  dl.meta dt { color: #777; }
  dl.meta dd { margin: 0; word-break: break-all; }
  .mono { font-family: Consolas, monospace; font-size: 12px; }
  .call { border: 1px solid #e1e3e6; border-radius: 6px; margin-bottom: 8px; overflow: hidden; }
  .call-error { border-color: #e3897a; }
  .call summary { display: flex; gap: 10px; align-items: center; padding: 8px 12px; cursor: pointer; background: #fafbfc; font-size: 12px; font-family: Consolas, monospace; }
  .call summary .method { font-weight: 700; padding: 2px 6px; border-radius: 3px; background: #e0e7ff; color: #3346c9; }
  .method-POST { background: #dcfce7 !important; color: #15803d !important; }
  .method-DELETE { background: #fee2e2 !important; color: #b91c1c !important; }
  .method-PUT, .method-PATCH { background: #fef3c7 !important; color: #92400e !important; }
  .call summary .status { font-weight: 600; }
  .call summary .url { color: #444; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
  .call summary .repeat { flex-shrink: 0; font-weight: 700; background: #333; color: #fff; padding: 2px 7px; border-radius: 10px; font-size: 11px; }
  .call-body { padding: 12px; border-top: 1px solid #eee; background: #fcfcfd; }
  .call-body h4 { margin: 10px 0 4px; font-size: 11px; text-transform: uppercase; color: #888; }
  .call-body pre { background: #1c1e21; color: #d4d4d4; padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 12px; margin: 0; white-space: pre-wrap; word-break: break-all; max-height: 480px; overflow-y: auto; }
  .none { color: #888; font-size: 12px; margin: 0; }
"""


def _matches_host(url, api_host):
    a, b = origin_of(url), origin_of(api_host)
    return a is not None and a == b


def _call_key(c):
    return json.dumps([c['method'], c['url'], c.get('postData') or '', c.get('status')])


def _filter_and_collapse(calls, api_host):
    """Filtering can leave identical calls next to each other that had other calls between
    them before, so collapse those again (summing the repeat counts)."""
    out = []
    for c in calls:
        if not _matches_host(c['url'], api_host):
            continue
        if out and _call_key(out[-1]) == _call_key(c):
            out[-1]['count'] += c.get('count', 1)
        else:
            out.append({**c, 'count': c.get('count', 1)})
    return out


def _block(label, text):
    if not text:
        return f'<h4>{label}</h4><p class="none">(none)</p>'
    return f'<h4>{label}</h4><pre>{esc(text)}</pre>'


def _call_html(c):
    error = ' call-error' if c.get('status') is not None and c['status'] >= 400 else ''
    status = c['status'] if c.get('status') is not None else 'FAILED'
    repeat = f'<span class="repeat">&times;{c["count"]}</span>' if c['count'] > 1 else ''
    payload = _block('Request Payload', pretty(c['postData'])) if c.get('postData') else ''
    return (
        f'<details class="call{error}">\n<summary>\n'
        f'<span class="method method-{esc(c["method"])}">{esc(c["method"])}</span>\n'
        f'<span class="status">{status}</span>\n<span class="url">{esc(c["url"])}</span>\n{repeat}\n</summary>\n'
        f'<div class="call-body">\n<h4>Request URL</h4><pre>{esc(c["method"])} {esc(c["url"])}</pre>\n'
        f'{_block("Request Headers", headers_text(c.get("requestHeaders")))}\n{payload}\n'
        f'{_block("Response Headers", headers_text(c.get("responseHeaders")))}\n'
        f'{_block("Response Body", pretty(c.get("responseBody")))}\n</div>\n</details>')


def build_api_html_report(start_url, started_at, finished_at, events, calls_by_event,
                          api_host=DEFAULT_API_HOST):
    total = 0
    sections = []
    for ev in events:
        calls = _filter_and_collapse(calls_by_event.get(ev['id'], []), api_host)
        if not calls:
            continue
        total += len(calls)
        sections.append(
            f'<section class="event" id="event-{ev["id"]}">\n<h2>{esc(event_name(ev))}</h2>\n<dl class="meta">\n'
            f'<dt>Page Name</dt><dd>{esc(ev.get("title") or ev["url"])}</dd>\n'
            f'<dt>Page URL</dt><dd class="mono">{esc(ev["url"])}</dd>\n'
            f'<dt>Event</dt><dd>#{ev["id"]} &middot; {esc(ev["type"])} &middot; {fmt_time(ev["timestamp"])}</dd>\n'
            f'</dl>\n{chr(10).join(_call_html(c) for c in calls)}\n</section>')

    body = '\n'.join(sections) or f'<p class="none">No API calls to {esc(api_host)} were captured.</p>'
    return (
        '<!doctype html>\n<html>\n<head>\n<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n<title>API Report</title>\n'
        f'<style>{_CSS}</style>\n</head>\n<body>\n<header>\n  <h1>API Report &mdash; {esc(api_host)}</h1>\n'
        f'  <div class="sub">Start URL: {esc(start_url)}<br />{fmt_datetime(started_at)} &ndash; '
        f'{fmt_datetime(finished_at)} &nbsp;|&nbsp; {len(sections)} events &nbsp;|&nbsp; '
        f'{total} API calls to {esc(api_host)}</div>\n'
        '  <div class="warn">Contains real request headers and tokens captured from the browser. '
        'Do not share outside the team.</div>\n</header>\n<main>\n  <div class="toolbar">\n'
        '    <button onclick="document.querySelectorAll(\'details.call\').forEach(d => d.open = true)">Expand all</button>\n'
        '    <button onclick="document.querySelectorAll(\'details.call\').forEach(d => d.open = false)">Collapse all</button>\n'
        f'  </div>\n  {body}\n</main>\n</body>\n</html>'
    )

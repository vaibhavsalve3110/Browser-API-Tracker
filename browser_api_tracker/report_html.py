"""report.html: technical report with a screenshot and the triggered API calls per event."""
import base64
import os

from .common import esc, fmt_datetime, fmt_time, has_value, event_value, pretty, pretty_json, target_text

_CSS = """
  body { font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 0; background: #f5f6f8; color: #1c1e21; }
  header { background: #1c1e21; color: #fff; padding: 24px 32px; }
  header h1 { margin: 0 0 8px; font-size: 20px; }
  header .sub { color: #b6b9bd; font-size: 13px; }
  main { max-width: 1000px; margin: 24px auto; padding: 0 16px; }
  nav.toc { background: #fff; border: 1px solid #e1e3e6; border-radius: 8px; padding: 16px 20px; margin-bottom: 24px; }
  nav.toc a { display: inline-block; margin: 2px 8px 2px 0; padding: 3px 8px; background: #eef1f5; border-radius: 4px; font-size: 12px; text-decoration: none; color: #333; }
  section.event { background: #fff; border: 1px solid #e1e3e6; border-radius: 8px; padding: 20px 24px; margin-bottom: 20px; }
  section.event h2 { margin: 0 0 10px; font-size: 16px; }
  section.event h2 .ts { color: #888; font-weight: normal; font-size: 12px; }
  .meta { font-size: 13px; color: #444; margin-bottom: 12px; line-height: 1.6; }
  .meta code { background: #f1f2f4; padding: 1px 5px; border-radius: 3px; }
  img.shot { max-width: 100%; border: 1px solid #ddd; border-radius: 6px; display: block; margin-bottom: 16px; }
  .calls h3 { font-size: 13px; text-transform: uppercase; letter-spacing: .03em; color: #666; margin-bottom: 8px; }
  .calls .none { color: #888; font-size: 13px; }
  .call { border: 1px solid #e1e3e6; border-radius: 6px; margin-bottom: 8px; overflow: hidden; }
  .call-error { border-color: #e3897a; }
  .call-head { display: flex; gap: 10px; align-items: center; padding: 8px 12px; cursor: pointer; background: #fafbfc; font-size: 12px; font-family: Consolas, monospace; }
  .call-head .method { font-weight: 700; padding: 2px 6px; border-radius: 3px; background: #e0e7ff; color: #3346c9; }
  .method-POST { background: #dcfce7; color: #15803d; }
  .method-DELETE { background: #fee2e2; color: #b91c1c; }
  .method-PUT, .method-PATCH { background: #fef3c7; color: #92400e; }
  .call-head .status { font-weight: 600; }
  .call-head .url { color: #444; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
  .call-head .repeat { flex-shrink: 0; font-weight: 700; background: #333; color: #fff; padding: 2px 7px; border-radius: 10px; font-size: 11px; }
  .call-body { display: none; padding: 12px; border-top: 1px solid #eee; background: #fcfcfd; }
  .call.open .call-body { display: block; }
  .call-body h4 { margin: 8px 0 4px; font-size: 11px; text-transform: uppercase; color: #888; }
  .call-body pre { background: #1c1e21; color: #d4d4d4; padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 12px; margin: 0; }
  .call-body .repeat-note { margin: 0 0 10px; font-size: 12px; color: #92400e; background: #fef3c7; padding: 6px 10px; border-radius: 5px; }
"""


def _call_html(c):
    status = c['status'] if c.get('status') is not None else 'FAILED'
    error = ' call-error' if c.get('status') is not None and c['status'] >= 400 else ''
    count = c.get('count', 1)
    parts = [
        f'<div class="call{error}">',
        '<div class="call-head" onclick="this.parentElement.classList.toggle(\'open\')">',
        f'<span class="method method-{esc(c["method"])}">{esc(c["method"])}</span>',
        f'<span class="status">{status}</span>',
        f'<span class="url">{esc(c["url"])}</span>',
    ]
    if count > 1:
        parts.append(f'<span class="repeat">&times;{count}</span>')
    parts.append('</div><div class="call-body">')
    if count > 1:
        parts.append(
            f'<p class="repeat-note">Sent {count} times in a row (identical method, URL, payload &amp; status) '
            f'&mdash; last at {fmt_time(c["lastTimestamp"])}.</p>')
    if c.get('postData'):
        parts.append(f'<h4>Request Payload</h4><pre>{esc(pretty(c["postData"]))}</pre>')
    parts.append(f'<h4>Request Headers</h4><pre>{esc(pretty_json(c.get("requestHeaders") or {}))}</pre>')
    if c.get('responseBody'):
        parts.append(f'<h4>Response Body</h4><pre>{esc(pretty(c["responseBody"]))}</pre>')
    parts.append('</div></div>')
    return '\n'.join(parts)


def build_html_report(start_url, started_at, finished_at, events, calls_by_event):
    blocks = []
    for ev in events:
        calls = calls_by_event.get(ev['id'], [])
        shot = ''
        if ev.get('screenshot') and os.path.exists(ev['screenshot']):
            with open(ev['screenshot'], 'rb') as fh:
                b64 = base64.b64encode(fh.read()).decode('ascii')
            shot = f'<img class="shot" src="data:image/png;base64,{b64}" alt="Screenshot for event {ev["id"]}" />'

        meta = [f'<div><strong>Page:</strong> {esc(ev["url"])}</div>']
        selector = (ev.get('target') or {}).get('selector')
        if selector:
            text = f' &mdash; "{esc(target_text(ev))}"' if target_text(ev) else ''
            meta.append(f'<div><strong>Element:</strong> <code>{esc(selector)}</code> {text}</div>')
        if has_value(ev):
            meta.append(f'<div><strong>Value:</strong> {esc(event_value(ev))}</div>')

        calls_html = '\n'.join(_call_html(c) for c in calls) if calls else \
            '<p class="none">No API calls captured for this event.</p>'
        blocks.append(
            f'<section class="event" id="event-{ev["id"]}">\n'
            f'<h2>#{ev["id"]} &middot; {esc(ev["type"])} <span class="ts">{fmt_time(ev["timestamp"])}</span></h2>\n'
            f'<div class="meta">{"".join(meta)}</div>\n{shot}\n'
            f'<div class="calls"><h3>API Calls Triggered ({len(calls)})</h3>\n{calls_html}</div>\n</section>')

    toc = ''.join(f'<a href="#event-{ev["id"]}">#{ev["id"]} {esc(ev["type"])}</a>' for ev in events)
    return (
        '<!doctype html>\n<html>\n<head>\n<meta charset="utf-8" />\n<title>Browser Session Report</title>\n'
        f'<style>{_CSS}</style>\n</head>\n<body>\n<header>\n  <h1>Browser Session Report</h1>\n'
        f'  <div class="sub">Start URL: {esc(start_url)} &nbsp;|&nbsp; {fmt_datetime(started_at)} &ndash; '
        f'{fmt_datetime(finished_at)} &nbsp;|&nbsp; {len(events)} events</div>\n</header>\n<main>\n'
        f'  <nav class="toc">{toc}</nav>\n{chr(10).join(blocks)}\n</main>\n</body>\n</html>'
    )

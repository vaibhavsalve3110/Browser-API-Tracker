"""Small helpers shared by every report module."""
import html
import json
import re
import struct
from datetime import datetime
from urllib.parse import urlsplit

_CTRL_RE = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\x7f￾￿]')
_DEFAULT_PORTS = {'http': 80, 'https': 443}


def js_str(value):
    """str() that prints booleans / whole floats / null the way the browser reports them."""
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if value is None:
        return 'null'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def clean_text(value, limit):
    """Strip characters that are illegal in XML/Excel and cap the length."""
    s = '' if value is None else js_str(value)
    s = _CTRL_RE.sub('', s)
    if len(s) > limit:
        s = f'{s[:limit]}\n...[truncated, {len(s)} chars total]'
    return s


def esc(value):
    """HTML-escape (& < > only) after dropping control characters."""
    s = '' if value is None else js_str(value)
    return html.escape(_CTRL_RE.sub('', s), quote=False)


def pretty(body):
    """Pretty-print JSON bodies; anything else is returned unchanged."""
    if not body:
        return ''
    try:
        return json.dumps(json.loads(body), indent=2, ensure_ascii=False)
    except (ValueError, RecursionError):
        return body


def pretty_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)


def headers_text(headers):
    return '\n'.join(f'{k}: {v}' for k, v in (headers or {}).items())


def fmt_time(ms):
    return datetime.fromtimestamp(ms / 1000).strftime('%H:%M:%S')


def fmt_datetime(ms):
    return datetime.fromtimestamp(ms / 1000).strftime('%Y-%m-%d %H:%M:%S')


def selector_of(ev):
    return (ev.get('target') or {}).get('selector') or ''


def target_text(ev):
    return (ev.get('target') or {}).get('text') or ''


def has_value(ev):
    extra = ev.get('extra')
    return isinstance(extra, dict) and 'value' in extra


def event_value(ev):
    return ev['extra']['value'] if has_value(ev) else None


def event_name(ev):
    """Human-readable event label used by the Excel/HTML API reports."""
    label = selector_of(ev)
    suffix = f' - {label}' if label else ''
    t = ev.get('type')
    names = {
        'page_load': 'Page load',
        'click': 'Click',
        'input_start': 'Started typing',
        'input_end': 'Entered value',
        'change': 'Changed',
        'submit': 'Submit',
    }
    if t == 'page_load':
        return 'Page load'
    return f'{names.get(t, t)}{suffix}'


def status_text(call):
    return call['status'] if call.get('status') is not None else 'FAILED'


def png_size(data):
    """Read width/height from a PNG header (IHDR); fall back to 800x450."""
    if len(data) < 24 or data[:4] != b'\x89PNG':
        return 800, 450
    width, height = struct.unpack('>II', data[16:24])
    if not width or not height:
        return 800, 450
    return width, height


def origin_of(url):
    """scheme://host[:port] (default ports dropped), or None if the URL has no host."""
    try:
        parts = urlsplit(url)
        if not parts.scheme or not parts.hostname:
            return None
        port = parts.port
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    host = parts.hostname.lower()
    if ':' in host:  # IPv6 literal
        host = f'[{host}]'
    extra = f':{port}' if port and port != _DEFAULT_PORTS.get(scheme) else ''
    return f'{scheme}://{host}{extra}'

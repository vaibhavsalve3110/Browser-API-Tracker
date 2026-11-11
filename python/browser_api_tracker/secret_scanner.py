"""Finds hardcoded keys / signature logic in the JavaScript a page loads, and pulls
auth/signature values out of captured API requests. Heuristic: results are leads to
verify, not proof."""
import asyncio
import json
import re
from urllib.parse import parse_qsl

MAX_SCRIPT_BYTES = 3 * 1024 * 1024
MAX_TOTAL_SOURCE_CHARS = 80 * 1024 * 1024
MAX_FINDINGS_PER_SCRIPT = 50

_NAME_PART = (
    r'(?:api[_-]?key|apikey|app[_-]?key|app[_-]?secret|client[_-]?secret|client[_-]?id|client[_-]?key|'
    r'access[_-]?key|secret[_-]?key|private[_-]?key|encryption[_-]?key|enc[_-]?key|aes[_-]?key|hmac[_-]?key|'
    r'sign(?:ature|ing)?[_-]?key|auth[_-]?token|access[_-]?token|secret|passphrase|password|salt)'
)
ASSIGN_RE = re.compile(
    r'(' + _NAME_PART + r'[\w$-]*)["\']?\s*[:=]\s*["\']([^"\'\s\\]{8,200})["\']', re.I)

TOKEN_FORMATS = [
    ('Google API key', re.compile(r'AIza[0-9A-Za-z_-]{35}')),
    ('AWS access key id', re.compile(r'AKIA[0-9A-Z]{16}')),
    ('Private/public key block', re.compile(r'-----BEGIN (?:RSA |EC |)(?:PRIVATE|PUBLIC) KEY-----')),
    ('JWT', re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}')),
    ('Stripe key', re.compile(r'\b[sp]k_(?:live|test)_[0-9A-Za-z]{16,}')),
    ('Razorpay key', re.compile(r'rzp_(?:live|test)_[0-9A-Za-z]{14,}')),
    ('Hardcoded Bearer token', re.compile(r'Bearer\s+[A-Za-z0-9._~+/-]{24,}')),
]

CRYPTO_RE = re.compile(
    r'(CryptoJS\.(?:AES|DES|TripleDES|Rabbit|RC4)\.(?:encrypt|decrypt)'
    r'|\bHmac(?:SHA(?:1|224|256|384|512)|MD5)\s*\('
    r'|createHmac\s*\('
    r'|crypto\.subtle\.(?:sign|verify|encrypt|decrypt|importKey)\s*\('
    r'|new\s+JSEncrypt'
    r'|\.setPublicKey\s*\('
    r'|forge\.(?:hmac|cipher|pki)'
    r'|\bsha256\s*\(|\bmd5\s*\()'
)

# Where client JS attaches auth: header-name literals plus what they are set to,
# setRequestHeader calls, and Bearer/Basic string building.
AUTH_USAGE_RE = re.compile(
    r'''["']((?:Authorization|x-[\w-]*(?:key|token|auth|sign|client|secret)[\w-]*|api[-_]?key))["']\s*[:\]]\s*=?\s*([^,;}\n]{1,100})'''
    r'''|setRequestHeader\(\s*["']([^"']*(?:auth|key|token|sign|client|secret)[^"']*)["']\s*,\s*([^)]{1,100})\)'''
    r'''|((?:Bearer|Basic)\s*["'`]\s*\+|`(?:Bearer|Basic)\s*\$\{[^}]{0,60}\})''',
    re.I)
_LITERAL_RE = re.compile(r'''^(["'])(?:(?!\1).)*\1\s*\)?$''')

HEADER_NAME_RE = re.compile(r'(auth|api[-_]?key|apikey|client|signature|sign|hmac|token|secret|key|nonce|checksum)', re.I)
HEADER_IGNORE_RE = re.compile(
    r'^(sec-|accept|content-|user-agent|origin|referer|host|cache-control|pragma|connection|cookie|'
    r'x-requested-with|x-client-data|keep-alive)', re.I)
PAYLOAD_NAME_RE = re.compile(
    r'(signature|^sign$|hmac|checksum|api[_-]?key|apikey|secret|client[_-]?id|client[_-]?key|token|nonce)', re.I)

_WS_RE = re.compile(r'\s+')


def _snippet(text, index, length, pad):
    return _WS_RE.sub(' ', text[max(0, index - pad): index + length + pad]).strip()[:300]


def _looks_like_secret(v):
    if len(v) < 8:
        return False
    if re.match(r'^(https?:|/|\.|#)', v):
        return False
    if re.match(r'^[a-z]+(?:[-_.][a-z]+)*$', v, re.I):
        return False
    return bool(re.search(r'\d', v)) or (len(v) >= 16 and bool(re.search('[a-z]', v)) and bool(re.search('[A-Z]', v)))


def scan_source(text, url):
    """Returns {'keys': [...], 'crypto': [...], 'auth': [...]} for one script/page body."""
    keys, crypto, auth = [], [], []
    seen = set()

    def add(type_, name, value, index, length):
        ident = f'{name}\u0000{value}'
        if ident in seen or len(keys) >= MAX_FINDINGS_PER_SCRIPT:
            return
        seen.add(ident)
        keys.append({'type': type_, 'name': name, 'value': value,
                     'context': _snippet(text, index, length, 60), 'scriptUrl': url})

    for m in ASSIGN_RE.finditer(text):
        if _looks_like_secret(m.group(2)):
            add('Hardcoded key/secret assignment', m.group(1), m.group(2), m.start(), len(m.group(0)))
    for type_, regex in TOKEN_FORMATS:
        for m in regex.finditer(text):
            add(type_, type_, m.group(0), m.start(), len(m.group(0)))

    auth_seen = set()
    for m in AUTH_USAGE_RE.finditer(text):
        name = m.group(1) or m.group(3) or 'Authorization scheme'
        expr = (m.group(2) or m.group(4) or m.group(5) or '').strip()
        ident = f'{name}\u0001{expr}'
        if ident in auth_seen or len(auth) >= 20:
            continue
        auth_seen.add(ident)
        literal = bool(_LITERAL_RE.match(expr))
        auth.append({
            'name': name,
            'expression': expr,
            'source': 'Literal (hardcoded in code)' if literal else 'Computed / variable',
            'context': _snippet(text, m.start(), len(m.group(0)), 80),
            'scriptUrl': url,
        })

    crypto_seen = set()
    for m in CRYPTO_RE.finditer(text):
        if m.group(0) in crypto_seen or len(crypto) >= 10:
            continue
        crypto_seen.add(m.group(0))
        crypto.append({'pattern': m.group(0).strip(),
                       'context': _snippet(text, m.start(), len(m.group(0)), 120), 'scriptUrl': url})
    return {'keys': keys, 'crypto': crypto, 'auth': auth}


def _scalar_str(value):
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _walk_payload(value, prefix, out, depth):
    if depth > 4 or value is None:
        return
    if isinstance(value, list):
        for i, v in enumerate(value[:20]):
            _walk_payload(v, f'{prefix}[{i}]', out, depth + 1)
    elif isinstance(value, dict):
        for k, v in value.items():
            _walk_payload(v, f'{prefix}.{k}' if prefix else k, out, depth + 1)
    elif prefix and PAYLOAD_NAME_RE.search(prefix.split('.')[-1]) and _scalar_str(value) != '':
        out.append({'location': 'Request payload', 'name': prefix, 'value': _scalar_str(value)})


def _header_type(name):
    if re.search(r'sign|hmac|checksum', name, re.I):
        return 'Client signature'
    if re.search(r'auth|token', name, re.I):
        return 'Auth token (usually session-issued)'
    return 'Client key / id'


def scan_call(call):
    """Auth/signature-looking values in one captured call's request headers and payload."""
    out = []
    for name, value in (call.get('requestHeaders') or {}).items():
        if HEADER_IGNORE_RE.search(name) or not HEADER_NAME_RE.search(name) or not value:
            continue
        out.append({'location': 'Request header', 'name': name, 'value': str(value),
                    'type': _header_type(name)})
    post = call.get('postData')
    if post:
        found = []
        try:
            _walk_payload(json.loads(post), '', found, 0)
        except (ValueError, RecursionError):
            try:
                for k, v in parse_qsl(post, keep_blank_values=True):
                    _walk_payload(v, k, found, 0)
            except ValueError:
                pass
        for f in found:
            out.append({**f, 'type': _header_type(f['name'])})
    return out


class ScriptScanner:
    """Collects every script/document the browser loads and scans it for keys and auth code."""

    def __init__(self, is_excluded):
        self._is_excluded = is_excluded
        self._sources = []
        self._total_chars = 0
        self.key_findings = []
        self.crypto_findings = []
        self.auth_findings = []
        self._pending = set()

    async def _handle(self, response):
        request = response.request
        rtype = request.resource_type
        if rtype not in ('script', 'document'):
            return
        url = request.url
        if url.startswith('data:') or self._is_excluded(url):
            return
        try:
            buf = await response.body()
        except Exception:
            return
        if len(buf) > MAX_SCRIPT_BYTES:
            return
        text = buf.decode('utf-8', errors='replace')

        screen_url = url
        if rtype != 'document':
            try:
                screen_url = request.frame.url
            except Exception:
                pass  # worker / no frame

        found = scan_source(text, url)
        self.auth_findings.extend({**a, 'screenUrl': screen_url} for a in found['auth'])
        self.key_findings.extend({**k, 'screenUrl': screen_url} for k in found['keys'])
        self.crypto_findings.extend({**c, 'screenUrl': screen_url} for c in found['crypto'])

        if self._total_chars + len(text) <= MAX_TOTAL_SOURCE_CHARS:
            self._total_chars += len(text)
            self._sources.append((url, text))

    def on_response(self, response):
        task = asyncio.ensure_future(self._guard(response))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _guard(self, response):
        try:
            await self._handle(response)
        except Exception:
            pass

    async def idle(self, timeout=5.0):
        if self._pending:
            await asyncio.wait(set(self._pending), timeout=timeout)

    def find_script_containing(self, value):
        if not value or len(value) < 8 or len(value) > 2000:
            return None
        for url, text in self._sources:
            if value in text:
                return url
        return None

    def get_results(self):
        return {
            'keyFindings': self.key_findings,
            'cryptoFindings': self.crypto_findings,
            'authFindings': self.auth_findings,
            'scriptsScanned': len(self._sources),
        }


class StaticScanner:
    """Stand-in used when rebuilding reports from a saved data.json (page scripts are gone)."""

    def __init__(self, results=None):
        self._results = {'keyFindings': [], 'cryptoFindings': [], 'authFindings': [], 'scriptsScanned': 0}
        self._results.update(results or {})

    def find_script_containing(self, value):
        return None

    def get_results(self):
        return self._results

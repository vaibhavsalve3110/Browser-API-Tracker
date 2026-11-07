// Finds hardcoded keys / signature logic in the JavaScript a page loads, and pulls
// auth/signature values out of captured API requests. Heuristic: results are leads to
// verify, not proof.

const MAX_SCRIPT_CHARS = 3 * 1024 * 1024;
const MAX_TOTAL_SOURCE_CHARS = 80 * 1024 * 1024;
const MAX_FINDINGS_PER_SCRIPT = 50;

const NAME_PART =
  '(?:api[_-]?key|apikey|app[_-]?key|app[_-]?secret|client[_-]?secret|client[_-]?id|client[_-]?key|' +
  'access[_-]?key|secret[_-]?key|private[_-]?key|encryption[_-]?key|enc[_-]?key|aes[_-]?key|hmac[_-]?key|' +
  'sign(?:ature|ing)?[_-]?key|auth[_-]?token|access[_-]?token|secret|passphrase|password|salt)';
const ASSIGN_RE = new RegExp(`(${NAME_PART}[\\w$-]*)["']?\\s*[:=]\\s*["']([^"'\\s\\\\]{8,200})["']`, 'gi');

const TOKEN_FORMATS = [
  { type: 'Google API key', re: /AIza[0-9A-Za-z_-]{35}/g },
  { type: 'AWS access key id', re: /AKIA[0-9A-Z]{16}/g },
  { type: 'Private/public key block', re: /-----BEGIN (?:RSA |EC |)(?:PRIVATE|PUBLIC) KEY-----/g },
  { type: 'JWT', re: /eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g },
  { type: 'Stripe key', re: /\b[sp]k_(?:live|test)_[0-9A-Za-z]{16,}/g },
  { type: 'Razorpay key', re: /rzp_(?:live|test)_[0-9A-Za-z]{14,}/g },
  { type: 'Hardcoded Bearer token', re: /Bearer\s+[A-Za-z0-9._~+/-]{24,}/g }
];

const CRYPTO_RE = new RegExp(
  '(CryptoJS\\.(?:AES|DES|TripleDES|Rabbit|RC4)\\.(?:encrypt|decrypt)' +
  '|\\bHmac(?:SHA(?:1|224|256|384|512)|MD5)\\s*\\(' +
  '|createHmac\\s*\\(' +
  '|crypto\\.subtle\\.(?:sign|verify|encrypt|decrypt|importKey)\\s*\\(' +
  '|new\\s+JSEncrypt' +
  '|\\.setPublicKey\\s*\\(' +
  '|forge\\.(?:hmac|cipher|pki)' +
  '|\\bsha256\\s*\\(|\\bmd5\\s*\\()',
  'g'
);

// Where client JS attaches auth: header-name literals plus what they are set to,
// setRequestHeader calls, and Bearer/Basic string building.
const AUTH_USAGE_RE = new RegExp(
  '["\']((?:Authorization|x-[\\w-]*(?:key|token|auth|sign|client|secret)[\\w-]*|api[-_]?key))["\']\\s*[:\\]]\\s*=?\\s*([^,;}\\n]{1,100})' +
  '|setRequestHeader\\(\\s*["\']([^"\']*(?:auth|key|token|sign|client|secret)[^"\']*)["\']\\s*,\\s*([^)]{1,100})\\)' +
  '|((?:Bearer|Basic)\\s*["\'`]\\s*\\+|`(?:Bearer|Basic)\\s*\\$\\{[^}]{0,60}\\})',
  'gi'
);

const HEADER_NAME_RE =/(auth|api[-_]?key|apikey|client|signature|sign|hmac|token|secret|key|nonce|checksum)/i;
const HEADER_IGNORE_RE = /^(sec-|accept|content-|user-agent|origin|referer|host|cache-control|pragma|connection|cookie|x-requested-with|x-client-data|keep-alive)/i;
const PAYLOAD_NAME_RE = /(signature|^sign$|hmac|checksum|api[_-]?key|apikey|secret|client[_-]?id|client[_-]?key|token|nonce)/i;

function snippet(text, index, length, pad) {
  return text.slice(Math.max(0, index - pad), index + length + pad).replace(/\s+/g, ' ').trim().slice(0, 300);
}

function looksLikeSecret(v) {
  if (v.length < 8) return false;
  if (/^(https?:|\/|\.|#)/.test(v)) return false;
  if (/^[a-z]+(?:[-_.][a-z]+)*$/i.test(v)) return false;
  return /\d/.test(v) || (v.length >= 16 && /[a-z]/.test(v) && /[A-Z]/.test(v));
}

function scanSource(text, url) {
  const keys = [];
  const crypto = [];
  const seen = new Set();

  const add = (type, name, value, index, len) => {
    const id = `${name}\u0000${value}`;
    if (seen.has(id) || keys.length >= MAX_FINDINGS_PER_SCRIPT) return;
    seen.add(id);
    keys.push({ type, name, value, context: snippet(text, index, len, 60), scriptUrl: url });
  };

  for (const m of text.matchAll(ASSIGN_RE)) {
    if (looksLikeSecret(m[2])) add('Hardcoded key/secret assignment', m[1], m[2], m.index, m[0].length);
  }
  for (const fmt of TOKEN_FORMATS) {
    for (const m of text.matchAll(fmt.re)) add(fmt.type, fmt.type, m[0], m.index, m[0].length);
  }

  const auth = [];
  const authSeen = new Set();
  for (const m of text.matchAll(AUTH_USAGE_RE)) {
    const name = m[1] || m[3] || 'Authorization scheme';
    const expr = (m[2] || m[4] || m[5] || '').trim();
    const id = `${name}\u0001${expr}`;
    if (authSeen.has(id) || auth.length >= 20) continue;
    authSeen.add(id);
    const literal = /^(["'])(?:(?!\1).)*\1\s*\)?$/.test(expr);
    auth.push({
      name,
      expression: expr,
      source: literal ? 'Literal (hardcoded in code)' : 'Computed / variable',
      context: snippet(text, m.index, m[0].length, 80),
      scriptUrl: url
    });
  }

  const cryptoSeen = new Set();
  for (const m of text.matchAll(CRYPTO_RE)) {
    if (cryptoSeen.has(m[0]) || crypto.length >= 10) continue;
    cryptoSeen.add(m[0]);
    crypto.push({ pattern: m[0].trim(), context: snippet(text, m.index, m[0].length, 120), scriptUrl: url });
  }
  return { keys, crypto, auth };
}

function walkPayload(value, prefix, out, depth) {
  if (depth > 4 || value == null) return;
  if (Array.isArray(value)) {
    value.slice(0, 20).forEach((v, i) => walkPayload(v, `${prefix}[${i}]`, out, depth + 1));
  } else if (typeof value === 'object') {
    for (const [k, v] of Object.entries(value)) walkPayload(v, prefix ? `${prefix}.${k}` : k, out, depth + 1);
  } else if (prefix && PAYLOAD_NAME_RE.test(prefix.split('.').pop()) && String(value) !== '') {
    out.push({ location: 'Request payload', name: prefix, value: String(value) });
  }
}

function headerType(name) {
  if (/sign|hmac|checksum/i.test(name)) return 'Client signature';
  if (/auth|token/i.test(name)) return 'Auth token (usually session-issued)';
  return 'Client key / id';
}

function scanCall(call) {
  const out = [];
  for (const [name, value] of Object.entries(call.requestHeaders || {})) {
    if (HEADER_IGNORE_RE.test(name) || !HEADER_NAME_RE.test(name) || !value) continue;
    out.push({ location: 'Request header', name, value: String(value), type: headerType(name) });
  }
  if (call.postData) {
    const found = [];
    try {
      walkPayload(JSON.parse(call.postData), '', found, 0);
    } catch (e) {
      try {
        for (const [k, v] of new URLSearchParams(call.postData)) walkPayload(v, k, found, 0);
      } catch (e2) { /* not form-encoded either */ }
    }
    for (const f of found) out.push({ ...f, type: headerType(f.name) });
  }
  return out;
}

function createScriptScanner({ isExcluded }) {
  const sources = [];
  let totalChars = 0;
  const keyFindings = [];
  const cryptoFindings = [];
  const authFindings = [];
  const pending = new Set();

  async function handle(response) {
    const request = response.request();
    const type = request.resourceType();
    if (type !== 'script' && type !== 'document') return;
    const url = request.url();
    if (url.startsWith('data:') || isExcluded(url)) return;

    let buf;
    try { buf = await response.body(); } catch (e) { return; }
    if (buf.length > MAX_SCRIPT_CHARS) return;
    const text = buf.toString('utf-8');

    let screenUrl = url;
    try { screenUrl = type === 'document' ? url : request.frame().url(); } catch (e) { /* worker/no frame */ }

    const { keys, crypto, auth } = scanSource(text, url);
    auth.forEach(a => authFindings.push({ ...a, screenUrl }));
    keys.forEach(k => keyFindings.push({ ...k, screenUrl }));
    crypto.forEach(c => cryptoFindings.push({ ...c, screenUrl }));

    if (totalChars + text.length <= MAX_TOTAL_SOURCE_CHARS) {
      totalChars += text.length;
      sources.push({ url, text });
    }
  }

  return {
    onResponse(response) {
      const p = handle(response).catch(() => {}).finally(() => pending.delete(p));
      pending.add(p);
    },
    async idle(timeoutMs = 5000) {
      await Promise.race([Promise.all([...pending]), new Promise(r => setTimeout(r, timeoutMs))]);
    },
    findScriptContaining(value) {
      if (!value || value.length < 8 || value.length > 2000) return null;
      const hit = sources.find(s => s.text.includes(value));
      return hit ? hit.url : null;
    },
    getResults() {
      return { keyFindings, cryptoFindings, authFindings, scriptsScanned: sources.length };
    }
  };
}

module.exports = { createScriptScanner, scanSource, scanCall };

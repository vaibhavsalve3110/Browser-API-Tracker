// Shared data shaping for api-details.xlsx and api-details.docx so both always agree.
const { eventName } = require('./reportApiListXlsx');
const { scanCall } = require('./secretScanner');

function cleanText(value, limit) {
  let s = String(value == null ? '' : value).replace(/[\x00-\x08\x0B\x0C\x0E-\x1F￾￿]/g, '');
  if (s.length > limit) s = `${s.slice(0, limit)}\n...[truncated, ${s.length} chars total]`;
  return s;
}

function pretty(body) {
  if (!body) return '';
  try { return JSON.stringify(JSON.parse(body), null, 2); } catch (e) { return body; }
}

function headerLines(headers) {
  return Object.entries(headers || {}).map(([k, v]) => `${k}: ${v}`).join('\n');
}

function buildScreenLookup(events) {
  const byUrl = new Map();
  for (const ev of events) {
    if (ev.title && !byUrl.has(ev.url)) byUrl.set(ev.url, ev.title);
  }
  return url => byUrl.get(url) || url;
}

// One row per API call, flattened, in event order.
function collectCallRows(events, callsByEvent) {
  const rows = [];
  for (const ev of events) {
    for (const call of callsByEvent.get(ev.id) || []) {
      rows.push({
        screen: ev.title || ev.url,
        event: eventName(ev),
        method: call.method,
        url: call.url,
        status: call.status != null ? call.status : 'FAILED',
        repeats: call.count > 1 ? call.count : 1,
        reqHeaders: headerLines(call.requestHeaders),
        reqBody: pretty(call.postData),
        resHeaders: headerLines(call.responseHeaders),
        resBody: pretty(call.responseBody),
        call,
        ev
      });
    }
  }
  return rows;
}

// Unique auth/signature values sent with requests, flagged if they appear in page JS.
function collectSignatureRows(callRows, scanner) {
  const unique = new Map();
  for (const r of callRows) {
    for (const f of scanCall(r.call)) {
      const id = JSON.stringify([f.name, f.value]);
      const existing = unique.get(id);
      if (existing) { existing.seen += r.call.count || 1; continue; }
      unique.set(id, { ...f, screen: r.screen, event: r.event, apiUrl: r.url, seen: r.call.count || 1 });
    }
  }
  return [...unique.values()].map(f => {
    const script = scanner.findScriptContaining(f.value.replace(/^Bearer\s+/i, ''));
    return {
      screen: f.screen, event: f.event, apiUrl: f.apiUrl, where: f.location, type: f.type, name: f.name,
      value: f.value, hardcoded: script ? 'Yes' : 'No (runtime value)', script: script || '', seen: f.seen
    };
  });
}

function collectKeyRows(scanner, screenName) {
  const results = scanner.getResults();
  const rows = results.keyFindings.map(k => ({
    screen: screenName(k.screenUrl), type: k.type, name: k.name, value: k.value, script: k.scriptUrl, context: k.context
  }));
  if (!rows.length) {
    rows.push({ screen: '', type: 'None found', name: '', value: '', script: '', context: `${results.scriptsScanned} script(s)/page(s) scanned` });
  }
  const logicRows = results.cryptoFindings.map(c => ({
    screen: screenName(c.screenUrl), event: '', apiUrl: '', where: 'JS code', type: 'Signature/encryption logic',
    name: c.pattern, value: c.context, hardcoded: '', script: c.scriptUrl, seen: 1
  }));
  const authUsageRows = (results.authFindings || []).map(a => ({
    screen: screenName(a.screenUrl), name: a.name, expression: a.expression, source: a.source, script: a.scriptUrl, context: a.context
  }));
  return { keyRows: rows, logicRows, authUsageRows };
}

module.exports = { cleanText, buildScreenLookup, collectCallRows, collectSignatureRows, collectKeyRows };

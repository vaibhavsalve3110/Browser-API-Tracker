// api-report.html: HTML report with NO screenshots. Only API calls to one API origin
// (default https://pnservices.bandhanmutual.com) are kept. Per call: page name, page URL,
// event name, request URL, request headers, response headers, request payload, response body.
const { eventName } = require('./reportApiListXlsx');

const DEFAULT_API_HOST = 'https://pnservices.bandhanmutual.com';

function esc(str) {
  return String(str == null ? '' : str)
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function pretty(body) {
  if (!body) return '';
  try { return JSON.stringify(JSON.parse(body), null, 2); } catch (e) { return body; }
}

function headersText(headers) {
  const entries = Object.entries(headers || {});
  return entries.length ? entries.map(([k, v]) => `${k}: ${v}`).join('\n') : '';
}

function matchesHost(url, apiHost) {
  try {
    const u = new URL(url);
    const h = new URL(apiHost);
    return u.origin.toLowerCase() === h.origin.toLowerCase();
  } catch (e) {
    return false;
  }
}

const callKey = c => JSON.stringify([c.method, c.url, c.postData || '', c.status]);

// Filtering can leave identical calls next to each other that had other calls between them
// before, so collapse those again (summing the repeat counts).
function filterAndCollapse(calls, apiHost) {
  const out = [];
  for (const c of calls) {
    if (!matchesHost(c.url, apiHost)) continue;
    const last = out[out.length - 1];
    if (last && callKey(last) === callKey(c)) last.count += c.count || 1;
    else out.push({ ...c, count: c.count || 1 });
  }
  return out;
}

function block(label, text) {
  if (!text) return `<h4>${label}</h4><p class="none">(none)</p>`;
  return `<h4>${label}</h4><pre>${esc(text)}</pre>`;
}

function buildApiHtmlReport({ startUrl, startedAt, finishedAt, events, callsByEvent, apiHost = DEFAULT_API_HOST }) {
  let total = 0;
  const groups = [];
  for (const ev of events) {
    const calls = filterAndCollapse(callsByEvent.get(ev.id) || [], apiHost);
    if (!calls.length) continue;
    total += calls.length;
    groups.push({ ev, calls });
  }

  const body = groups.map(({ ev, calls }) => `
    <section class="event" id="event-${ev.id}">
      <h2>${esc(eventName(ev))}</h2>
      <dl class="meta">
        <dt>Page Name</dt><dd>${esc(ev.title || ev.url)}</dd>
        <dt>Page URL</dt><dd class="mono">${esc(ev.url)}</dd>
        <dt>Event</dt><dd>#${ev.id} &middot; ${esc(ev.type)} &middot; ${new Date(ev.timestamp).toLocaleTimeString()}</dd>
      </dl>
      ${calls.map(c => `
      <details class="call ${c.status != null && c.status >= 400 ? 'call-error' : ''}">
        <summary>
          <span class="method method-${esc(c.method)}">${esc(c.method)}</span>
          <span class="status">${c.status != null ? c.status : 'FAILED'}</span>
          <span class="url">${esc(c.url)}</span>
          ${c.count > 1 ? `<span class="repeat">&times;${c.count}</span>` : ''}
        </summary>
        <div class="call-body">
          <h4>Request URL</h4><pre>${esc(c.method)} ${esc(c.url)}</pre>
          ${block('Request Headers', headersText(c.requestHeaders))}
          ${c.postData ? block('Request Payload', pretty(c.postData)) : ''}
          ${block('Response Headers', headersText(c.responseHeaders))}
          ${block('Response Body', pretty(c.responseBody))}
        </div>
      </details>`).join('\n')}
    </section>`).join('\n');

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>API Report</title>
<style>
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
</style>
</head>
<body>
<header>
  <h1>API Report &mdash; ${esc(apiHost)}</h1>
  <div class="sub">Start URL: ${esc(startUrl)}<br />${new Date(startedAt).toLocaleString()} &ndash; ${new Date(finishedAt).toLocaleString()} &nbsp;|&nbsp; ${groups.length} events &nbsp;|&nbsp; ${total} API calls to ${esc(apiHost)}</div>
  <div class="warn">Contains real request headers and tokens captured from the browser. Do not share outside the team.</div>
</header>
<main>
  <div class="toolbar">
    <button onclick="document.querySelectorAll('details.call').forEach(d => d.open = true)">Expand all</button>
    <button onclick="document.querySelectorAll('details.call').forEach(d => d.open = false)">Collapse all</button>
  </div>
  ${body || `<p class="none">No API calls to ${esc(apiHost)} were captured.</p>`}
</main>
</body>
</html>`;
}

module.exports = { buildApiHtmlReport, DEFAULT_API_HOST };

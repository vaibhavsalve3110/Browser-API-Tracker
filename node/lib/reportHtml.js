const fs = require('fs');
const path = require('path');

function esc(str) {
  return String(str == null ? '' : str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function pretty(body) {
  if (!body) return '';
  try {
    return JSON.stringify(JSON.parse(body), null, 2);
  } catch (e) {
    return body;
  }
}

function buildHtmlReport({ startUrl, startedAt, finishedAt, events, callsByEvent }) {
  const eventBlocks = events.map(ev => {
    const calls = callsByEvent.get(ev.id) || [];
    let screenshotTag = '';
    if (ev.screenshot && fs.existsSync(ev.screenshot)) {
      const b64 = fs.readFileSync(ev.screenshot).toString('base64');
      screenshotTag = `<img class="shot" src="data:image/png;base64,${b64}" alt="Screenshot for event ${ev.id}" />`;
    }
    const callRows = calls.map((c, i) => `
      <div class="call ${c.status && c.status >= 400 ? 'call-error' : ''}">
        <div class="call-head" onclick="this.parentElement.classList.toggle('open')">
          <span class="method method-${esc(c.method)}">${esc(c.method)}</span>
          <span class="status">${c.status != null ? c.status : 'FAILED'}</span>
          <span class="url">${esc(c.url)}</span>
          ${c.count > 1 ? `<span class="repeat">&times;${c.count}</span>` : ''}
        </div>
        <div class="call-body">
          ${c.count > 1 ? `<p class="repeat-note">Sent ${c.count} times in a row (identical method, URL, payload &amp; status) &mdash; last at ${new Date(c.lastTimestamp).toLocaleTimeString()}.</p>` : ''}
          ${c.postData ? `<h4>Request Payload</h4><pre>${esc(pretty(c.postData))}</pre>` : ''}
          <h4>Request Headers</h4><pre>${esc(JSON.stringify(c.requestHeaders, null, 2))}</pre>
          ${c.responseBody ? `<h4>Response Body</h4><pre>${esc(pretty(c.responseBody))}</pre>` : ''}
        </div>
      </div>`).join('\n');

    return `
    <section class="event" id="event-${ev.id}">
      <h2>#${ev.id} &middot; ${esc(ev.type)} <span class="ts">${new Date(ev.timestamp).toLocaleTimeString()}</span></h2>
      <div class="meta">
        <div><strong>Page:</strong> ${esc(ev.url)}</div>
        ${ev.target && ev.target.selector ? `<div><strong>Element:</strong> <code>${esc(ev.target.selector)}</code> ${ev.target.text ? '&mdash; "' + esc(ev.target.text) + '"' : ''}</div>` : ''}
        ${ev.extra && ev.extra.value !== undefined ? `<div><strong>Value:</strong> ${esc(ev.extra.value)}</div>` : ''}
      </div>
      ${screenshotTag}
      <div class="calls">
        <h3>API Calls Triggered (${calls.length})</h3>
        ${calls.length ? callRows : '<p class="none">No API calls captured for this event.</p>'}
      </div>
    </section>`;
  }).join('\n');

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>Browser Session Report</title>
<style>
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
</style>
</head>
<body>
<header>
  <h1>Browser Session Report</h1>
  <div class="sub">Start URL: ${esc(startUrl)} &nbsp;|&nbsp; ${new Date(startedAt).toLocaleString()} &ndash; ${new Date(finishedAt).toLocaleString()} &nbsp;|&nbsp; ${events.length} events</div>
</header>
<main>
  <nav class="toc">
    ${events.map(ev => `<a href="#event-${ev.id}">#${ev.id} ${esc(ev.type)}</a>`).join('')}
  </nav>
  ${eventBlocks}
</main>
</body>
</html>`;
}

module.exports = { buildHtmlReport };

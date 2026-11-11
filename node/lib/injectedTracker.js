// Runs INSIDE the browser page (via page.addInitScript). Re-injected automatically
// on every navigation. Reports user interactions back to Node via window.__trackEvent.
function injectedTracker() {
  if (window.__apiTrackerAttached) return;
  window.__apiTrackerAttached = true;

  function describeElement(el) {
    if (!el || el.nodeType !== 1) return { tag: '', selector: '' };
    const tag = el.tagName.toLowerCase();
    const id = el.id || '';
    const cls = typeof el.className === 'string' ? el.className.trim() : '';
    const text = (el.innerText || el.value || el.textContent || '').trim().slice(0, 100);
    let selector = tag;
    if (id) selector += '#' + id;
    else if (cls) selector += '.' + cls.split(/\s+/).filter(Boolean).slice(0, 3).join('.');
    return { tag, id, class: cls, text, selector };
  }

  function send(type, el, extra) {
    try {
      if (window.__trackEvent) {
        window.__trackEvent({
          type,
          url: location.href,
          title: document.title,
          target: describeElement(el),
          extra: extra || null,
          ts: Date.now()
        });
      }
    } catch (e) {
      /* page context may be tearing down during navigation */
    }
  }

  function fieldValue(el) {
    if (!el) return undefined;
    if (el.type === 'password') return '(hidden)';
    if (el.type === 'checkbox' || el.type === 'radio') return el.checked;
    return el.value;
  }

  function isTypedField(el) {
    return !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable) &&
      el.type !== 'checkbox' && el.type !== 'radio';
  }

  // For text/typed fields we only want a screenshot of the FIRST keystroke and the LAST
  // keystroke of a typing session, not one per character. `input` fires on every keystroke,
  // so a session is tracked per-element and only its first and last (on blur) are reported.
  const typingSessions = new WeakSet();

  document.addEventListener('click', function (e) {
    send('click', e.target);
  }, true);

  document.addEventListener('input', function (e) {
    const el = e.target;
    if (!isTypedField(el)) return;
    if (!typingSessions.has(el)) {
      typingSessions.add(el);
      send('input_start', el, { value: fieldValue(el) });
    }
  }, true);

  document.addEventListener('blur', function (e) {
    const el = e.target;
    if (isTypedField(el) && typingSessions.has(el)) {
      typingSessions.delete(el);
      send('input_end', el, { value: fieldValue(el) });
    }
  }, true);

  // Checkboxes, radios and selects aren't "typed" — a single change event is already the
  // whole interaction, so they keep the original one-shot capture.
  document.addEventListener('change', function (e) {
    const el = e.target;
    if (el && (el.tagName === 'SELECT' || (el.tagName === 'INPUT' && (el.type === 'checkbox' || el.type === 'radio')))) {
      send('change', el, { value: fieldValue(el) });
    }
  }, true);

  document.addEventListener('submit', function (e) {
    const el = e.target;
    // A submit usually follows a typing session that hasn't blurred yet (Enter key) — flush
    // its "last" screenshot first so the typed value is still captured.
    if (document.activeElement && isTypedField(document.activeElement) && typingSessions.has(document.activeElement)) {
      typingSessions.delete(document.activeElement);
      send('input_end', document.activeElement, { value: fieldValue(document.activeElement) });
    }
    send('submit', el);
  }, true);

  window.addEventListener('load', function () {
    send('page_load', document.body);
  });
}

module.exports = { injectedTracker };

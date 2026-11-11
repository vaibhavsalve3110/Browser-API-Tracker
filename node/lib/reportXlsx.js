const ExcelJS = require('exceljs');
const path = require('path');

// input_start is an intermediate "began typing" marker (see injectedTracker.js) — it isn't
// a completed action on its own, so it doesn't get its own test case row.
const SKIP_TYPES = new Set(['input_start']);

function scenarioFor(ev) {
  const label = ev.target && ev.target.selector ? ev.target.selector : 'the page';
  const text = ev.target && ev.target.text ? ` ("${ev.target.text}")` : '';
  switch (ev.type) {
    case 'page_load':
      return `Verify the page loads successfully`;
    case 'click':
      return `Verify clicking ${label}${text} performs the expected action`;
    case 'input_end':
      return `Verify entering a value into ${label}${text} is accepted`;
    case 'change':
      return `Verify selecting/changing ${label}${text} updates the state correctly`;
    case 'submit':
      return `Verify submitting the form (${label}) completes the expected workflow`;
    default:
      return `Verify ${ev.type} on ${label}${text} behaves as expected`;
  }
}

function stepsFor(ev) {
  const label = ev.target && ev.target.selector ? ev.target.selector : 'the page';
  const value = ev.extra && ev.extra.value !== undefined ? ev.extra.value : undefined;
  const lines = [`1. Navigate to ${ev.url}`];
  switch (ev.type) {
    case 'page_load':
      lines[0] = `1. Navigate to ${ev.url} and wait for it to finish loading`;
      break;
    case 'click':
      lines.push(`2. Click on ${label}`);
      break;
    case 'input_end':
      lines.push(`2. Enter a value into ${label}`);
      lines.push(`3. Move focus away from the field (blur) or proceed to the next field`);
      break;
    case 'change':
      lines.push(`2. Change the value of ${label}`);
      break;
    case 'submit':
      lines.push(`2. Fill in the required fields`);
      lines.push(`3. Submit the form (${label})`);
      break;
    default:
      lines.push(`2. Perform "${ev.type}" on ${label}`);
  }
  if (value !== undefined && value !== '' && ev.type !== 'change') {
    lines.push(`Test data: ${value}`);
  }
  return lines.join('\n');
}

function expectedResultFor(calls) {
  if (!calls || !calls.length) {
    return 'UI updates as expected (no backend API call was triggered by this action).';
  }
  const failed = calls.filter(c => c.status == null || c.status >= 400);
  if (failed.length) {
    return `Verify error handling — one or more API calls returned a non-success status (${failed.map(c => c.status != null ? c.status : 'FAILED').join(', ')}).`;
  }
  return `All triggered API call(s) return a success status (${[...new Set(calls.map(c => c.status))].join(', ')}).`;
}

async function buildXlsxReport({ startUrl, events, callsByEvent, sessionDir }) {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'Browser API Tracker';
  workbook.created = new Date();

  const sheet = workbook.addWorksheet('Test Cases');
  sheet.columns = [
    { header: 'Test Case ID', key: 'id', width: 14 },
    { header: 'Test Scenario', key: 'scenario', width: 45 },
    { header: 'Precondition', key: 'precondition', width: 30 },
    { header: 'Test Steps', key: 'steps', width: 45 },
    { header: 'Related API Call(s)', key: 'apis', width: 45 },
    { header: 'Expected Result', key: 'expected', width: 45 },
    { header: 'Screenshot', key: 'screenshot', width: 35 }
  ];

  sheet.getRow(1).font = { bold: true, color: { argb: 'FFFFFFFF' } };
  sheet.getRow(1).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1C1E21' } };
  sheet.getRow(1).alignment = { vertical: 'middle' };

  let tcNum = 1;
  const rows = events.filter(ev => !SKIP_TYPES.has(ev.type));

  for (const ev of rows) {
    const calls = (callsByEvent.get(ev.id) || []);
    const apiText = calls.length
      ? calls.map(c => `${c.method} ${c.url}${c.count > 1 ? ` (x${c.count})` : ''} -> ${c.status != null ? c.status : 'FAILED'}`).join('\n')
      : 'None';

    const row = sheet.addRow({
      id: `TC-${String(tcNum++).padStart(3, '0')}`,
      scenario: scenarioFor(ev),
      precondition: `User is on: ${ev.url}`,
      steps: stepsFor(ev),
      apis: apiText,
      expected: expectedResultFor(calls),
      screenshot: ev.screenshot ? path.relative(sessionDir, ev.screenshot) : ''
    });
    row.alignment = { vertical: 'top', wrapText: true };
  }

  sheet.autoFilter = { from: 'A1', to: 'G1' };
  sheet.views = [{ state: 'frozen', ySplit: 1 }];

  return workbook.xlsx.writeBuffer();
}

module.exports = { buildXlsxReport };

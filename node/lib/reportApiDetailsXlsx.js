const ExcelJS = require('exceljs');
const {
  cleanText, buildScreenLookup, collectCallRows, collectSignatureRows, collectKeyRows
} = require('./apiDetailsData');

const CELL_LIMIT = 32000;

function styleHeader(sheet) {
  const row = sheet.getRow(1);
  row.font = { bold: true, color: { argb: 'FFFFFFFF' } };
  row.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1C1E21' } };
  row.alignment = { vertical: 'middle' };
  sheet.views = [{ state: 'frozen', ySplit: 1 }];
}

function addRow(sheet, data) {
  const cleaned = {};
  for (const [k, v] of Object.entries(data)) cleaned[k] = typeof v === 'number' ? v : cleanText(v, CELL_LIMIT);
  sheet.addRow(cleaned).alignment = { vertical: 'top', wrapText: true };
}

async function buildApiDetailsXlsx({ events, callsByEvent, scanner }) {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'Browser API Tracker';
  workbook.created = new Date();

  const callRows = collectCallRows(events, callsByEvent);
  const sigRows = collectSignatureRows(callRows, scanner);
  const { keyRows, logicRows, authUsageRows } = collectKeyRows(scanner, buildScreenLookup(events));

  const details = workbook.addWorksheet('API Details');
  details.columns = [
    { header: 'Screen Name', key: 'screen', width: 30 },
    { header: 'Event Name', key: 'event', width: 30 },
    { header: 'Method', key: 'method', width: 9 },
    { header: 'API URL', key: 'url', width: 55 },
    { header: 'Status', key: 'status', width: 8 },
    { header: 'Repeats', key: 'repeats', width: 8 },
    { header: 'Request Headers', key: 'reqHeaders', width: 50 },
    { header: 'Request Payload', key: 'reqBody', width: 50 },
    { header: 'Response Headers', key: 'resHeaders', width: 50 },
    { header: 'Response Body', key: 'resBody', width: 60 }
  ];
  styleHeader(details);
  callRows.forEach(r => addRow(details, r));
  details.autoFilter = { from: 'A1', to: 'J1' };

  const keys = workbook.addWorksheet('Hardcoded Keys (JS)');
  keys.columns = [
    { header: 'Screen Name', key: 'screen', width: 30 },
    { header: 'Type', key: 'type', width: 28 },
    { header: 'Name', key: 'name', width: 28 },
    { header: 'Value', key: 'value', width: 50 },
    { header: 'Script URL', key: 'script', width: 55 },
    { header: 'Context in code', key: 'context', width: 70 }
  ];
  styleHeader(keys);
  keyRows.forEach(r => addRow(keys, r));
  keys.autoFilter = { from: 'A1', to: 'F1' };

  const sig = workbook.addWorksheet('Client Signature & Auth');
  sig.columns = [
    { header: 'Screen Name', key: 'screen', width: 30 },
    { header: 'Event Name', key: 'event', width: 30 },
    { header: 'API URL', key: 'apiUrl', width: 50 },
    { header: 'Found In', key: 'where', width: 18 },
    { header: 'Type', key: 'type', width: 26 },
    { header: 'Name', key: 'name', width: 26 },
    { header: 'Value / Code snippet', key: 'value', width: 60 },
    { header: 'Hardcoded in JS?', key: 'hardcoded', width: 16 },
    { header: 'Script URL', key: 'script', width: 55 },
    { header: 'Seen On (calls)', key: 'seen', width: 10 }
  ];
  styleHeader(sig);
  [...sigRows, ...logicRows].forEach(r => addRow(sig, r));
  sig.autoFilter = { from: 'A1', to: 'J1' };

  const authJs = workbook.addWorksheet('Auth in Client JS');
  authJs.columns = [
    { header: 'Screen Name', key: 'screen', width: 30 },
    { header: 'Header / Field', key: 'name', width: 28 },
    { header: 'Set To (expression in code)', key: 'expression', width: 50 },
    { header: 'Source', key: 'source', width: 26 },
    { header: 'Script URL', key: 'script', width: 55 },
    { header: 'Context in code', key: 'context', width: 70 }
  ];
  styleHeader(authJs);
  authUsageRows.forEach(r => addRow(authJs, r));
  if (!authUsageRows.length) addRow(authJs, { screen: '', name: 'None found', expression: '', source: '', script: '', context: '' });
  authJs.autoFilter = { from: 'A1', to: 'F1' };

  return workbook.xlsx.writeBuffer();
}

module.exports = { buildApiDetailsXlsx };

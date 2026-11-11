const ExcelJS = require('exceljs');

function eventName(ev) {
  const label = ev.target && ev.target.selector ? ev.target.selector : '';
  switch (ev.type) {
    case 'page_load': return 'Page load';
    case 'click': return `Click${label ? ' - ' + label : ''}`;
    case 'input_start': return `Started typing${label ? ' - ' + label : ''}`;
    case 'input_end': return `Entered value${label ? ' - ' + label : ''}`;
    case 'change': return `Changed${label ? ' - ' + label : ''}`;
    case 'submit': return `Submit${label ? ' - ' + label : ''}`;
    default: return `${ev.type}${label ? ' - ' + label : ''}`;
  }
}

async function buildApiListXlsx({ events, callsByEvent }) {
  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'Browser API Tracker';
  workbook.created = new Date();

  const sheet = workbook.addWorksheet('API List');
  sheet.columns = [
    { header: 'Page Name', key: 'page', width: 35 },
    { header: 'Event Name', key: 'event', width: 35 },
    { header: 'Method', key: 'method', width: 10 },
    { header: 'API URL', key: 'url', width: 65 },
    { header: 'Status', key: 'status', width: 10 },
    { header: 'Repeats', key: 'repeats', width: 10 }
  ];

  sheet.getRow(1).font = { bold: true, color: { argb: 'FFFFFFFF' } };
  sheet.getRow(1).fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1C1E21' } };
  sheet.getRow(1).alignment = { vertical: 'middle' };

  for (const ev of events) {
    const calls = callsByEvent.get(ev.id) || [];
    for (const call of calls) {
      const row = sheet.addRow({
        page: ev.title || ev.url,
        event: eventName(ev),
        method: call.method,
        url: call.url,
        status: call.status != null ? call.status : 'FAILED',
        repeats: call.count > 1 ? call.count : 1
      });
      row.alignment = { vertical: 'top', wrapText: true };
    }
  }

  sheet.autoFilter = { from: 'A1', to: 'F1' };
  sheet.views = [{ state: 'frozen', ySplit: 1 }];

  return workbook.xlsx.writeBuffer();
}

module.exports = { buildApiListXlsx, eventName };

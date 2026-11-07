const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell,
  WidthType, ShadingType, PageOrientation
} = require('docx');
const {
  cleanText, buildScreenLookup, collectCallRows, collectSignatureRows, collectKeyRows
} = require('./apiDetailsData');

// Word gets slow with huge text blocks, so bodies are capped much lower than in Excel.
const BLOCK_LIMIT = 4000;

function cell(text, { header = false, width = 25 } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.PERCENTAGE },
    shading: header ? { type: ShadingType.CLEAR, fill: '1C1E21' } : undefined,
    children: [new Paragraph({
      children: [new TextRun({
        text: cleanText(text, 600), bold: header, color: header ? 'FFFFFF' : undefined, size: 16
      })]
    })]
  });
}

function table(headers, widths, rows) {
  return new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, { header: true, width: widths[i] })) }),
      ...rows.map(r => new TableRow({ children: r.map((v, i) => cell(v, { width: widths[i] })) }))
    ]
  });
}

function codeBlock(label, text) {
  if (!text) return [];
  const lines = cleanText(text, BLOCK_LIMIT).split('\n');
  return [
    new Paragraph({ text: label, heading: HeadingLevel.HEADING_4 }),
    new Paragraph({
      shading: { type: ShadingType.CLEAR, fill: 'F1F2F4' },
      children: lines.map((line, i) => new TextRun({ text: line, font: 'Consolas', size: 15, break: i ? 1 : 0 }))
    })
  ];
}

async function buildApiDetailsDocx({ startUrl, startedAt, finishedAt, events, callsByEvent, scanner }) {
  const callRows = collectCallRows(events, callsByEvent);
  const sigRows = collectSignatureRows(callRows, scanner);
  const { keyRows, logicRows, authUsageRows } = collectKeyRows(scanner, buildScreenLookup(events));

  const children = [
    new Paragraph({ text: 'API Details', heading: HeadingLevel.TITLE }),
    new Paragraph({ text: `Start URL: ${startUrl}` }),
    new Paragraph({ text: `${new Date(startedAt).toLocaleString()} - ${new Date(finishedAt).toLocaleString()} | ${callRows.length} API calls` }),
    new Paragraph({
      children: [new TextRun({
        text: 'Contains real request headers, tokens and keys captured from the browser. Do not share outside the team.',
        italics: true, color: 'B91C1C', size: 18
      })]
    })
  ];

  children.push(new Paragraph({ text: '1. API calls by screen and event', heading: HeadingLevel.HEADING_1 }));
  let lastGroup = null;
  for (const r of callRows) {
    const group = `${r.screen}\u0001${r.event}\u0001${r.ev.id}`;
    if (group !== lastGroup) {
      lastGroup = group;
      children.push(new Paragraph({ text: `Screen: ${cleanText(r.screen, 200)}`, heading: HeadingLevel.HEADING_2 }));
      children.push(new Paragraph({
        children: [new TextRun({ text: `Event: ${r.event}`, bold: true, size: 20 })]
      }));
    }
    children.push(table(['Method', 'Status', 'API URL', 'Repeats'], [12, 10, 66, 12],
      [[r.method, r.status, r.url, r.repeats > 1 ? `x${r.repeats}` : '1']]));
    children.push(...codeBlock('Request Headers', r.reqHeaders));
    children.push(...codeBlock('Request Payload', r.reqBody));
    children.push(...codeBlock('Response Headers', r.resHeaders));
    children.push(...codeBlock('Response Body', r.resBody));
    children.push(new Paragraph({ text: '' }));
  }
  if (!callRows.length) children.push(new Paragraph({ text: 'No API calls captured.' }));

  children.push(new Paragraph({ text: '2. Hardcoded keys found in browser JavaScript', heading: HeadingLevel.HEADING_1 }));
  children.push(table(['Screen', 'Type', 'Name', 'Value', 'Script URL'], [18, 16, 16, 24, 26],
    keyRows.map(k => [k.screen, k.type, k.name, k.value, k.script])));

  children.push(new Paragraph({ text: '3. Client signature and auth values', heading: HeadingLevel.HEADING_1 }));
  children.push(table(['Screen / Event', 'Found In', 'Name', 'Value', 'Hardcoded in JS?', 'API URL'], [18, 12, 14, 26, 12, 18],
    sigRows.map(s => [`${s.screen} / ${s.event}`, `${s.where} (${s.type})`, s.name, s.value, s.hardcoded, s.apiUrl])));

  if (logicRows.length) {
    children.push(new Paragraph({ text: 'Signature / encryption logic in page JavaScript', heading: HeadingLevel.HEADING_2 }));
    children.push(table(['Screen', 'Pattern', 'Code snippet', 'Script URL'], [18, 18, 40, 24],
      logicRows.map(l => [l.screen, l.name, l.value, l.script])));
  }

  children.push(new Paragraph({ text: '4. How client JavaScript sets auth', heading: HeadingLevel.HEADING_1 }));
  children.push(authUsageRows.length
    ? table(['Screen', 'Header / Field', 'Set to (code)', 'Source', 'Script URL'], [16, 18, 30, 16, 20],
      authUsageRows.map(a => [a.screen, a.name, a.expression, a.source, a.script]))
    : new Paragraph({ text: 'None found in the scanned scripts.' }));

  const doc = new Document({
    sections: [{
      properties: { page: { size: { orientation: PageOrientation.LANDSCAPE } } },
      children
    }]
  });
  return Packer.toBuffer(doc);
}

module.exports = { buildApiDetailsDocx };

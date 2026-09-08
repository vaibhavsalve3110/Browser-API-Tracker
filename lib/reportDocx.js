const fs = require('fs');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, ImageRun,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle
} = require('docx');
const { getPngSize } = require('./pngSize');

const MAX_IMG_WIDTH = 560;

function pretty(body) {
  if (!body) return '';
  try {
    return JSON.stringify(JSON.parse(body), null, 2);
  } catch (e) {
    return body;
  }
}

function truncate(str, max) {
  if (!str) return str;
  return str.length > max ? str.slice(0, max) + `\n...[truncated, ${str.length} chars total]` : str;
}

function cell(text, opts) {
  return new TableCell({
    width: { size: (opts && opts.size) || 25, type: WidthType.PERCENTAGE },
    shading: opts && opts.header ? { type: ShadingType.CLEAR, fill: '1C1E21' } : undefined,
    children: [new Paragraph({
      children: [new TextRun({ text: String(text == null ? '' : text), bold: !!(opts && opts.header), color: opts && opts.header ? 'FFFFFF' : undefined, size: 18 })]
    })]
  });
}

function codeParagraph(text) {
  return new Paragraph({
    shading: { type: ShadingType.CLEAR, fill: 'F1F2F4' },
    children: [new TextRun({ text: text || '', font: 'Consolas', size: 16 })]
  });
}

async function buildDocxReport({ startUrl, startedAt, finishedAt, events, callsByEvent }) {
  const children = [];

  children.push(new Paragraph({ text: 'Browser Session Report', heading: HeadingLevel.TITLE }));
  children.push(new Paragraph({ text: `Start URL: ${startUrl}` }));
  children.push(new Paragraph({ text: `${new Date(startedAt).toLocaleString()} - ${new Date(finishedAt).toLocaleString()} | ${events.length} events` }));

  for (const ev of events) {
    children.push(new Paragraph({
      text: `#${ev.id} ${ev.type} (${new Date(ev.timestamp).toLocaleTimeString()})`,
      heading: HeadingLevel.HEADING_1
    }));
    children.push(new Paragraph({ text: `Page: ${ev.url}` }));
    if (ev.target && ev.target.selector) {
      children.push(new Paragraph({ text: `Element: ${ev.target.selector}${ev.target.text ? ' — "' + ev.target.text + '"' : ''}` }));
    }
    if (ev.extra && ev.extra.value !== undefined) {
      children.push(new Paragraph({ text: `Value: ${ev.extra.value}` }));
    }

    if (ev.screenshot && fs.existsSync(ev.screenshot)) {
      const buf = fs.readFileSync(ev.screenshot);
      const size = getPngSize(buf);
      const width = Math.min(MAX_IMG_WIDTH, size.width);
      const height = Math.round((size.height / size.width) * width) || 1;
      children.push(new Paragraph({
        children: [new ImageRun({ data: buf, transformation: { width, height }, type: 'png' })]
      }));
    }

    const calls = callsByEvent.get(ev.id) || [];
    children.push(new Paragraph({ text: `API Calls Triggered (${calls.length})`, heading: HeadingLevel.HEADING_2 }));

    if (!calls.length) {
      children.push(new Paragraph({ text: 'No API calls captured for this event.' }));
    }

    for (const c of calls) {
      const rows = [
        new TableRow({ children: [cell('Method', { header: true, size: 18 }), cell('Status', { header: true, size: 12 }), cell('URL', { header: true, size: 55 }), cell('Repeats', { header: true, size: 15 })] }),
        new TableRow({ children: [cell(c.method, { size: 18 }), cell(c.status != null ? c.status : 'FAILED', { size: 12 }), cell(c.url, { size: 55 }), cell(c.count > 1 ? `x${c.count}` : '1', { size: 15 })] })
      ];
      children.push(new Table({ width: { size: 100, type: WidthType.PERCENTAGE }, rows }));

      if (c.count > 1) {
        children.push(new Paragraph({
          children: [new TextRun({ text: `Sent ${c.count} times in a row (identical method, URL, payload & status) — last at ${new Date(c.lastTimestamp).toLocaleTimeString()}.`, italics: true, size: 18 })]
        }));
      }

      if (c.postData) {
        children.push(new Paragraph({ text: 'Request Payload', heading: HeadingLevel.HEADING_3 }));
        children.push(codeParagraph(truncate(pretty(c.postData), 4000)));
      }
      if (c.responseBody) {
        children.push(new Paragraph({ text: 'Response Body', heading: HeadingLevel.HEADING_3 }));
        children.push(codeParagraph(truncate(pretty(c.responseBody), 4000)));
      }
      children.push(new Paragraph({ text: '' }));
    }
  }

  const doc = new Document({
    sections: [{ properties: {}, children }]
  });

  return Packer.toBuffer(doc);
}

module.exports = { buildDocxReport };

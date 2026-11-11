const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, HeadingLevel, ImageRun } = require('docx');
const { getPngSize } = require('./pngSize');

const MAX_IMG_WIDTH = 560;

// The technical report already lists every low-level event (including the "first
// keystroke" of a typing session). The journey doc reads as a narrative for a human,
// so intermediate "started typing" moments are skipped — only the completed action
// for each field/element shows up as a step.
const SKIP_TYPES = new Set(['input_start']);

function describeStep(ev) {
  const label = ev.target && ev.target.selector ? ev.target.selector : 'element';
  const text = ev.target && ev.target.text ? ev.target.text : '';
  const value = ev.extra && ev.extra.value !== undefined ? ev.extra.value : undefined;

  switch (ev.type) {
    case 'page_load':
      return `Opened the page: ${ev.url}`;
    case 'click':
      return `Clicked "${text || label}" (${label})`;
    case 'input_end':
      return `Entered "${value !== undefined ? value : ''}" into ${label}`;
    case 'change':
      return `Selected/changed ${label}${value !== undefined ? ` to "${value}"` : ''}`;
    case 'submit':
      return `Submitted the form (${label})`;
    default:
      return `${ev.type} on ${label}`;
  }
}

async function buildJourneyDocx({ startUrl, startedAt, finishedAt, events }) {
  const steps = events.filter(ev => !SKIP_TYPES.has(ev.type));
  const children = [];

  children.push(new Paragraph({ text: 'User Journey', heading: HeadingLevel.TITLE }));
  children.push(new Paragraph({ text: `Start URL: ${startUrl}` }));
  children.push(new Paragraph({ text: `${new Date(startedAt).toLocaleString()} - ${new Date(finishedAt).toLocaleString()} | ${steps.length} steps` }));
  children.push(new Paragraph({ text: '' }));

  steps.forEach((ev, i) => {
    children.push(new Paragraph({
      text: `Step ${i + 1}: ${describeStep(ev)}`,
      heading: HeadingLevel.HEADING_1
    }));
    children.push(new Paragraph({
      children: [new TextRun({ text: `Page: ${ev.url}  •  ${new Date(ev.timestamp).toLocaleTimeString()}`, italics: true, size: 18, color: '666666' })]
    }));

    if (ev.screenshot && fs.existsSync(ev.screenshot)) {
      const buf = fs.readFileSync(ev.screenshot);
      const size = getPngSize(buf);
      const width = Math.min(MAX_IMG_WIDTH, size.width);
      const height = Math.round((size.height / size.width) * width) || 1;
      children.push(new Paragraph({
        children: [new ImageRun({ data: buf, transformation: { width, height }, type: 'png' })]
      }));
    }
    children.push(new Paragraph({ text: '' }));
  });

  const doc = new Document({ sections: [{ properties: {}, children }] });
  return Packer.toBuffer(doc);
}

module.exports = { buildJourneyDocx };

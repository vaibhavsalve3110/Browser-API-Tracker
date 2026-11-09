"""python-docx helpers: tables, shaded code blocks, screenshots, landscape pages."""
import os
from io import BytesIO

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from .common import clean_text, png_size

MAX_IMG_WIDTH_PX = 560


def new_document(landscape=False):
    doc = Document()
    section = doc.sections[0]
    if landscape:
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width, section.page_height = section.page_height, section.page_width
    return doc


def usable_width(doc):
    s = doc.sections[0]
    return s.page_width - s.left_margin - s.right_margin


def _shade(element_pr, fill):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), fill)
    element_pr.append(shd)


def add_text(doc, text, bold=False, italic=False, size=None, color=None):
    p = doc.add_paragraph()
    run = p.add_run(clean_text(text, 5000))
    run.bold = bold
    run.italic = italic
    if size:
        run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    return p


def add_heading(doc, text, level):
    return doc.add_heading(clean_text(text, 1000), level)


def add_code_block(doc, text, size=7.5):
    """Monospace paragraph on a grey background; newlines become line breaks."""
    p = doc.add_paragraph()
    _shade(p._p.get_or_add_pPr(), 'F1F2F4')
    lines = clean_text(text, 1_000_000).split('\n')
    for i, line in enumerate(lines):
        run = p.add_run()
        if i:
            run.add_break()
        run.add_text(line)
        run.font.name = 'Consolas'
        run.font.size = Pt(size)
    return p


def add_table(doc, headers, widths_pct, rows, font_size=8, cell_limit=600):
    """Header row (white on dark, repeats on each page) plus body rows. widths are percentages."""
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = 'Table Grid'
    table.autofit = False
    total = usable_width(doc)
    widths = [int(total * w / 100) for w in widths_pct]

    def fill(cell, text, header, width):
        cell.width = width
        para = cell.paragraphs[0]
        run = para.add_run(clean_text(text, cell_limit))
        run.font.size = Pt(font_size)
        if header:
            run.bold = True
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            _shade(cell._tc.get_or_add_tcPr(), '1C1E21')

    head = table.rows[0]
    trpr = head._tr.get_or_add_trPr()
    trpr.append(OxmlElement('w:tblHeader'))
    for i, h in enumerate(headers):
        fill(head.cells[i], h, True, widths[i])
    for r in rows:
        row = table.add_row()
        for i, v in enumerate(r):
            fill(row.cells[i], v, False, widths[i])
    return table


def add_screenshot(doc, path):
    if not path or not os.path.exists(path):
        return
    with open(path, 'rb') as fh:
        data = fh.read()
    width, _height = png_size(data)
    doc.add_picture(BytesIO(data), width=Inches(min(MAX_IMG_WIDTH_PX, width) / 96))

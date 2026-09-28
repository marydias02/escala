"""Convert non-PDF attachments (images, Excel, CSV, Word) to PDF.

Each natural unit of the source becomes one PDF: an image, a visible sheet, a
CSV file, a Word document. PDFs are not handled here — they keep their own path, which
segments them into documents.

Pure Python by design: no office suite is needed on the host, so the output is
a faithful reading of the content rather than a pixel copy of the original.
"""

import csv
import html
import io
import re
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

import docx
import fitz
import openpyxl
from docx.drawing import Drawing
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.hyperlink import Hyperlink
from docx.text.paragraph import Paragraph

from email_core.config import MAX_SHEET_ROWS
from email_core.email_pdf import A4, MARGIN, render_html_pdf

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif"}
EXCEL_EXTENSIONS = {".xlsx", ".xlsm"}
CSV_EXTENSIONS = {".csv"}
WORD_EXTENSIONS = {".docx"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | EXCEL_EXTENSIONS | CSV_EXTENSIONS | WORD_EXTENSIONS

# Tried in order; cp1252 decodes any byte, so it is the last resort.
_CSV_ENCODINGS = ("utf-8-sig", "cp1252")
_CSV_DELIMITERS = ";,\t|"

A4_LANDSCAPE = fitz.paper_rect("a4-l")
SHEET_MARGIN = 30

# Image formats MuPDF can draw; Word also embeds emf/wmf, which it cannot.
_DRAWABLE_IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "bmp", "tif", "tiff"}
_EMU_PER_PT = 12700

_TABLE_CSS = """
table { border-collapse: collapse; margin-bottom: 6pt; }
td { border: 0.5pt solid #999; padding: 1pt 3pt; vertical-align: top; }
"""

_SHEET_CSS = "body { font-family: sans-serif; font-size: 7pt; } h2 { font-size: 10pt; }" + _TABLE_CSS

_DOC_CSS = (
    "body { font-family: sans-serif; font-size: 10pt; }"
    " p { margin: 0 0 4pt 0; white-space: pre-wrap; }"
    " h1 { font-size: 14pt; } h2 { font-size: 12pt; } h3 { font-size: 11pt; }"
    " .margin { font-size: 8pt; color: #555; }"
    + _TABLE_CSS
)


@dataclass
class ConvertedDocument:
    """One PDF produced from one unit of a non-PDF attachment."""

    filename: str
    pdf_bytes: bytes


def convert_to_pdfs(filename: str, data: bytes) -> list[ConvertedDocument] | None:
    """Convert an attachment to one PDF per unit; None when the format is unsupported."""
    path = Path(filename)
    ext = path.suffix.lower()
    stem = path.stem

    if ext in IMAGE_EXTENSIONS:
        return [ConvertedDocument(f"{stem}.pdf", _image_to_pdf(data, ext))]
    if ext in EXCEL_EXTENSIONS:
        return [ConvertedDocument(f"{stem}_{slug}.pdf", pdf) for slug, pdf in _xlsx_to_pdfs(data, filename)]
    if ext in CSV_EXTENSIONS:
        pdf = _csv_to_pdf(data, filename)
        return [ConvertedDocument(f"{stem}.pdf", pdf)] if pdf else []
    if ext in WORD_EXTENSIONS:
        return [ConvertedDocument(f"{stem}.pdf", _docx_to_pdf(data))]
    return None


def _html_document(css: str, body: str) -> str:
    return f"<html><head><style>{css}</style></head><body>{body}</body></html>"


def _merge_pdfs(parts: list[bytes]) -> bytes:
    """Concatenate PDFs into one."""
    merged = fitz.open()
    for part in parts:
        with fitz.open(stream=part, filetype="pdf") as doc:
            merged.insert_pdf(doc)
    return merged.tobytes()


# --------------------------------------------------------------------------- #
# Images
# --------------------------------------------------------------------------- #


def _image_to_pdf(data: bytes, ext: str) -> bytes:
    """Embed the image unchanged, one page per frame."""
    with fitz.open(stream=data, filetype=ext.lstrip(".")) as image:
        return image.convert_to_pdf()


# --------------------------------------------------------------------------- #
# Excel
# --------------------------------------------------------------------------- #


_CURRENCY_TAG = re.compile(r"\[\$([^\]\-]*)")
_CURRENCY_SYMBOLS = "€$£"


def _number_text(value: int | float, number_format: str) -> str:
    """A number with its format's decimals, percent and currency; no thousands separator."""
    section = (number_format or "General").split(";")[0]
    currency_tag = _CURRENCY_TAG.search(section)
    # Drop bracketed tags ([Red], [$€-1]) and quoted literals before reading placeholders.
    pattern = re.sub(r'\[[^\]]*\]|"[^"]*"', "", section)

    if "0" not in pattern and "#" not in pattern:
        return str(int(value)) if float(value).is_integer() else format(value, ".15g")

    decimals = re.search(r"\.([0#]+)", pattern)
    places = decimals.group(1).count("0") if decimals else 0
    if "%" in pattern:
        return f"{value * 100:.{places}f}%"

    text = f"{value:.{places}f}"
    symbol = currency_tag.group(1) if currency_tag else next((s for s in _CURRENCY_SYMBOLS if s in section), "")
    if not symbol:
        return text
    placeholder = min(i for i in (section.find("0"), section.find("#")) if i >= 0)
    return f"{symbol}{text}" if section.find(symbol) < placeholder else f"{text} {symbol}"


def _cell_text(value, number_format: str = "General") -> str:
    """A cell value as display text."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == time(0) else value.isoformat(sep=" ")
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _number_text(value, number_format)
    return str(value)


def _slug(name: str, fallback: str) -> str:
    return re.sub(r"[^\w-]+", "_", name).strip("_") or fallback


def _sheet_html(ws, filename: str) -> str | None:
    """One sheet as an HTML table; None when it holds no values."""
    cells = [(c.row, c.column) for row in ws.iter_rows() for c in row if c.value not in (None, "")]
    if not cells:
        return None

    min_row, max_row = min(r for r, _ in cells), max(r for r, _ in cells)
    min_col, max_col = min(c for _, c in cells), max(c for _, c in cells)
    if max_row - min_row + 1 > MAX_SHEET_ROWS:
        print(f"  ⚠️  {filename} / {ws.title}: {max_row - min_row + 1} rows, only the first {MAX_SHEET_ROWS} rendered")
        max_row = min_row + MAX_SHEET_ROWS - 1

    # Merged ranges: span at the top-left cell, skip the cells it covers.
    spans: dict[tuple[int, int], tuple[int, int]] = {}
    covered: set[tuple[int, int]] = set()
    for merged in ws.merged_cells.ranges:
        top, left = max(merged.min_row, min_row), max(merged.min_col, min_col)
        bottom, right = min(merged.max_row, max_row), min(merged.max_col, max_col)
        if top > bottom or left > right:
            continue
        spans[(top, left)] = (bottom - top + 1, right - left + 1)
        covered.update((r, c) for r in range(top, bottom + 1) for c in range(left, right + 1))

    rows = []
    for values in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        tds = []
        for cell in values:
            key = (cell.row, cell.column)
            if key in covered and key not in spans:
                continue
            rowspan, colspan = spans.get(key, (1, 1))
            attrs = (f' rowspan="{rowspan}"' if rowspan > 1 else "") + (f' colspan="{colspan}"' if colspan > 1 else "")
            tds.append(f"<td{attrs}>{html.escape(_cell_text(cell.value, cell.number_format))}</td>")
        rows.append(f"<tr>{''.join(tds)}</tr>")

    return f"<h2>{html.escape(ws.title)}</h2><table>{''.join(rows)}</table>"


def _xlsx_to_pdfs(data: bytes, filename: str) -> list[tuple[str, bytes]]:
    """One (sheet slug, PDF) per visible, non-empty sheet."""
    workbook = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    pdfs = []
    for index, ws in enumerate(workbook.worksheets, start=1):
        if ws.sheet_state != "visible":
            continue
        body = _sheet_html(ws, filename)
        if body is None:
            continue
        pdf = render_html_pdf(_html_document(_SHEET_CSS, body), paper=A4_LANDSCAPE, margin=SHEET_MARGIN)
        pdfs.append((_slug(ws.title, f"sheet{index}"), pdf))
    return pdfs


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #


def _decode_csv(data: bytes) -> str:
    for encoding in _CSV_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _csv_to_pdf(data: bytes, filename: str) -> bytes | None:
    """The file as one table PDF, values as written; None when it holds no values."""
    text = _decode_csv(data)
    try:
        delimiter = csv.Sniffer().sniff(text[:8192], delimiters=_CSV_DELIMITERS).delimiter
    except csv.Error:
        delimiter = ";" if text.count(";") > text.count(",") else ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return None
    if len(rows) > MAX_SHEET_ROWS:
        print(f"  ⚠️  {filename}: {len(rows)} rows, only the first {MAX_SHEET_ROWS} rendered")
        rows = rows[:MAX_SHEET_ROWS]

    width = max(len(row) for row in rows)
    trs = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row + [""] * (width - len(row))) + "</tr>"
        for row in rows
    )
    body = f"<h2>{html.escape(Path(filename).name)}</h2><table>{trs}</table>"
    return render_html_pdf(_html_document(_SHEET_CSS, body), paper=A4_LANDSCAPE, margin=SHEET_MARGIN)


# --------------------------------------------------------------------------- #
# Word
# --------------------------------------------------------------------------- #

_PAGE_BREAK = None  # marker between HTML pieces: start a new page here
_BLANK_LINE = "<p>&#160;</p>"


class _ImageStore:
    """Images referenced from the HTML, served to the Story through an archive."""

    def __init__(self):
        self.archive = fitz.Archive()
        self.count = 0

    def add(self, drawing: Drawing) -> str:
        """An <img> tag for a picture drawing, or "" when it cannot be drawn."""
        if not drawing.has_picture:
            return ""
        image = drawing.image
        if image.ext.lower() not in _DRAWABLE_IMAGE_EXTS:
            return ""

        self.count += 1
        name = f"img{self.count}.{image.ext}"
        self.archive.add((image.blob, name))

        width = _drawing_width_pt(drawing)
        frame_width = A4.width - 2 * MARGIN
        size = f' width="{min(width, frame_width):.0f}"' if width else f' width="{frame_width:.0f}"'
        return f'<img src="{name}"{size}/>'


def _drawing_width_pt(drawing: Drawing) -> float | None:
    """The drawing's displayed width in points, from its extent."""
    extents = drawing._drawing.xpath("./wp:inline/wp:extent | ./wp:anchor/wp:extent")
    if not extents:
        return None
    return int(extents[0].get("cx")) / _EMU_PER_PT


def _run_pieces(run, images: _ImageStore) -> list[str | None]:
    """A run's HTML in document order, with page-break markers."""
    pieces: list[str | None] = []
    wrap = [("<b>", "</b>")] * bool(run.bold) + [("<i>", "</i>")] * bool(run.italic)

    def text(value: str) -> None:
        opened = "".join(o for o, _ in wrap)
        closed = "".join(c for _, c in reversed(wrap))
        pieces.append(f"{opened}{html.escape(value)}{closed}")

    for child in run._r.iterchildren():
        tag = child.tag
        if tag == qn("w:t"):
            text(child.text or "")
        elif tag == qn("w:tab"):
            text("\t")
        elif tag in (qn("w:br"), qn("w:cr")):
            if child.get(qn("w:type")) == "page":
                pieces.append(_PAGE_BREAK)
            else:
                text("\n")
        elif tag == qn("w:lastRenderedPageBreak"):
            pieces.append(_PAGE_BREAK)
        elif tag == qn("w:drawing"):
            pieces.append(images.add(Drawing(child, run)))
    return pieces


def _paragraph_tag(paragraph: Paragraph) -> str:
    name = paragraph.style.name if paragraph.style is not None else ""
    if name == "Title":
        return "h1"
    match = re.fullmatch(r"Heading ([1-3])", name)
    return f"h{match.group(1)}" if match else "p"


def _paragraph_blocks(paragraph: Paragraph, images: _ImageStore) -> list[str | None]:
    """A paragraph as HTML blocks, split wherever a page break falls inside it."""
    tag = _paragraph_tag(paragraph)
    pieces: list[str | None] = []
    if paragraph.paragraph_format.page_break_before:
        pieces.append(_PAGE_BREAK)

    for item in paragraph.iter_inner_content():
        for run in item.runs if isinstance(item, Hyperlink) else [item]:
            pieces.extend(_run_pieces(run, images))

    ppr = paragraph._p.pPr
    if ppr is not None and ppr.sectPr is not None and ppr.sectPr.start_type != WD_SECTION.CONTINUOUS:
        pieces.append(_PAGE_BREAK)

    # Blank paragraphs are Word's vertical spacing, so keep them as blank lines.
    if _PAGE_BREAK not in pieces and not "".join(pieces).strip():
        return [_BLANK_LINE]

    blocks: list[str | None] = []
    current: list[str] = []

    def flush() -> None:
        content = "".join(current)
        if content.strip():
            blocks.append(f"<{tag}>{content}</{tag}>")
        current.clear()

    for piece in pieces:
        if piece is _PAGE_BREAK:
            flush()
            blocks.append(_PAGE_BREAK)
        else:
            current.append(piece)
    flush()
    return blocks


def _table_html(table: Table) -> str:
    """A Word table, with merged cells rendered once and spanned."""
    # Merged cells repeat the same `w:tc` element in every grid slot they cover.
    grid = [[cell._tc for cell in row.cells] for row in table.rows]
    cells = {cell._tc: cell for row in table.rows for cell in row.cells}
    emitted: set = set()
    rows = []
    for r, row in enumerate(grid):
        tds = []
        for tc in row:
            if tc in emitted:
                continue
            emitted.add(tc)
            colspan = row.count(tc)
            rowspan = sum(1 for other_row in grid[r:] if tc in other_row)
            cell = cells[tc]
            attrs = (f' rowspan="{rowspan}"' if rowspan > 1 else "") + (f' colspan="{colspan}"' if colspan > 1 else "")
            text = "<br/>".join(html.escape(p.text) for p in cell.paragraphs)
            tds.append(f"<td{attrs}>{text}</td>")
        rows.append(f"<tr>{''.join(tds)}</tr>")
    return f"<table>{''.join(rows)}</table>"


def _blocks(container, images: _ImageStore) -> list[str | None]:
    """A body, header or footer as HTML blocks with page-break markers."""
    blocks: list[str | None] = []
    for item in container.iter_inner_content():
        if isinstance(item, Table):
            blocks.append(_table_html(item))
        else:
            blocks.extend(_paragraph_blocks(item, images))
    return blocks


def _margin_html(container, images: _ImageStore) -> str:
    """Header or footer content, page breaks dropped."""
    body = "".join(b for b in _blocks(container, images) if b not in (_PAGE_BREAK, _BLANK_LINE))
    return f'<div class="margin">{body}</div>' if body else ""


def _docx_to_pdf(data: bytes) -> bytes:
    """The document as one PDF, starting a new page at each break Word recorded."""
    document = docx.Document(io.BytesIO(data))
    images = _ImageStore()

    def has_content(segment: list[str]) -> bool:
        return any(block != _BLANK_LINE for block in segment)

    # Page segments: split at breaks, blank segments dropped so doubled markers collapse.
    segments: list[list[str]] = [[]]
    for block in _blocks(document, images):
        if block is _PAGE_BREAK:
            if has_content(segments[-1]):
                segments.append([])
        else:
            segments[-1].append(block)
    segments = [s for s in segments if has_content(s)] or [[""]]

    section = document.sections[0]
    if header := _margin_html(section.header, images):
        segments[0].insert(0, f"{header}<hr/>")
    if footer := _margin_html(section.footer, images):
        segments[-1].append(f"<hr/>{footer}")

    parts = [
        render_html_pdf(_html_document(_DOC_CSS, "".join(segment)), archive=images.archive)
        for segment in segments
    ]
    return _merge_pdfs(parts)

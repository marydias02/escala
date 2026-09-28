"""Render an email body to a PDF, via PyMuPDF's Story layout engine.

The output carries a provenance header — sender, subject, received-at and the
Graph message id — above the body text, so the rendered file identifies the
message it came from without reference to any database row.
"""

import html
import io

import fitz

A4 = fitz.paper_rect("a4")
MARGIN = 50

_CSS = """
body { font-family: sans-serif; font-size: 10pt; color: #111; }
h1 { font-size: 13pt; margin-bottom: 4pt; }
.meta { font-size: 8pt; color: #555; margin-bottom: 2pt; }
hr { margin: 10pt 0; }
pre { font-family: sans-serif; font-size: 10pt; white-space: pre-wrap; }
"""


def _header_html(sender: str, subject: str, received: str, message_id: str) -> str:
    rows = [
        ("From", sender),
        ("Received", received),
        ("Message id", message_id),
    ]
    lines = "".join(
        f'<div class="meta"><b>{label}:</b> {html.escape(value or "—")}</div>' for label, value in rows
    )
    return f"<h1>{html.escape(subject or '(no subject)')}</h1>{lines}<hr/>"


def render_html_pdf(
    document: str,
    paper: fitz.Rect = A4,
    margin: int = MARGIN,
    archive: fitz.Archive | None = None,
) -> bytes:
    """An HTML document as PDF bytes, paginated to `paper`.

    `archive` resolves resources the HTML references, such as `<img src>`.
    """
    story = fitz.Story(html=document, archive=archive)
    buffer = io.BytesIO()
    writer = fitz.DocumentWriter(buffer)
    frame = paper + (margin, margin, -margin, -margin)

    more = 1
    while more:
        device = writer.begin_page(paper)
        more, _ = story.place(frame)
        story.draw(device)
        writer.end_page()
    writer.close()

    return buffer.getvalue()


def render_email_pdf(
    *,
    sender: str,
    subject: str,
    body: str,
    received: str,
    message_id: str,
) -> bytes:
    """One email as PDF bytes, paginated to A4."""
    document = (
        "<html><head><style>" + _CSS + "</style></head><body>"
        + _header_html(sender, subject, received, message_id)
        + f"<pre>{html.escape(body or '')}</pre>"
        + "</body></html>"
    )
    return render_html_pdf(document)

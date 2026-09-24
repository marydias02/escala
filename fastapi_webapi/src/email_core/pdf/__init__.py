"""Deterministic PDF primitives: splitting, text/layout parsing, OCR, scan detection.

No LLM calls and no use-case knowledge. `page_mode.document_content_parts` is
the one that decides how a document reaches the model — rendered page images for
a scan, the PDF itself otherwise — and is what lets both use cases hand a
document over multimodally.
"""

from email_core.pdf.ocr import ocr_page
from email_core.pdf.page_mode import (
    document_content_parts,
    image_coverage,
    is_scanned_pdf,
    render_page_data_urls,
)
from email_core.pdf.parser import build_attachment_evidence
from email_core.pdf.splitter import (
    DocumentBoundary,
    SplitDocument,
    count_pages,
    ensure_readable,
    repair_pdf,
    split_pdf,
    validate_segmentation,
)

__all__ = [
    "DocumentBoundary",
    "SplitDocument",
    "build_attachment_evidence",
    "count_pages",
    "document_content_parts",
    "ensure_readable",
    "image_coverage",
    "is_scanned_pdf",
    "ocr_page",
    "render_page_data_urls",
    "repair_pdf",
    "split_pdf",
    "validate_segmentation",
]

"""Deterministic PDF page counting, boundary checking and splitting.

Nothing here calls an LLM. The model proposes boundaries; this module decides
whether they are usable and cuts the pages. Keeping the two apart is what makes
segmentation verifiable.
"""

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

import fitz
from pypdf import PdfReader, PdfWriter


class DocumentBoundary(Protocol):
    """Where one document starts and ends inside a multi-document PDF.

    A Protocol rather than an import: the concrete boundary model belongs to
    whichever use case ran segmentation (`invoice_extraction.models`), and the
    cutting mechanics here need only these two page numbers. This keeps
    `email_core` free of any use-case import.
    """

    start_page: int
    end_page: int


@dataclass
class SplitDocument:
    """One single-document PDF cut out of a larger source PDF."""

    filename: str
    encoded_pdf: str
    boundary: Optional[DocumentBoundary]

    @property
    def pdf_bytes(self) -> bytes:
        return base64.b64decode(self.encoded_pdf)


def repair_pdf(pdf_bytes: bytes) -> bytes:
    """Rebuild a PDF's cross-reference table by round-tripping it through PyMuPDF.

    Some senders produce PDFs whose `startxref` offset points at the wrong byte, so
    pypdf cannot find the document root and falls back to scanning for a `/Catalog`
    key — a recovery that succeeds or fails depending on object ordering. PyMuPDF
    parses these files without complaint, and writing them back out produces bytes
    with a valid xref that pypdf then reads normally.

    Raises if the bytes are not recoverable, so callers can report a real failure
    rather than silently emitting an empty document.
    """
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return doc.tobytes()


def ensure_readable(pdf_bytes: bytes) -> bytes:
    """Return bytes pypdf can read, repairing them first if it cannot.

    Repair is attempted only on failure: a PDF that already parses is passed through
    untouched, so well-formed files are never rewritten.
    """
    try:
        count_pages(pdf_bytes)
    except Exception:  # noqa: BLE001 - pypdf raises several unrelated types here
        return repair_pdf(pdf_bytes)

    return pdf_bytes


def count_pages(pdf_bytes: bytes) -> int:
    """The authoritative page count. Never ask the model for this."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    # `len(reader.pages)` is what actually forces the page tree to be resolved;
    # constructing the reader alone succeeds even on a broken xref.
    return len(reader.pages)


def validate_segmentation(documents: list[DocumentBoundary], total_pages: int) -> list[str]:
    """Check the VLM boundaries against the deterministic page count.

    Returns a list of human-readable problems (empty == clean coverage).
    """
    problems: list[str] = []
    if not documents:
        return [f"No documents returned for a {total_pages}-page PDF."]

    ordered = sorted(documents, key=lambda d: d.start_page)
    covered: set[int] = set()
    expected_next = 1
    for d in ordered:
        if not (1 <= d.start_page <= total_pages) or not (1 <= d.end_page <= total_pages):
            problems.append(f"Out-of-range boundary {d.start_page}-{d.end_page} (valid 1-{total_pages}).")
        if d.end_page < d.start_page:
            problems.append(f"Inverted boundary {d.start_page}-{d.end_page}.")
        if d.start_page != expected_next:
            problems.append(
                f"Gap/overlap: expected next document to start at page {expected_next}, got {d.start_page}."
            )
        for p in range(max(d.start_page, 1), min(d.end_page, total_pages) + 1):
            if p in covered:
                problems.append(f"Page {p} covered by more than one document.")
            covered.add(p)
        expected_next = d.end_page + 1

    missing = set(range(1, total_pages + 1)) - covered
    if missing:
        problems.append(f"Pages not covered by any document: {sorted(missing)}.")
    return problems


def split_pdf(pdf_bytes: bytes, base_filename: str, boundaries: list[DocumentBoundary]) -> list[SplitDocument]:
    """Cut a source PDF into one child PDF per detected document boundary.

    Output names are always `<stem>_NNN.pdf`, including when the source turned out
    to hold a single document — one naming rule regardless of segmentation outcome.
    A single boundary short-circuits and reuses the original bytes rather than
    round-tripping every page through PdfWriter.
    """
    stem = Path(base_filename).stem
    suffix = Path(base_filename).suffix or ".pdf"

    # Single document -> no split, reuse the original bytes as-is.
    if len(boundaries) <= 1:
        boundary = boundaries[0] if boundaries else None
        return [
            SplitDocument(
                filename=f"{stem}_001{suffix}",
                encoded_pdf=base64.b64encode(pdf_bytes).decode("utf-8"),
                boundary=boundary,
            )
        ]

    reader = PdfReader(io.BytesIO(pdf_bytes))
    page_count = len(reader.pages)

    split_documents: list[SplitDocument] = []
    for i, boundary in enumerate(boundaries, start=1):
        writer = PdfWriter()
        # start_page/end_page are 1-based inclusive; PdfReader.pages is 0-based.
        # Clamp to the real page count as a safety net against bad boundaries.
        start_idx = max(boundary.start_page - 1, 0)
        end_idx = min(boundary.end_page, page_count)
        for page_idx in range(start_idx, end_idx):
            writer.add_page(reader.pages[page_idx])

        buffer = io.BytesIO()
        writer.write(buffer)
        child_bytes = buffer.getvalue()

        split_documents.append(
            SplitDocument(
                filename=f"{stem}_{i:03d}{suffix}",
                encoded_pdf=base64.b64encode(child_bytes).decode("utf-8"),
                boundary=boundary,
            )
        )

    return split_documents

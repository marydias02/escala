"""Decide whether a PDF is a scan, and render its pages for the vision path.

A scanned page is one large image XObject covering the sheet, so any text layer
it carries was produced by the scanner's own OCR rather than authored. That text
can be well-formed and still wrong, which is why coverage — not character
statistics — is the signal used here.
"""

from __future__ import annotations

import base64
from pathlib import Path

import fitz  # PyMuPDF
from loguru import logger

from invoice_extraction.config import (
    COVERAGE_SCAN_PAGES,
    RENDER_DPI,
    RENDER_MAX_PAGES,
    SCANNED_COVERAGE_THRESHOLD,
)


def image_coverage(page: fitz.Page) -> float:
    """Fraction of the page area covered by image XObjects.

    Overlaps are counted rather than unioned, and the result is left unclamped:
    scanners emit overlapping strips, so a ratio above 1.0 is itself a scan
    fingerprint.
    """
    page_area = abs(page.rect.width * page.rect.height)
    if not page_area:
        return 0.0

    covered = sum(
        abs(rect.width * rect.height)
        for info in page.get_images(full=True)
        for rect in page.get_image_rects(info[0])
    )
    return covered / page_area


def is_scanned_pdf(
    pdf_path: Path,
    *,
    threshold: float = SCANNED_COVERAGE_THRESHOLD,
    max_pages: int = COVERAGE_SCAN_PAGES,
) -> tuple[bool, float]:
    """Whether image XObjects blanket the document, plus the coverage that decided it.

    The ratio is returned so it can be traced: a document near the threshold is
    what tells you the threshold needs tuning.
    """
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:  # noqa: BLE001 - an unreadable PDF is not a scan
        logger.warning(f"Could not open {pdf_path} for scan detection: {type(exc).__name__}: {exc}")
        return False, 0.0

    try:
        coverage = max(
            (image_coverage(doc.load_page(i)) for i in range(min(len(doc), max_pages))),
            default=0.0,
        )
    except Exception as exc:  # noqa: BLE001 - fall back to the text path
        logger.warning(f"Scan detection failed on {pdf_path}: {type(exc).__name__}: {exc}")
        return False, 0.0
    finally:
        try:
            doc.close()
        except Exception:  # noqa: BLE001
            pass

    return coverage >= threshold, coverage


def document_content_parts(doc, *, scanned: bool) -> list[dict]:
    """The message parts carrying the document itself: page images, or the PDF.

    Scanned documents go as images because the API extracts a PDF's text layer
    instead of reading its pixels — on a scan that layer is the scanner's OCR,
    and whatever it misread is simply absent from what the model sees.

    Falls back to the PDF part when rendering produces nothing, so a rendering
    failure degrades to today's behaviour rather than sending no document.
    """
    if scanned:
        urls = render_page_data_urls(doc.path)
        if urls:
            return [{"type": "image_url", "image_url": {"url": url}} for url in urls]
        logger.warning(f"{doc.filename}: detected as scanned but rendered no pages; sending PDF")

    return [
        {
            "type": "file",
            "file": {
                "file_data": doc.as_data_url(),
                "filename": doc.filename,
                "format": "application/pdf",
            },
        }
    ]


def render_page_data_urls(
    pdf_path: Path,
    *,
    dpi: int = RENDER_DPI,
    max_pages: int = RENDER_MAX_PAGES,
) -> list[str]:
    """Rasterize pages to PNG data-URLs — one image per page, nothing touches disk."""
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Could not open {pdf_path} for rendering: {type(exc).__name__}: {exc}")
        return []

    urls: list[str] = []
    try:
        for i in range(min(len(doc), max_pages)):
            png = doc.load_page(i).get_pixmap(dpi=dpi, alpha=False).tobytes("png")
            urls.append(f"data:image/png;base64,{base64.b64encode(png).decode('utf-8')}")
    except Exception as exc:  # noqa: BLE001 - keep whatever rendered
        logger.warning(f"Rendering failed on {pdf_path}: {type(exc).__name__}: {exc}")
    finally:
        try:
            doc.close()
        except Exception:  # noqa: BLE001
            pass

    return urls

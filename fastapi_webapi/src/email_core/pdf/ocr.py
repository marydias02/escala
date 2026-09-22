"""OCR fallback for PDF pages with no text layer."""

from __future__ import annotations

import fitz
from loguru import logger

OCR_DPI = 300
OCR_MIN_SCORE = 0.5
OCR_LINE_TOL_RATIO = 0.6

_engine = None
_engine_failed = False


def _get_engine():
    """Return a shared RapidOCR engine, or None when OCR is unavailable."""
    global _engine, _engine_failed

    if _engine is not None or _engine_failed:
        return _engine

    try:
        from rapidocr import RapidOCR
        _engine = RapidOCR()
    except Exception as exc:
        _engine_failed = True
        logger.warning(f"RapidOCR unavailable; scanned pages yield no text: {exc}")

    return _engine


def _lines_from_detections(detections: list[tuple[float, float, float, str]]) -> str:
    """Bucket detections by vertical centre, then sort each line left to right."""
    lines: list[list[tuple[float, float, float, str]]] = []
    current_y = None

    for det in sorted(detections, key=lambda d: d[0]):
        y_center, _x, height, _text = det
        if current_y is not None and abs(y_center - current_y) <= max(1.0, height * OCR_LINE_TOL_RATIO):
            lines[-1].append(det)
        else:
            lines.append([det])
            current_y = y_center

    out = [" ".join(d[3] for d in sorted(ln, key=lambda d: d[1])).strip() for ln in lines]
    return "\n".join(ln for ln in out if ln).strip()


def ocr_page(page: fitz.Page, *, dpi: int = OCR_DPI) -> str:
    """OCR one rendered page in memory, returning "" when nothing is recovered."""
    engine = _get_engine()
    if engine is None:
        return ""

    try:
        # Rendered straight to PNG bytes; nothing touches disk.
        result = engine(page.get_pixmap(dpi=dpi, alpha=False).tobytes("png"))
    except Exception as exc:
        logger.warning(f"OCR failed on page {page.number + 1}: {exc}")
        return ""

    # RapidOCR returns None when detection finds no text.
    if result is None or result.txts is None:
        return ""

    detections = []
    for box, text, score in zip(result.boxes, result.txts, result.scores):
        text = (text or "").strip()
        if not text or score < OCR_MIN_SCORE:
            continue

        ys = [pt[1] for pt in box]
        xs = [pt[0] for pt in box]
        detections.append(((min(ys) + max(ys)) / 2.0, min(xs), max(1.0, max(ys) - min(ys)), text))

    return _lines_from_detections(detections)

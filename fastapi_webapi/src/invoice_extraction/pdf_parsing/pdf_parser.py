from __future__ import annotations
import re
import tempfile
from pathlib import Path
import fitz  # PyMuPDF
import re
from typing import List, Tuple
import statistics
from pypdf import PdfReader
import base64

PDF_LAYOUT_WIDTH_CHARS = 200     # increase if columns collide 
PDF_LAYOUT_LINE_Y_TOL = 4     # points; increase if a single line splits 
PDF_LAYOUT_GAP_MULT = 1.6        # bigger => fewer blank lines inserted

PDF_LAYOUT_USE_TABS = True         
PDF_LAYOUT_TAB_SIZE_CHARS = 8


_NUM_HEAD_RE = re.compile(r"^\d{1,3}$")
_NUM_TAIL_RE = re.compile(r"^\d{3}[.,]\d+$")

def _merge_split_numbers_in_line(line, *, gap_factor: float = 2.0):
    """
    Joins patterns like: '2' + '910,600' => '2910,600'
    and '3' + '060,600' => '3060,600', when they are bery close on X.
    """
    if not line:
        return line

    merged = []
    i = 0
    while i < len(line):
        w1 = line[i]
        t1 = (w1[4] or "").strip()

        if i + 1 < len(line):
            w2 = line[i + 1]
            t2 = (w2[4] or "").strip()

            if _NUM_HEAD_RE.match(t1) and _NUM_TAIL_RE.match(t2):
                # Horizontal Gap between two words
                gap = float(w2[0]) - float(w1[2])
                h = max(1.0, float(w1[3]) - float(w1[1]))
                if 0 <= gap <= gap_factor * h:
                    new_text = t1 + t2  # removes the thousand separator (2 300,00 -> 2300,00)
                    new_item = (
                        float(w1[0]),
                        min(float(w1[1]), float(w2[1])),
                        float(w2[2]),
                        max(float(w1[3]), float(w2[3])),
                        new_text,
                        w1[5], w1[6], w1[7],
                    )
                    merged.append(new_item)
                    i += 2
                    continue

        merged.append(w1)
        i += 1

    return merged


def _group_words_into_lines(words, y_tol: float):
    """
    words items from page.get_text("words"):
      (x0, y0, x1, y1, text, block_no, line_no, word_no)
    Groups words into visual lines by y-center.
    """
    # sort top-to-bottom then left-to-right
    words = sorted(words, key=lambda w: ((w[1] + w[3]) / 2.0, w[0]))

    lines = []
    cur = []
    cur_y = None

    for w in words:
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        if not (text or "").strip():
            continue

        y_center = (y0 + y1) / 2.0
        if cur_y is None:
            cur = [w]
            cur_y = y_center
            continue

        if abs(y_center - cur_y) <= y_tol:
            cur.append(w)
        else:
            lines.append(sorted(cur, key=lambda ww: ww[0]))
            cur = [w]
            cur_y = y_center

    if cur:
        lines.append(sorted(cur, key=lambda ww: ww[0]))

    return lines



def _render_lines_to_fixed_width(
    lines,
    *,
    width_chars: int,
    gap_mult: float,
    use_tabs: bool = False,
    tab_size_chars: int = 8,
):
    """
    Layout-preserving text output.

    - use_tabs=False: Pads with spaces.
    - use_tabs=True: emits '\t' between tab-stops (coarse columns).
    """
    heights = []
    for line in lines:
        y0 = min(w[1] for w in line)
        y1 = max(w[3] for w in line)
        heights.append(max(1.0, y1 - y0))
    line_h = statistics.median(heights) if heights else 10.0

    all_x0 = [w[0] for ln in lines for w in ln]
    all_x1 = [w[2] for ln in lines for w in ln]
    min_x = min(all_x0) if all_x0 else 0.0
    max_x = max(all_x1) if all_x1 else 1.0
    content_w = max(1.0, max_x - min_x)

    out_lines = []
    prev_bottom = None

    # number of tab "cells" across the line when use_tabs=True
    tab_size_chars = max(1, int(tab_size_chars))
    n_tabs = max(2, (int(width_chars) + tab_size_chars - 1) // tab_size_chars)

    for ln in lines:
        top = min(w[1] for w in ln)
        bottom = max(w[3] for w in ln)
        ln = _merge_split_numbers_in_line(ln, gap_factor=2.0)
        if prev_bottom is not None:
            gap = top - prev_bottom
            if gap > gap_mult * line_h:
                blanks = max(1, int(round(gap / line_h)) - 1)
                out_lines.extend([""] * blanks)

        if not use_tabs:
            # -------- spaces to fixed columns --------
            s = ""
            for w in ln:
                x0, text = w[0], w[4]
                col = int(((x0 - min_x) / content_w) * (width_chars - 1))
                col = max(0, min(width_chars - 1, col))

                if len(s) < col:
                    s += " " * (col - len(s))
                else:
                    if s and not s.endswith(" "):
                        s += " "
                s += text
            out_lines.append(s.rstrip())
        else:
            # -------- tabs by tab-stops --------
            cells = [""] * n_tabs
            for w in ln:
                x0, text = w[0], w[4]

                # map x position -> tab cell index
                tcol = int(((x0 - min_x) / content_w) * (n_tabs - 1))
                tcol = max(0, min(n_tabs - 1, tcol))

                if cells[tcol]:
                    cells[tcol] += " " + text
                else:
                    cells[tcol] = text

            # trim trailing empty cells only (keep leading empties if any)
            last = -1
            for i in range(n_tabs - 1, -1, -1):
                if cells[i]:
                    last = i
                    break
            out_lines.append("\t".join(cells[: last + 1]) if last >= 0 else "")

        prev_bottom = bottom

    return "\n".join(out_lines).rstrip()


def _items_from_dict_with_min_font(page, *, min_font_size: float):
    """
    Returns list of items shaped like 'words' tuples:
      (x0, y0, x1, y1, text, block_no, line_no, item_no)
    but built from spans filtered by font size.
    """
    d = page.get_text("dict")
    items = []
    item_no = 0

    for b_idx, block in enumerate(d.get("blocks", [])):
        if block.get("type") != 0:  # 0=text
            continue

        for l_idx, line in enumerate(block.get("lines", [])):
            for span in line.get("spans", []):
                size = float(span.get("size") or 0.0)
                if size < min_font_size:
                    continue

                text = (span.get("text") or "").strip()
                if not text:
                    continue

                x0, y0, x1, y1 = span["bbox"]
                items.append((x0, y0, x1, y1, text, b_idx, l_idx, item_no))
                item_no += 1

    return items


def pdf_text_layout_preserving(pdf_path: Path, max_pages: int, *, min_font_size: float | None = None) -> str:
    try:
        doc = fitz.open(str(pdf_path))
    except Exception:
        return ""

    parts = []
    try:
        n = min(len(doc), max_pages)
        for i in range(n):
            page = doc.load_page(i)

            if min_font_size is None:
                items = page.get_text("words") or []
            else:
                items = _items_from_dict_with_min_font(page, min_font_size=min_font_size)

            if not items:
                continue

            lines = _group_words_into_lines(items, y_tol=PDF_LAYOUT_LINE_Y_TOL)
            if not lines:
                continue

            text = _render_lines_to_fixed_width(
                lines,
                width_chars=PDF_LAYOUT_WIDTH_CHARS,
                gap_mult=PDF_LAYOUT_GAP_MULT,
                use_tabs=PDF_LAYOUT_USE_TABS,               
                tab_size_chars=PDF_LAYOUT_TAB_SIZE_CHARS,   
            )

            if text.strip():
                tag = f"layout>=font{min_font_size:g}" if min_font_size is not None else "layout"
                parts.append(f"\n--- PAGE {i+1} ({tag}) ---\n{text}")
    finally:
        try:
            doc.close()
        except Exception:
            pass

    return "\n".join(parts).strip()



_word_re = re.compile(r"\w+|[^\w\s]", flags=re.UNICODE)

def _normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def _lower_strip(s: str) -> str:
    return _normalize_whitespace(s).lower()

def _words(s: str) -> List[str]:
    return [m.group(0) for m in _word_re.finditer(s)]

def _remove_common_word_prefix(base: str, text: str) -> Tuple[str, str]:
    """
    Removes the longest common word-prefix between base and text.
    Returns (removed_prefix, remainder_text). `removed_prefix` preserves original text slice.
    """
    removed = ""
    if not base or not text:
        return removed, text

    base_tokens = _words(_lower_strip(base))
    text_tokens = _words(_lower_strip(text))
    if not base_tokens or not text_tokens:
        return removed, text

    i = 0
    max_i = min(len(base_tokens), len(text_tokens))
    while i < max_i and base_tokens[i] == text_tokens[i]:
        i += 1
    if i == 0:
        return removed, text

    orig_tokens = list(_word_re.finditer(text))
    if len(orig_tokens) < i:
        return removed, text
    cut_pos = orig_tokens[i - 1].end()
    removed = text[:cut_pos].rstrip()
    remainder = text[cut_pos:].lstrip()
    return removed, remainder


def _remove_common_word_suffix(base: str, text: str) -> Tuple[str, str]:
    """
    Removes the longest common word-suffix between base and text.
    Returns (removed_suffix, remainder_text). `removed_suffix` preserves original text slice.
    """
    removed = ""
    if not base or not text:
        return removed, text

    base_tokens = _words(_lower_strip(base))
    text_tokens = _words(_lower_strip(text))
    if not base_tokens or not text_tokens:
        return removed, text

    i = 0
    max_i = min(len(base_tokens), len(text_tokens))
    # compare from the end
    while i < max_i and base_tokens[-1 - i] == text_tokens[-1 - i]:
        i += 1
    if i == 0:
        return removed, text

    orig_tokens = list(_word_re.finditer(text))
    if len(orig_tokens) < i:
        return removed, text
    start_pos = orig_tokens[-i].start()
    removed = text[start_pos:].rstrip()
    remainder = text[:start_pos].rstrip()
    return removed, remainder


def _remove_case_insensitive_substring(base: str, text: str, min_chars: int = 20) -> Tuple[str, str]:
    """
    If a reasonably long normalized substring of `base` appears in `text`, remove the first occurrence.
    Returns (removed_substring, remainder_text). `removed_substring` preserves original text slice.
    """
    if not base or not text:
        return "", text

    base_norm = _lower_strip(base)
    if len(base_norm) < min_chars:
        return "", text

    text_norm = _lower_strip(text)
    if base_norm in text_norm:
        m = re.search(re.escape(base_norm), text, flags=re.IGNORECASE)
        if m:
            removed = text[m.start():m.end()].strip()
            remainder = (text[:m.start()] + text[m.end():]).strip()
            return removed, remainder

    # fallback: sliding word-window, shrinking until min_chars
    base_words = _words(base_norm)
    for window in range(len(base_words), 0, -1):
        candidate = " ".join(base_words[:window])
        if len(candidate) < min_chars:
            continue
        if candidate in text_norm:
            pattern = re.compile(re.escape(candidate), flags=re.IGNORECASE)
            m = pattern.search(text)
            if m:
                removed = text[m.start():m.end()].strip()
                remainder = (text[:m.start()] + text[m.end():]).strip()
                return removed, remainder
    return "", text

def _collapse_consecutive_duplicate_lines(text: str) -> str:
    """
    Remove immediate consecutive duplicate lines (keeps first occurrence).
    Also strip trailing/leading blank lines and collapse multi-blank to single blank.
    """
    if not text:
        return ""
    lines = text.splitlines()
    out_lines = []
    prev = None
    for ln in lines:
        if prev is None or ln != prev:
            out_lines.append(ln)
        prev = ln
    cleaned = "\n".join(out_lines)
    cleaned = re.sub(r"\n\s*\n+", "\n\n", cleaned).strip()
    return cleaned

def _trim_repeated_block_at_top(text: str, max_scan_chars: int = 2000) -> str:
    """
    Heuristic: if the opening block of a page repeats immediately later in the same page,
    remove the second contiguous repetition. Useful when extraction yields the header twice.
    Only considers matches within max_scan_chars of the start for performance/safety.
    """
    if not text:
        return ""
    head = text[:max_scan_chars]
    head_norm = _lower_strip(head)
    min_fragment_chars = 40
    for size in range(len(head_norm), min_fragment_chars - 1, -1):
        frag = head_norm[:size]
        if len(frag) < min_fragment_chars:
            continue
        m = re.search(re.escape(frag), text, flags=re.IGNORECASE)
        if not m:
            continue
        first_end = m.end()
        m2 = re.search(re.escape(frag), text[first_end:], flags=re.IGNORECASE)
        if m2:
            start2 = first_end + m2.start()
            end2 = first_end + m2.end()
            gap = text[first_end:start2]
            if len(gap) <= 200:  # heuristic: small gap => repeated block
                return (text[:start2] + text[end2:]).strip()
    return text


def dedupe_pages_extract_tops_bottoms(
    page_texts: List[str],
    min_common_substring_chars: int = 40
) -> Tuple[List[str], str, str]:
    """
    Compare pages against page_texts[0] (base). Remove matching top (prefix),
    bottom (suffix) and long substring matches from subsequent pages.

    Returns (core_pages, first_top_removed, first_bottom_removed)
    - core_pages: list of cleaned page bodies (same length as page_texts)
    - first_top_removed: the first non-empty top (prefix) removed from any page
    - first_bottom_removed: the first non-empty bottom (suffix) removed from any page
    """
    if not page_texts:
        return [], "", ""

    # Step 1: pre-clean every page
    precleaned = [_collapse_consecutive_duplicate_lines((p or "").strip()) for p in page_texts]

    # Step 2: trim repeated header block inside page 0
    precleaned[0] = _trim_repeated_block_at_top(precleaned[0], max_scan_chars=3000)

    base = precleaned[0] or ""
    cores: List[str] = [base]  # page 0 kept as-is (already cleaned)
    first_top_removed: str = ""
    first_bottom_removed: str = ""

    for i in range(1, len(precleaned)):
        t_orig = precleaned[i]

        # Step 4a: strip header
        top_removed, middle = _remove_common_word_prefix(base, t_orig)

        # Step 4b: strip footer
        bottom_removed = ""
        bottom_candidate, middle_after_suffix = _remove_common_word_suffix(base, middle)
        if bottom_candidate:
            bottom_removed = bottom_candidate
            middle = middle_after_suffix

        # Step 4c: fallback â€” interior substring (watermark, mid-page repeat)
        if not top_removed and not bottom_removed:
            sub_removed, middle_after_sub = _remove_case_insensitive_substring(
                base, middle, min_chars=min_common_substring_chars
            )
            if sub_removed:
                norm_middle = _lower_strip(middle)
                norm_removed = _lower_strip(sub_removed)
                if norm_middle.startswith(norm_removed):
                    top_removed = sub_removed
                elif norm_middle.endswith(norm_removed):
                    bottom_removed = sub_removed
                else:
                    top_removed = sub_removed  # classify as top when position is ambiguous
                middle = middle_after_sub

        # Step 4d: second suffix pass if only prefix was removed
        if top_removed and not bottom_removed:
            bottom_candidate2, middle_after_suffix2 = _remove_common_word_suffix(base, middle)
            if bottom_candidate2:
                bottom_removed = bottom_candidate2
                middle = middle_after_suffix2

        # Record first seen top/bottom
        if top_removed and not first_top_removed:
            first_top_removed = top_removed.strip()
        if bottom_removed and not first_bottom_removed:
            first_bottom_removed = bottom_removed.strip()

        middle = _collapse_consecutive_duplicate_lines(middle)
        cores.append((middle or "").strip())

    return cores, first_top_removed, first_bottom_removed

def is_text_good(text: str, min_chars: int = 800, min_alpha_ratio: float = 0.15) -> bool:
    if not text:
        return False
    if len(text) < min_chars:
        return False

    letters = sum(ch.isalpha() for ch in text)
    ratio = letters / max(len(text), 1)

    bad = text.count("\ufffd") + len(re.findall(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", text))
    bad_ratio = bad / max(len(text), 1)

    return ratio >= min_alpha_ratio and bad_ratio < 0.01


def pdf_text_best_effort(pdf_path: Path, max_pages: int, *, min_font_size: float | None = None) -> str:
    text = pdf_text_layout_preserving(pdf_path, max_pages=max_pages, min_font_size=min_font_size)
    if text.strip():
        return text

    # Font-size filter was set: no point falling back â€” nothing above threshold.
    if min_font_size is not None:
        return ""

    try:
        reader = PdfReader(str(pdf_path))
        parts = []
        for i, page in enumerate(reader.pages[:max_pages], start=1):
            t = page.extract_text() or ""
            if t.strip():
                parts.append(f"\n--- PAGE {i} (text) ---\n{t}")
        return "\n".join(parts).strip()
    except Exception:
        return ""

def pdf_text_first_pages_best_effort(pdf_path: Path, max_pages: int = 10, min_font_size: int = 10) -> str:
    text = pdf_text_best_effort(pdf_path, max_pages=max_pages, min_font_size=min_font_size)

    # Third-tier fallback: PyMuPDF plain text mode
    if not is_text_good(text, min_chars=200, min_alpha_ratio=0.10):
        try:
            doc = fitz.open(str(pdf_path))
            parts = []
            for i in range(min(len(doc), max_pages)):
                t = doc.load_page(i).get_text("text") or ""
                if t.strip():
                    parts.append(f"\n--- PAGE {i + 1} (text) ---\n{t}")
            if parts:
                text = "\n".join(parts)
        except Exception:
            pass

    return text or ""

def pdf_text_per_page(pdf_path: Path, max_pages: int) -> list[str]:
    """
    Returns per-page text in layout-preserving form (preferred) with fallback.
    """
    # Preferred: layout-preserving per page
    try:
        doc = fitz.open(str(pdf_path))
        out = []
        for i in range(min(len(doc), max_pages)):
            page = doc.load_page(i)
            words = page.get_text("words") or []
            if words:
                lines = _group_words_into_lines(words, y_tol=PDF_LAYOUT_LINE_Y_TOL)
                out.append(
                    _render_lines_to_fixed_width(
                        lines,
                        width_chars=PDF_LAYOUT_WIDTH_CHARS,
                        gap_mult=PDF_LAYOUT_GAP_MULT,
                        use_tabs=PDF_LAYOUT_USE_TABS,
                        tab_size_chars=PDF_LAYOUT_TAB_SIZE_CHARS,
                    )
                )
            else:
                out.append("")
        return out
    except Exception:
        pass

    # Fallback: pypdf per page
    try:
        reader = PdfReader(str(pdf_path))
        return [(p.extract_text() or "") for p in reader.pages[:max_pages]]
    except Exception:
        return []

def count_good_chars(text: str) -> int:
    return sum(ch.isalnum() for ch in (text or ""))

def doc_type_label(p: Path) -> str:
    ext = p.suffix.lower()
    if ext in (".pdf", ".PDF"):
        return "PDF"
    if ext == ".xlsx":
        return "XLSX"
    if ext == ".csv":
        return "CSV"
    if ext == ".docx":
        return "DOCX"
    if ext == ".doc":
        return "DOC"
    if ext == ".xls":
        return "XLS"
    return ext.upper().lstrip(".")

def pdf_pages_to_image_data_urls(pdf_path: Path, max_pages: int, dpi: int = 100) -> list[str]:
    doc = fitz.open(str(pdf_path))
    urls: list[str] = []
    for i in range(min(len(doc), max_pages)):
        page = doc.load_page(i)
        pix = page.get_pixmap(dpi=dpi)
        b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
        urls.append(f"data:image/png;base64,{b64}")
    return urls


def build_attachment_evidence(
    p: Path,
    *,
    max_pages_text: int,
    max_pages_vision: int,
    dpi: int,
    min_good_chars_per_page: int,
    min_font_size: int,
) -> dict:
    doc_type = doc_type_label(p)

    if p.suffix.lower() == ".pdf":
        # Step 1: extract text as a list — one string per page
        page_texts = pdf_text_per_page(p, max_pages=max_pages_text)

        # Step 2: score each page by alphanumeric char count
        good_counts = [count_good_chars(t) for t in page_texts]
        max_good = max(good_counts, default=0)

        # Step 3: strip repeated headers / footers across pages
        clean_pages, top_page, bot_page = dedupe_pages_extract_tops_bottoms(
            page_texts, min_common_substring_chars=100
        )

        # Step 4: join cleaned bodies
        extracted_body = "\n".join((t or "").strip() for t in clean_pages).strip()

        # Step 4 (cont.): sandwich header + body + footer
        parts = []
        if top_page:
            parts.append(top_page.strip())
        if extracted_body:
            parts.append(extracted_body)
        if bot_page:
            parts.append(bot_page.strip())
        extracted_text = "\n\n".join(parts).strip()

        # Step 5: quality gate
        allow_text_only = max_good >= min_good_chars_per_page
        good_score = max_good
            
    else:
        # Non-PDF branches (DOCX, XLSX, CSV) — out of scope for this notebook
        print(f"Non-PDF branch not covered in this notebook: {p.suffix}")

    return {
        "path": str(p),
        "filename": p.name,
        "doc_type": doc_type,
        "extracted_text": extracted_text or "",
        "allow_text_only": bool(allow_text_only and (extracted_text or "").strip()),
        "good_score": int(good_score),
    }
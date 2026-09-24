"""Prompts for the document segmentation node.

Unlike the other prompt modules, these are builders rather than module-level
constants: `total_pages` is interpolated into the text. That interpolation is the
mechanism that keeps page counting out of the model's hands — the count comes from
pypdf and is stated as authoritative, so the model only assigns boundaries inside a
range it was given.
"""

from langchain_core.messages import HumanMessage, SystemMessage


def build_segmentation_system_prompt(total_pages: int) -> str:
    """The segmentation system prompt for a PDF with a known page count."""
    return f"""
You are a document segmentation system for accounting documents.

Your task is ONLY to identify the boundaries of the independent accounting
documents inside the attached PDF.

The PDF has exactly {total_pages} page(s). This number is authoritative — do
NOT re-count the pages and do NOT return page numbers outside the range
1..{total_pages}.

For each document return:

- start_page (1-based, inclusive, between 1 and {total_pages})
- end_page   (1-based, inclusive, between 1 and {total_pages})
- confidence (0-1)

Do NOT extract invoice information (no supplier, amounts, VAT, dates, etc.).

A new document begins whenever a new invoice, receipt, credit note, debit
note or unrelated accounting document starts.

There can be multiple independent documents in a single PDF, and they may be
of different types.

There can also be multiple copies of the same document. Treat each copy as a
DISTINCT document and return it separately. If there is an original and copy,
there should be two SEPERATE entries in the output.

Cover every page exactly once: the boundaries must be contiguous and
non-overlapping. The first document must start at page 1 and the last document
must end at page {total_pages}.
"""


def build_segmentation_system_message(total_pages: int) -> SystemMessage:
    """Build the segmentation SystemMessage for a PDF with a known page count."""
    return SystemMessage(content=build_segmentation_system_prompt(total_pages))


def build_segmentation_human_message(filename: str, encoded_pdf: str, total_pages: int) -> HumanMessage:
    """Build the segmentation HumanMessage carrying the PDF itself."""
    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": (
                    f"This PDF has {total_pages} page(s). "
                    "Identify the boundaries of the independent accounting documents. "
                    f"All page numbers must be between 1 and {total_pages}."
                ),
            },
            {"type": "file", "base64": encoded_pdf, "mime_type": "application/pdf"},
        ]
    )

"""Prompts for the payment segmentation node.

`total_pages` is interpolated at the very END of the system prompt: everything
before it is identical across calls and can be served from the provider's prefix
cache, which a varying page count at the top would invalidate every time.

Stating the count at all is what keeps page counting out of the model's hands —
it comes from pypdf and is given as authoritative.
"""

from langchain_core.messages import HumanMessage, SystemMessage

# Static prefix — identical on every call, so it stays cacheable.
SEGMENTATION_SYSTEM_PREFIX = """
You are a document segmentation system for an accounts-receivable department.

Your task is ONLY to identify the boundaries of the independent documents inside
the attached PDF.

For each document return:

- start_page (1-based, inclusive)
- end_page   (1-based, inclusive)
- confidence (0-1)

Do NOT extract any information from the documents (no client, amounts,
document numbers, dates, etc.). Boundaries only.

A NEW DOCUMENT BEGINS when a new payment note, remittance advice, transfer
receipt, or any other unrelated document starts. Signals include a fresh
letterhead or title block, a new payment reference, a restarting page counter
("Page 1 of 2"), or a new addressee.

ONE DOCUMENT CONTINUES across pages when the following page carries on the same
payment: a document table that spills over, a continued list of settled
documents, a totals page that closes the table before it, or a page that repeats
the same payment reference.

A long table of settled documents is ONE document, not one per page. Splitting a
payment note away from its own totals line would make both halves unreadable, so
when in doubt prefer FEWER, larger documents.

Several independent payment notes CAN arrive in one PDF, and they may be
addressed to different parties or cover different payments. Treat each as its
own document.

There can also be multiple copies of the same document. Treat each copy as a
DISTINCT document and return it separately.

Cover every page exactly once: the boundaries must be contiguous and
non-overlapping. The first document must start at page 1 and the last document
must end at the final page.
"""


def build_segmentation_system_prompt(total_pages: int) -> str:
    """The payment segmentation system prompt for a PDF with a known page count."""
    return (
        f"{SEGMENTATION_SYSTEM_PREFIX}\n"
        f"THIS PDF HAS EXACTLY {total_pages} PAGE(S). That number is authoritative — do\n"
        f"NOT re-count the pages, and do NOT return any page number outside 1..{total_pages}.\n"
    )


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
                    "Identify the boundaries of the independent documents. "
                    f"All page numbers must be between 1 and {total_pages}."
                ),
            },
            {"type": "file", "base64": encoded_pdf, "mime_type": "application/pdf"},
        ]
    )

from langchain_core.language_models import BaseChatModel

from invoice_extraction.invoice_utils.llm_retry import invoke_with_retry
from invoice_extraction.models import DocumentSegmentation
from invoice_extraction.prompts import (
    build_segmentation_human_message,
    build_segmentation_system_message,
)


def segment_document(
    llm: BaseChatModel,
    encoded_pdf: str,
    filename: str,
    total_pages: int,
) -> DocumentSegmentation:
    """Find the boundaries of the independent accounting documents inside one PDF.

    `total_pages` must come from pypdf, never from the model: VLMs cannot count
    pages reliably. It is stated as authoritative in the prompt so the model only
    assigns boundaries within a known 1..total_pages range.

    Returns boundaries only — no classification, no extraction. Callers are
    expected to run `validate_segmentation` on the result before trusting it.
    """
    structured_llm = llm.with_structured_output(DocumentSegmentation)
    system_message = build_segmentation_system_message(total_pages)
    human_message = build_segmentation_human_message(filename, encoded_pdf, total_pages)

    return invoke_with_retry(structured_llm, [system_message, human_message], stage="chunking")

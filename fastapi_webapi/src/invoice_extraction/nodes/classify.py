from typing import cast

from langchain_core.language_models import BaseChatModel

from invoice_extraction.invoice_utils.documents import InvoiceDocument
from invoice_extraction.invoice_utils.llm_retry import invoke_with_retry
from invoice_extraction.models import DocumentClassification
from invoice_extraction.prompts import (
    CLASSIFICATION_SYSTEM_MESSAGE,
    build_classification_human_message,
)
from invoice_extraction.tracing import STAGE_CLASSIFICATION, classification_summary, span


def classify_document(
    llm: BaseChatModel, doc: InvoiceDocument, *, scanned: bool = False
) -> DocumentClassification:
    """Classify a single document: accounting type + legal state.

    `scanned` routes the document to the vision path: the API extracts a PDF's
    text layer rather than reading its pixels, and on a scan that layer is the
    scanner's own OCR, so anything it misread never reaches the model.
    """
    structured_llm = llm.with_structured_output(DocumentClassification)
    human_message = build_classification_human_message(doc, scanned=scanned)

    with span(STAGE_CLASSIFICATION, "LLM") as stage_span:
        stage_span.set_inputs(
            {"filename": doc.filename, "input_mode": "image" if scanned else "pdf"}
        )
        classification = invoke_with_retry(
            structured_llm, [CLASSIFICATION_SYSTEM_MESSAGE, human_message], stage="classification"
        )
        stage_span.set_outputs(classification_summary(classification))
        return cast(DocumentClassification, classification)

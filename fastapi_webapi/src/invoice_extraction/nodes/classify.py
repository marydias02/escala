from langchain_core.language_models import BaseChatModel

from invoice_extraction.invoice_utils.documents import InvoiceDocument
from invoice_extraction.invoice_utils.llm_retry import invoke_with_retry
from invoice_extraction.models import DocumentClassification
from invoice_extraction.prompts import (
    CLASSIFICATION_SYSTEM_MESSAGE,
    build_classification_human_message,
)


def classify_document(llm: BaseChatModel, doc: InvoiceDocument) -> DocumentClassification:
    """Classify a single document: accounting type + legal state.

    Note: `with_structured_output` is called with its default method rather than
    method="function_calling" — pixtral-large via Bedrock rejects tool_choice /
    parallel_tool_calls, which the function-calling path sets.
    """
    structured_llm = llm.with_structured_output(DocumentClassification)
    human_message = build_classification_human_message(doc.filename, doc.encoded_pdf)

    return invoke_with_retry(structured_llm, [CLASSIFICATION_SYSTEM_MESSAGE, human_message])
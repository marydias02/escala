from langchain_core.language_models import BaseChatModel

from invoice_extraction.invoice_utils.documents import InvoiceDocument
from invoice_extraction.invoice_utils.llm_retry import invoke_with_retry
from invoice_extraction.models import DocumentClassification, InvoiceData
from invoice_extraction.prompts import EXTRACTION_SYSTEM_MESSAGE, build_extraction_human_message
from invoice_extraction.tracing import STAGE_EXTRACTION, invoice_data_summary, span


def extract_document(
    llm: BaseChatModel,
    doc: InvoiceDocument,
    classification: DocumentClassification,
) -> InvoiceData:
    """Extract InvoiceData from a document already classified as an invoice-like Original.

    The confirmed classification is passed into the prompt as context so the
    model does not re-classify.
    """
    structured_llm = llm.with_structured_output(InvoiceData)
    human_message = build_extraction_human_message(
        doc.filename, doc.encoded_pdf, classification
    )

    with span(STAGE_EXTRACTION, "LLM") as stage_span:
        stage_span.set_inputs(
            {
                "filename": doc.filename,
                "document_type": classification.document_type.value,
            }
        )
        invoice_data = invoke_with_retry(
            structured_llm, [EXTRACTION_SYSTEM_MESSAGE, human_message], stage="extraction"
        )
        stage_span.set_outputs(invoice_data_summary(invoice_data))
        return invoice_data
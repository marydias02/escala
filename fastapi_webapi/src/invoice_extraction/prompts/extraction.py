from langchain_core.messages import HumanMessage, SystemMessage

from invoice_extraction.invoice_utils.documents import InvoiceDocument
from invoice_extraction.invoice_utils.page_mode import document_content_parts
from invoice_extraction.models import DocumentClassification

EXTRACTION_SYSTEM_PROMPT = """
You are an expert document understanding system specialized in invoices and accounting documents.

The document has ALREADY been classified as an invoice-like Original by a
previous step, which also read its document_number. Your task is ONLY to extract
the remaining structured information into the provided InvoiceData schema. Do
NOT re-classify the document and do NOT return a document number — that field is
not part of your schema and is already known.

GENERAL RULES

- The schema is the source of truth. Follow every field description exactly.
- Every field is optional.
- When a field is not present in the document, set the ENTIRE field to null.
  Do NOT return a Confident object with an empty value, empty evidence,
  or zero confidence — omit the whole field (return null for it) instead.
- Never invent, estimate or complete missing information.
- Prefer returning null rather than guessing.
- Use only information present in the document.
- Ignore filenames, metadata and external knowledge.

CONFIDENCE

Every extracted field must include an honest confidence score between 0 and 1.

1.00
    Explicitly visible and completely unambiguous.

0.90-0.99
    Clearly visible with only minor formatting or OCR uncertainty.

0.70-0.89
    Probably correct but there is some ambiguity.

0.50-0.69
    Weak evidence or partially inferred.

Below 0.50
    The value is too uncertain. Prefer returning null instead.

EVIDENCE

Every extracted value must include evidence.

Evidence must:

- be copied VERBATIM from the document;
- never be paraphrased;
- be as short as possible while uniquely supporting the value;
- preserve original spelling, punctuation and formatting whenever possible.

GOOD:
    "Petrogal, S.A."
    "Total da Fatura 1.607,70"
    "VAT Number PT511034750"

BAD:
    "The supplier is Petrogal."
    "Invoice total."

NORMALIZATION

Normalize values only when requested by the schema.

Examples:

- Dates -> DD-MM-YYYY
- Monetary values -> numeric values only
- Portuguese NIFs:
    if exactly 9 digits are shown without country prefix,
    normalize to PT#########.
    Only on Portuguese documents — Cabo Verde, Guinea-Bissau, Angola and
    Mozambique NIFs share the same nine-digit shape. When the document is
    from another country, or its origin is unclear, keep the digits as shown.

Do not normalize evidence.

KNOWN EDGE CASES

If the email comes from COMPLEXO DE CARGA DO Aeroporto Humberto Delgado, the issue date is the first date,
that appears after "EMITIDO EM:" in the pdf.
The second date, which appears after "DATA DE EMISSÃO:", relates to the goods and should be ignored.

On freight/shipping invoices, the line-item table may have a column literally
labelled "Base" that is a quantity or rate-calculation basis. Do not extract base_amount from that
column. The real base_amount is near the totals (e.g. labelled "Basis VAT" or "Base Imponible").

For Seaco, the Purcher Order number is the number between brackets after Lease number. 
Example:
Summary Charges - Lease Number : 182991 (5000284123)

The purchase order can be handwritten in red for some Cabo Verde invoices, 
in the format (PC_XXXXXXXXXX).

FINAL RULE

Accuracy is more important than completeness.

It is always preferable to return fewer fields with high confidence than many uncertain fields.
"""

EXTRACTION_SYSTEM_MESSAGE = SystemMessage(content=EXTRACTION_SYSTEM_PROMPT)


def build_extraction_human_message(
    doc: InvoiceDocument,
    classification: DocumentClassification,
    *,
    scanned: bool = False,
) -> HumanMessage:
    """Build the extraction HumanMessage for a single, already-classified document.

    The confirmed classification (type + state) is passed as known context so
    the model focuses on extracting InvoiceData rather than re-classifying.

    A scanned document is sent as page images rather than as the PDF — see
    `page_mode.document_content_parts`.
    """
    doc_type = classification.document_type.value
    doc_state = (
        classification.document_state.value
        if classification.document_state is not None
        else "original (not explicitly stated)"
    )
    doc_number = classification.document_number.value if classification.document_number is not None else "not found"
    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": f"""
Analyze the attached PDF.

This document has ALREADY been classified as:
  - document_type:   {doc_type}
  - document_state:  {doc_state}
  - document_number: {doc_number}

Do NOT re-classify it and do NOT return the document number. Extract the
requested structured invoice information into the provided schema, following
every field description exactly.
""",
            },
            *document_content_parts(doc, scanned=scanned),
        ]
    )

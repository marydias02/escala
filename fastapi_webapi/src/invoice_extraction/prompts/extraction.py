from langchain_core.messages import HumanMessage, SystemMessage

from email_core.documents import LoadedDocument
from email_core.pdf.page_mode import document_content_parts
from invoice_extraction.models import DocumentClassification

EXTRACTION_SYSTEM_PROMPT = """
You are an expert document understanding system specialized in invoices and accounting documents.

The document has ALREADY been classified by a previous step, which also read its
document_number. Your task is ONLY to extract
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

ISSUE DATE

issue_date is the date the supplier issued the document: "Data de Emissão" or
"Issue Date" wins over any other date.

KNOWN EDGE CASES

On a condomínio receipt the supplier is the condomínio named under "CONDOMÍNIO:",
with the NIF from that same block — not the administrator in the letterhead.
Its charges are quotas, not taxed supplies: FCR (Fundo Comum de Reserva) and
permilagem columns are never VAT. Absent an explicit IVA line, vat_amount is 0
and base_amount equals the total.

If the email comes from COMPLEXO DE CARGA DO Aeroporto Humberto Delgado, the issue date is the first date,
that appears after "EMITIDO EM:" in the pdf.
The second date, which appears after "DATA DE EMISSÃO:", relates to the goods and should be ignored.

On freight/shipping invoices, the line-item table may have a column literally
labelled "Base" that is a quantity or rate-calculation basis. Do not extract base_amount from that
column. The real base_amount is near the totals (e.g. labelled "Basis VAT" or "Base Imponible").

For TCL - Terminal de Contentores de Leixões (Yilport), the supplier NIF is the
one after "Legal Person / Registration:" in its address block. The "Vat Reg No"
in the table below it (with Payment Due On, File No, Vessel) is the client's VAT.

For Seaco, the Purcher Order number is the number between brackets after Lease number. 
Example:
Summary Charges - Lease Number : 182991 (5000284123)
Other suppliers may also use similar formats, such as 1234567-5000284123, where the purchase order is the second number after the dash.

The purchase order can be handwritten for some Cabo Verde invoices, usually at
the very top of the page, as a "PC" prefix followed by the 10-digit number
(PC_XXXXXXXXXX, PC-XXXXXXXXXX). Handwriting OCRs poorly: the prefix may arrive
as Pe, le, PL or be lost entirely, the separator may be any dash or space, and a
short page or sequence number may follow. Read an isolated 10-digit number in
that position as the purchase order even when the prefix is garbled. Return the
10 digits ALONE, stripping the prefix, the separator and any trailing number.

FINAL RULE

Accuracy is more important than completeness.

It is always preferable to return fewer fields with high confidence than many uncertain fields.
"""

EXTRACTION_SYSTEM_MESSAGE = SystemMessage(content=EXTRACTION_SYSTEM_PROMPT)


def build_extraction_human_message(
    doc: LoadedDocument,
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
    exception_line = (
        f"\n  - exception:       {classification.document_exception.value} — see KNOWN EDGE CASES"
        if classification.document_exception is not None
        else ""
    )
    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": f"""
Analyze the attached PDF.

This document has ALREADY been classified as:
  - document_type:   {doc_type}
  - document_state:  {doc_state}
  - document_number: {doc_number}{exception_line}

Do NOT re-classify it and do NOT return the document number. Extract the
requested structured invoice information into the provided schema, following
every field description exactly.
""",
            },
            *document_content_parts(doc, scanned=scanned),
        ]
    )

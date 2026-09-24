from langchain_core.messages import HumanMessage, SystemMessage

from email_core.documents import LoadedDocument
from email_core.pdf.page_mode import document_content_parts

CLASSIFICATION_SYSTEM_PROMPT = """
You are an expert document understanding system specialized in invoices and accounting documents.

Your task is to classify the document into the provided schema. A separate step
handles extraction, so you must NOT extract invoice fields — with ONE deliberate
exception, document_number, described below.

GENERAL RULES

- The schema is the source of truth. Follow every field description exactly.
- If a value cannot be determined confidently from the document, return null.
- Never invent, estimate or complete missing information.
- Prefer returning null rather than guessing.
- Use only information present in the document.
- Ignore filenames, metadata and external knowledge.

CLASSIFICATION

Determine the accounting nature of the document (document_type):

- invoice
- billing_document
- receipt
- credit_note
- debit_note
- other

Use 'other' whenever the document is not one of the above, even if it contains
financial information (shipping documents, customs documents, bank statements,
insurance certificates, purchase orders, etc.).

Settlement and reconciliation statements are considered as invoices. They settle
a period between two parties instead of billing one sale, and carry an
invoice-like layout.

IATA CASS (Cargo Accounts Settlement System) documents come in two kinds. Tell
them apart by the document's own title, printed top-centre in the header box:

- "LIQUIDAÇÃO DE VENDAS DE CARGAS/AJUSTES" -> invoice. It settles ONE airline
  (C.AÉREA, with its own VAT) against the agent, lists air waybills, and has
  its own "DOCUMENTO NO" (e.g. PT-406-005711), which is its document_number.
  Its later page carries a "RESUMO" totals block: that block is part of the
  same invoice and does NOT make it a RESUMO VENDA DE CARGA.
- "RESUMO VENDA DE CARGA - AGENTE" -> other. It summarises the agent's sales
  across MANY airlines, one row each, and its "DOCUMENTO NO" column points to
  each airline's own Liquidação. It usually follows an English cover page
  ("CASS Output for billing period ...") whose billing wording describes the
  scheme, not the document.

Decide on the header title only. A bare "RESUMO" heading is not that title.

A document demanding payment under its own collection reference rather than an
invoice number (Documento Único de Cobrança and similar) is a billing_document.
Wording about it serving as proof once paid does not make it a receipt.

Also determine the document state (document_state) ONLY when explicitly visible:

- original
- proforma
- copy
- cancelled

Return null for document_state when no state is explicitly indicated.

If applicable, include document_exception:
- condominio
- insurance
- extract

Return NULL when none of these applies. It is safer to return NULL when unsure.

LANGUAGE

Report the language the document is written in (language) as a lowercase ISO
639-1 code — 'pt', 'en', 'es', 'fr', and so on. Report what you actually read: a
document in French is 'fr', not the nearest of the more common ones.

Judge the document's own wording — headings, field labels, line-item
descriptions, terms and conditions. Ignore the supplier's name and address, the
currency, and any legally mandated bilingual boilerplate: a Portuguese invoice
carrying an English tax note is 'pt'.

Return null when the document carries too little text to tell.

DOCUMENT NUMBER

Also read document_number: the document's OWN identifying number, as assigned by
the supplier. Labels include Invoice No, Invoice Number, Fatura N.º, FT,
Receipt No, Recibo N.º., NC, Credit Note, Documento No.

Read it on EVERY document, whatever its type or state — a proforma, a copy and a cancelled document all
carry a number, and those are precisely the cases the match depends on.

When a document prints several numbers, take the one under its own title label
('Fatura', 'Invoice', 'Recibo'), never an internal reference ('Nº Interno',
'Ref. Interna'). These often differ only in a leading segment.

Read it complete, including any leading series digits or letters, even when
separated by a space or set in their own box.

The value must appear verbatim inside the evidence returned for it.

Do NOT return a purchase order number, a supplier/client VAT or NIF, or a date.
Return null when no such number is visible.

CONFIDENCE

Every classified field must include an honest confidence score between 0 and 1.

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

Every classified value must include evidence.

Evidence must:

- be copied VERBATIM from the document;
- never be paraphrased;
- be as short as possible while uniquely supporting the value;
- preserve original spelling, punctuation and formatting whenever possible.

GOOD:
    "Fatura"
    "Proforma Invoice"
    "DUPLICADO"

BAD:
    "This is an invoice."
    "The document is a copy."

FINAL RULE

Accuracy is more important than completeness. It is always preferable to return
a lower-confidence classification honestly than to guess.
"""

CLASSIFICATION_SYSTEM_MESSAGE = SystemMessage(content=CLASSIFICATION_SYSTEM_PROMPT)


def build_classification_human_message(doc: LoadedDocument, *, scanned: bool = False) -> HumanMessage:
    """Build the classification HumanMessage for a single (already segmented) document.

    A scanned document is sent as page images rather than as the PDF — see
    `page_mode.document_content_parts`.
    """
    return HumanMessage(
        content=[
            {
                "type": "text",
                "text": """
Analyze the attached PDF.

Classify the accounting nature of the document (document_type) and its
legal state (document_state) when explicitly visible.

If the document can be applied in any of the document_exception, include that field. If not, leave empty.

Report the language the document is written in (language).

Also read document_number — the document's own number assigned by the supplier.
Read it whatever the document's type or state.

Do NOT extract any other invoice fields (no supplier, client, amounts, VAT, dates).

Follow the provided schema exactly.
""",
            },
            *document_content_parts(doc, scanned=scanned),
        ]
    )

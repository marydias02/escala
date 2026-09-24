from typing import Literal

from pydantic import BaseModel, Field

from email_core.confidence import Confident


class DocumentClassification(BaseModel):
    """
    Semantic classification of the document.

    The goal is to identify the accounting nature of the document, independently
    from its visual appearance.
    """

    document_type: Confident[
        Literal[
            "invoice",
            "billing_document",
            "receipt",
            "credit_note",
            "debit_note",
            "other",
        ]
    ] = Field(
        description="""
    Primary accounting document type.

    Choose:

    - invoice
    - billing_document
    - receipt
    - credit_note
    - debit_note
    - other

    Use 'other' whenever the document is not one of the above, even if it contains
    financial information (shipping documents, customs documents, bank statements,
    insurance certificates, purchase orders, etc.).

    Avisos de recibo (Receipt notices) are considered receipts.

    Documents "Anexos" (Annexes) are considered other.

    Settlement/reconciliation statements (Liquidação, IATA CASS, statement of
    account) are to be considered as invoice, when they actually settle a
    balance between two parties.

    RESUMO VENDA DE CARGA are other, whatever else the document carries. They
    report an agent's own sales to the airlines, so there is nothing billed to
    us. These arrive bundled behind a CASS/IATA cover page full of settlement
    and billing-period wording: that cover page describes the scheme, not this
    document. Where "RESUMO VENDA DE CARGA" appears anywhere in the document,
    the type is other and the settlement rule above does not apply.

    billing_document is a demand for payment issued under its own collection
    reference rather than an invoice number — Documento Único de Cobrança (DUC)
    and similar. Wording about the document serving as proof once paid describes
    what it becomes after payment, not what it is: classify it here, not as a
    receipt.

    Do not infer the type from filenames.
    Only use the document contents.
    """
    )

    document_state: Confident[Literal["original", "proforma", "copy", "cancelled"]] | None = Field(
        default=None,
        description="""
    Legal status of the document.

    Examples:

    Proforma Invoice (provisional invoice)
    Original
    Cópia (copy)
    Duplicate (copy)
    Duplicado (copy)
    ANULADO (cancelled)
    Cancelled (cancelled)

    Return null when no state is explicitly indicated.
    """,
    )
    document_number: Confident[str] | None = Field(
        default=None,
        description="""
    The document's own identifying number, as assigned by the supplier.

    Usually labelled:

    Invoice No
    Invoice Number
    Fatura N.º
    FT
    Receipt No
    Recibo N.º

    This identifies THIS document, not a purchase order and not a
    supplier/client registry id.

    Do NOT return:

    - purchase order numbers
    - supplier or client VAT/NIF
    - due date or issue date

    Read this number on EVERY document, whatever its type or state — including
    proformas, copies and cancelled documents. It is what allows a duplicate to
    be matched against its original.
    """,
    )

    language: Confident[str] | None = Field(
        default=None,
        description="""
    The language the document is written in, as a lowercase ISO 639-1 code:
    'pt', 'en', 'es', 'fr', ...

    Judge the document's own wording — headings, labels, terms and conditions —
    not the supplier's name or address, and not the currency.

    Return null when the document carries too little text to tell.
    """,
    )

    document_exception: Confident[Literal["condominio", "insurance", "extract"]] | None = Field(
        default=None,
        description="""
    Optional exceptions that should be populated when a document is a receipt.
    Condomínio refers to service charges of buildings.
    Insurance refers to receipts from insurance companies.
    Extract refers to bank extract.
    If none of the above applies, assume None. SHOULD BE NONE BY DEFAULT
    """,
    )


def normalize_document_number(value: str | None) -> str | None:
    """The comparable form of a document number, or None when there is nothing to compare.

    Suppliers rarely print the same number identically twice: "FT 2024/123",
    "FT2024/123" and "ft 2024/123" are one document. Matching a duplicate against
    its original therefore compares this form, not the raw string — casefolded,
    with spaces, dots and hyphens dropped.

    Separators are dropped rather than collapsed because they are decorative in
    these references; digits and letters are not, so nothing that distinguishes
    two real documents is lost.
    """
    if value is None:
        return None

    normalized = "".join(char for char in value.casefold() if char.isalnum())
    return normalized or None


def document_number_of(classification: DocumentClassification | None) -> str | None:
    """The raw document number read at classification, or None."""
    if classification is None or classification.document_number is None:
        return None
    return classification.document_number.value

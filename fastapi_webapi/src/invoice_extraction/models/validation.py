from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from invoice_extraction.models.common import Checked, drop_empty_confident_fields


class ValidationReport(BaseModel):
    """
    Final, post-validation view of an invoice.

    This is the pipeline's output. Every field holds the value the validator
    believes is CORRECT — not the raw extracted value. When validation finds an
    error (for example supplier and client swapped), the corrected value goes
    here; the original `InvoiceData` is kept alongside for traceability.

    Naming note: `bu_*` are the client fields. "BU" is the business unit being
    billed, i.e. `client_name` / `client_vat` from InvoiceData.

    Return null for any field you cannot confirm or correct.
    """

    supplier_name: Optional[Checked[str]] = Field(
        default=None,
        description="Validated name of the company issuing the invoice (the seller).",
    )

    supplier_id: Optional[Checked[str]] = Field(
        default=None,
        description=(
            "Internal registry id of the supplier. This is NOT present in the document "
            "and cannot be derived from it — always return null. It is filled by a "
            "registry lookup in a later step."
        ),
    )

    supplier_vat: Optional[Checked[str]] = Field(
        default=None,
        description="Validated VAT/NIF of the supplier. Portuguese NIFs normalized to PT#########.",
    )

    bu_name: Optional[Checked[str]] = Field(
        default=None,
        description=(
            "Validated name of the billed party (business unit). This is the CLIENT — "
            "it corresponds to `client_name` in the extracted data."
        ),
    )

    bu_id: Optional[Checked[str]] = Field(
        default=None,
        description=(
            "Internal registry id of the billed business unit. This is NOT present in the "
            "document and cannot be derived from it — always return null. It is filled by a "
            "registry lookup in a later step."
        ),
    )

    bu_vat: Optional[Checked[str]] = Field(
        default=None,
        description=(
            "Validated VAT/NIF of the billed party. This is the CLIENT VAT — it corresponds "
            "to `client_vat` in the extracted data. Portuguese NIFs normalized to PT#########."
        ),
    )

    issue_date: Optional[Checked[str]] = Field(
        default=None,
        description="Validated invoice issue date, normalized to DD-MM-YYYY.",
    )

    base_amount: Optional[Checked[float]] = Field(
        default=None,
        description="Validated net amount before VAT.",
    )

    vat_amount: Optional[Checked[float]] = Field(
        default=None,
        description="Validated total VAT amount (absolute monetary value, not a rate).",
    )

    total_amount: Optional[Checked[float]] = Field(
        default=None,
        description="Validated final payable amount including VAT.",
    )

    currency: Optional[Checked[str]] = Field(
        default=None,
        description="Validated ISO 4217 currency code (EUR, USD, GBP, ...).",
    )

    po_list: List[Checked[str]] = Field(
        default_factory=list,
        description=(
            "Validated purchase order references. Corresponds to `purchase_order` in the "
            "extracted data. Empty list when none are present."
        ),
    )

    notes: str = Field(
        description="""
        Terse validator remarks. Telegraphic style — no prose, no full sentences.
        Record only what a reviewer needs: corrections made, tool results, and
        anything that could not be validated.

        GOOD:
            "supplier/client swapped, fixed. supplier_vat in client registry.
             total 563,21 ok vs parsed text. issue_date not in parsed text, kept."

        BAD:
            "I have carefully reviewed the extracted invoice data and I believe
             that the supplier and the client appear to have been swapped."
        """
    )

    @model_validator(mode="before")
    @classmethod
    def drop_empty_fields(cls, data):
        return drop_empty_confident_fields(data)
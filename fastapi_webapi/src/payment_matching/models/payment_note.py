from pydantic import BaseModel, Field, model_validator

from email_core.confidence import Confident, drop_empty_confident_fields


class PaymentNoteLine(BaseModel):
    """One document the note settles, and the amount applied to it."""

    document_number: Confident[str] | None = Field(
        default=None,
        description="""
    The invoice or document number this amount is applied to, exactly as written
    (keep prefixes, slashes and spacing). Null when the line states an amount
    against no identifiable document.
    """,
    )

    value_paid: Confident[str] | None = Field(
        default=None,
        description="""
    The amount applied to this document, as a plain decimal string using '.' for
    the decimal separator and no thousands separator or currency symbol.
    A discount, withholding or retention is negative: "-12.50".
    """,
    )


class PaymentNoteDocument(BaseModel):
    """A document classified as a payment note, with what it settles.

    `is_payment_note` false means the remaining fields are null and `lines` is
    empty.
    """

    is_payment_note: Confident[bool] = Field(
        description="""
    True when the document is a payment note / remittance advice — it declares
    that an amount HAS BEEN paid and, usually, which documents it settles
    (nota de pagamento, aviso de pagamento, remittance advice, payment advice,
    comprovativo de transferência).

    Signals that make this True:

    - it lists documents with amounts applied to them under a payment total;
    - it is a bank transfer receipt or proof of payment;
    - it states a payment has been executed on a date.

    Signals that make this False:

    - an invoice, credit note or debit note — a document asking to be paid;
    - a statement of account or list of open items with nothing paid;
    - a delivery note, purchase order, quote or contract.

    A document listing invoice numbers is not a payment note unless it declares
    they have been paid.
    """
    )

    payment_note_code: Confident[str] | None = Field(
        default=None,
        description="The note's own reference or document number. Null if it carries none.",
    )

    client_name: Confident[str] | None = Field(
        default=None,
        description="""
    The party that made the payment, as written — the customer paying us, not
    our own company and not the bank. Null if not stated.
    """,
    )

    total_payment_note: Confident[str] | None = Field(
        default=None,
        description="""
    The total the note declares paid, as a plain decimal string using '.' for
    the decimal separator and no thousands separator or currency symbol.
    Null if no total is stated.
    """,
    )

    currency: Confident[str] | None = Field(
        default=None,
        description="ISO-4217 code for the note's amounts: 'EUR', 'USD', 'CVE'. Null if not stated.",
    )

    payment_date: Confident[str] | None = Field(
        default=None,
        description="Date the payment was made, ISO-8601 (YYYY-MM-DD). Null if not stated.",
    )

    lines: list[PaymentNoteLine] = Field(
        default_factory=list,
        description="""
    One entry per document the note settles, in the order they appear. A note
    settling several invoices has several entries; one settling a single invoice
    has one. Empty when the note states a total but identifies no documents.
    """,
    )

    _drop_empty = model_validator(mode="before")(drop_empty_confident_fields)

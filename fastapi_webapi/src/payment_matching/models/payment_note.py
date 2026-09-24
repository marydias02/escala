from pydantic import BaseModel, Field, model_validator

from email_core.confidence import Confident, drop_empty_confident_fields


class PaymentNoteLine(BaseModel):
    """One document the note settles, and the amount applied to it."""

    document_number: Confident[str] | None = Field(
        default=None,
        description="""
    The invoice or document number this amount is applied to, copied exactly as
    written whatever its format — do not normalize, reformat, pad or strip
    anything. Null when the line states an amount against no identifiable
    document.
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
        description="""
    The reference identifying the PAYMENT as a whole. It appears once, usually
    near the top or in a phrase such as "referente ao pagamento X".

    The values listed in the settled-documents table are `document_number`s and
    belong in `lines`, never here. Null if the note carries no payment
    reference of its own.
    """,
    )

    client_name: Confident[str] | None = Field(
        default=None,
        description="""
    Legal or commercial name of the party that MADE the payment — our customer.

    A payment note is issued BY the payer and addressed TO us, so this is the
    document's issuer/sender: usually the top header, logo or company address
    block.

    Do NOT return the addressee — a party marked "ao cuidado de", "A/C",
    "destinatário" or "Exmo(s). Senhor(es)" is us, not the payer, even when it
    is the one shown with a NIF/VAT number. Do NOT return a bank named as the
    transfer's intermediary.

    When the document names only one company, that is the payer.
    """,
    )

    client_vat: Confident[str] | None = Field(
        default=None,
        description="""
    Tax identification number (VAT/NIF/NIPC) of the party that made the payment.

    Usually appears close to the payer's name. Value = digits/prefix only;
    strip label words like "NIF", "CIF", "VAT No." and separators
    (e.g. "NIF·A-48084909" -> "A48084909").

    For Portuguese documents a NIF/NIPC is always nine digits, so a PT-prefixed
    number of any other length is a different registration — do not return it.
    Where exactly nine digits are shown without a country prefix, normalize as
    PT#########. Apply that only when the document itself is Portuguese: Cabo
    Verde, Guinea-Bissau, Angola and Mozambique NIFs are also nine digits, so
    the shape alone proves nothing — on those documents keep the digits exactly
    as shown. Do not invent prefixes for other countries.

    Return null if no payer VAT appears.
    """,
    )

    bu_name: Confident[str] | None = Field(
        default=None,
        description="""
    Name of OUR company receiving the payment — the addressee of the note.

    Usually marked "ao cuidado de", "A/C", "destinatário", "Exmo(s).
    Senhor(es)" or sits in a recipient block. This is the counterpart of
    `client_name`: the payer issues the note, this party receives the money.

    Return null when the document names only one company.
    """,
    )

    bu_vat: Confident[str] | None = Field(
        default=None,
        description="""
    Tax identification number (VAT/NIF/NIPC) of OUR receiving company.

    Usually appears next to the addressee's name, sometimes under a label such
    as "V/N.º Contrib.", "V/NIF" or "Nº Contribuinte". Same normalization as
    `client_vat`: digits/prefix only, labels and separators stripped.

    Return null if no addressee VAT appears.
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
        description="""
    ISO-4217 code for the note's amounts: 'EUR', 'USD', 'CVE'.

    Read it from whatever the document shows — a code, a currency name, or a
    symbol attached directly to an amount ("6059.26€") rather than sitting in
    its own column or header. € -> EUR, $ -> USD, escudos -> CVE.

    Null when nothing indicates a currency.
    """,
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

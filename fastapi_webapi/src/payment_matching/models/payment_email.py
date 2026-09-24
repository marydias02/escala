from pydantic import BaseModel, Field, model_validator

from email_core.confidence import Confident, drop_empty_confident_fields


class PaymentEmailInfo(BaseModel):
    """What an email body says about a payment.

    Every field other than `is_payment_related` is null when the email is not
    about a payment.
    """

    is_payment_related: Confident[bool] = Field(
        description="""
    True when the email is about a payment that has been made or is being
    announced — a remittance advice, a payment confirmation, a transfer notice,
    a payment note (nota de pagamento) delivered in the body or attached.

    Signals that make this True:

    - the body states an amount has been paid, transferred or settled;
    - it announces a payment covering one or more invoices;
    - it forwards or describes a bank transfer, remittance or payment note.

    Signals that make this False:

    - an invoice being DELIVERED to us for future payment;
    - a payment reminder or dunning letter asking us to pay;
    - a quote, order confirmation, statement of account with nothing paid;
    - general correspondence, marketing, newsletters.

    An invoice number in the body is not by itself a payment. Ask whether money
    has moved, or is being declared as moved.

    Return False when the body is empty or gives no indication either way.
    """
    )

    client_name: Confident[str] | None = Field(
        default=None,
        description="""
    The party that MADE the payment — our customer, usually the sender of the
    email or the company they write on behalf of.

    Not our own company (the recipient), and not a bank named as the transfer's
    intermediary. Null if not stated.
    """,
    )

    client_vat: Confident[str] | None = Field(
        default=None,
        description="""
    Tax identification number (VAT/NIF/NIPC) of the party that made the payment.

    Value = digits/prefix only; strip label words like "NIF", "CIF", "VAT No."
    and separators (e.g. "NIF·A-48084909" -> "A48084909").

    For Portuguese senders a NIF/NIPC is always nine digits, so a PT-prefixed
    number of any other length is a different registration — do not return it.
    Where exactly nine digits are shown without a country prefix, normalize as
    PT#########. Apply that only when the email is Portuguese: Cabo Verde,
    Guinea-Bissau, Angola and Mozambique NIFs are also nine digits, so the shape
    alone proves nothing. Do not invent prefixes for other countries.

    Return null if no payer VAT appears.
    """,
    )

    bu_name: Confident[str] | None = Field(
        default=None,
        description="""
    Name of OUR company receiving the payment, when the body names it — the
    addressee, often marked "ao cuidado de", "A/C" or "destinatário".

    Null when the body names only the payer.
    """,
    )

    bu_vat: Confident[str] | None = Field(
        default=None,
        description="""
    Tax identification number (VAT/NIF/NIPC) of OUR receiving company, when the
    body states it. Same normalization as `client_vat`.

    Return null if no addressee VAT appears.
    """,
    )

    invoice_numbers: list[Confident[str]] = Field(
        default_factory=list,
        description="""
    Every invoice or document number the body says the payment settles, copied
    exactly as written whatever its format — do not normalize, reformat, pad or
    strip anything. Empty when none is named.
    """,
    )

    total_amount_paid: Confident[str] | None = Field(
        default=None,
        description="""
    The total amount paid, as a plain decimal string using '.' for the decimal
    separator and no thousands separator or currency symbol: "1234.56".
    Null if no amount is stated.
    """,
    )

    currency: Confident[str] | None = Field(
        default=None,
        description="ISO-4217 code of the amount paid: 'EUR', 'USD', 'CVE'. Null if not stated.",
    )

    payment_reference: Confident[str] | None = Field(
        default=None,
        description="""
    Any reference identifying the payment itself — a payment-note code, transfer
    reference, remittance id. Not an invoice number. Null if absent.
    """,
    )

    payment_date: Confident[str] | None = Field(
        default=None,
        description="Date the payment was made, ISO-8601 (YYYY-MM-DD). Null if not stated.",
    )

    _drop_empty = model_validator(mode="before")(drop_empty_confident_fields)

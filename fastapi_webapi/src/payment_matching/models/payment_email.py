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
    The party that made the payment, as written. This is the customer paying us,
    not our own company and not the bank. Null if not stated.
    """,
    )

    invoice_numbers: list[Confident[str]] = Field(
        default_factory=list,
        description="""
    Every invoice or document number the body says the payment settles, exactly
    as written (keep prefixes, slashes and spacing). Empty when none is named.
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

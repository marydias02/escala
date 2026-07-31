from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from invoice_extraction.models.common import Confident, drop_empty_confident_fields


class InvoiceData(BaseModel):
    """
    Core accounting information extracted from an invoice-like document.

    Every field is optional.

    Never guess.
    Prefer null whenever multiple values could match.
    """

    supplier_name: Optional[Confident[str]] = Field(
        default=None,
        description="""
        Legal or commercial name of the company issuing the invoice.

        Usually located:

        - top header
        - company logo
        - company address block

        This is the seller.

        Do NOT return:

        - customer
        - recipient
        - ship-to
        - consignee
        - billing contact
        """,
    )

    supplier_vat: Optional[Confident[str]] = Field(
        default=None,
        description="""
        Tax identification number (VAT/NIF) of the supplier.

        Usually appears close to the supplier name.

        Examples:

        PT501925350
        PT500697370
        NL800822274B01

        For Portuguese invoices:

        If exactly nine digits are shown without country prefix,
        normalize as:

        PT#########

        Do not invent prefixes for other countries.
        """,
    )

    client_name: Optional[Confident[str]] = Field(
        default=None,
        description="""
        Company or person receiving the invoice.

        Usually located in:

        - customer block
        - invoice address
        - 'Exmo(s). Senhor(es)'
        - Bill To
        - Customer

        Do not confuse with supplier.
        """,
    )

    client_vat: Optional[Confident[str]] = Field(
        default=None,
        description="""
        VAT number of the customer.

        Usually appears close to the customer name.

        Normalize Portuguese NIFs to PT######### when only nine digits
        are shown.

        Return null if no customer VAT appears.
        """,
    )

    document_number: Optional[Confident[str]] = Field(
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
        """,
    )

    purchase_order: List[Confident[str]] = Field(
        default_factory=list,
        description="""
        All purchase order numbers or references found in the invoice.
        Usually appear in the header or customer block.
        Return an empty list if none are present.
        Purchase orders have 10 digits
        """,
    )

    issue_date: Optional[Confident[str]] = Field(
        default=None,
        description="""
        Invoice issue date.

        Normalize to:

        DD-MM-YYYY

        Look for labels such as:

        Issue Date
        Data
        Data de emissão
        Invoice Date

        Do NOT use:

        Due Date
        Shipment Date
        Check-in
        Check-out
        Operation Date
        Service Period
        """,
    )

    base_amount: Optional[Confident[float]] = Field(
        default=None,
        description="""
        Net amount before VAT.

        Usually labelled:

        Base
        Valor Líquido
        Net Amount
        Taxable Amount
        Subtotal

        Do not return the total including VAT.

        When VAT is zero due to exemption or reverse charge,
        this value may equal the total amount.
        """,
    )

    vat_amount: Optional[Confident[float]] = Field(
        default=None,
        description="""
        Total VAT amount charged on the invoice.

        This is an absolute monetary amount.

        Examples:

        55.99
        189.60
        0.00

        Do NOT return:

        23
        16
        6

        Those are VAT rates, not VAT amounts.
        """,
    )

    total_amount: Optional[Confident[float]] = Field(
        default=None,
        description="""
        Final payable amount including VAT.

        Usually labelled:

        Total
        Total Invoice
        Valor Total
        Total da Fatura
        Amount Due

        For zero-VAT invoices:

        total = base amount.

        Do not return intermediate subtotals.
        """,
    )

    currency: Optional[Confident[str]] = Field(
        default=None,
        description="""
        Currency code of the invoice.

        Use ISO 4217 three-letter codes:
        EUR, USD, GBP, JPY, etc.
        If no currency is explicitly indicated, return null.
        """,
    )

    @model_validator(mode="before")
    @classmethod
    def drop_empty_fields(cls, data):
        return drop_empty_confident_fields(data)
from pydantic import BaseModel, Field, model_validator

from email_core.confidence import Confident, drop_empty_confident_fields


class InvoiceData(BaseModel):
    """
    Core accounting information extracted from an invoice-like document.

    Every field is optional.

    Never guess.
    Prefer null whenever multiple values could match.
    """

    supplier_name: Confident[str] | None = Field(
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

    supplier_vat: Confident[str] | None = Field(
        default=None,
        description="""
        Tax identification number (VAT/NIF/NIPC/BRN/Legal person/Registration) of the supplier.

        Usually appears close to the supplier name, but not every number printed
        there is it: suppliers may also show licence or packer
        registrations, sometimes prefixed. Prefer one explicitly labelled
        NIF/NIPC/VAT, even when it sits in the footer among the registered
        office details.

        Value = digits/prefix only. Strip label words like "NIF", "CIF",
        "VAT No." and separators (e.g. "NIF·A-48084909" -> "A48084909").

        Examples:

        PT501925350
        PT500697370
        NL800822274B01

        For Portuguese invoices:

        A NIF/NIPC is always nine digits, so a PT-prefixed number of any other
        length is a different registration — do not return it. Digits may be
        printed spaced apart.

        If exactly nine digits are shown without country prefix,
        normalize as:

        PT#########

        Apply this only when the document itself is Portuguese. Cabo Verde,
        Guinea-Bissau, Angola and Mozambique NIFs are also nine digits, so the
        shape alone proves nothing — on those documents keep the digits exactly
        as shown.

        Do not invent prefixes for other countries.
        """,
    )

    client_name: Confident[str] | None = Field(
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

    client_vat: Confident[str] | None = Field(
        default=None,
        description="""
        VAT number of the customer.

        Usually appears close to the customer name, but may instead sit in a
        header table under a label such as "V/N.º Contrib.", "V/NIF" or
        "Nº Contribuinte" — "V/" meaning yours, i.e. the customer's. In a
        column layout the value is on the line below its label, not beside it,
        and OCR may mangle the label itself.

        Value = digits/prefix only. Strip label words like "NIF", "CIF",
        "VAT No." and separators (e.g. "C.I.F. 511011911" -> "511011911").

        Normalize Portuguese NIFs to PT######### when only nine digits
        are shown.

        Return null if no customer VAT appears.
        """,
    )

    # NOTE: `document_number` is deliberately NOT here. It is read during
    # CLASSIFICATION (see `DocumentClassification.document_number`), because the
    # routing rules need it for documents that never reach extraction at all —
    # a proforma or a copy is gated out, yet its number is exactly what decides
    # whether the same email already carried the original.

    purchase_order: list[Confident[str]] = Field(
        default_factory=list,
        description="""
        All purchase order numbers or references found in the invoice.
        Usually appear in the header or customer block.
        Return an empty list if none are present.
        Purchase orders have 10 digits
        """,
    )

    issue_date: Confident[str] | None = Field(
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

    base_amount: Confident[float] | None = Field(
        default=None,
        description="""
        Net amount before VAT (the taxable base).

        Usually labelled, typically in a VAT/tax summary block near the
        totals (not in the line-item table):

        Basis VAT
        Base Imponible
        Valor Líquido
        Net Amount
        Taxable Amount
        Subtotal

        Some invoices may also have a column inside the line-item table labelled just "Base". 
        On those documents that column is a quantity or rate-calculation basis (e.g. weight,
        units) and is NOT a monetary amount — do not confuse it with the taxable base amount. 
        The real base_amount is a monetary value in the invoice currency, normally found next to
        "VAT Amount" and the VAT rate in the tax summary.

        Do not return the total including VAT.

        When VAT is zero due to exemption or reverse charge,
        this value may equal the total amount.
        """,
    )

    vat_amount: Confident[float] | None = Field(
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

        Only extract an amount explicitly labelled as VAT (IVA, VAT, Tax).
        An unlabelled column sitting between a net value and the total is
        not VAT. If nothing is labelled as VAT, return null.
        """,
    )

    total_amount: Confident[float] | None = Field(
        default=None,
        description="""
        Total amount invoiced, including VAT and before any withholding.

        Usually labelled:

        Total
        Total Invoice
        Valor Total
        Total da Fatura
        Preço Total

        For zero-VAT invoices:

        total = base amount.

        Do not return intermediate subtotals.

        Withholding tax (retenção na fonte, IRS/IR retido) is deducted by the
        customer, not discounted by the supplier: it lowers what is remitted,
        never what is owed. Ignore it. Where a document shows both, take
        "Preço Total" and not "Total Pagar"/"Amount Due", which is already net
        of the retention.
        """,
    )

    currency: Confident[str] | None = Field(
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

from typing import Literal, Optional

from pydantic import BaseModel, Field

from invoice_extraction.models.common import Confident


class DocumentClassification(BaseModel):
    """
    Semantic classification of the document.

    The goal is to identify the accounting nature of the document, independently
    from its visual appearance.
    """

    document_type: Confident[
        Literal[
            "invoice",
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
    - receipt
    - credit_note
    - debit_note
    - other

    Use 'other' whenever the document is not one of the above, even if it contains
    financial information (shipping documents, customs documents, bank statements,
    insurance certificates, purchase orders, etc.).

    Do not infer the type from filenames.
    Only use the document contents.
    """
    )

    document_state: Optional[
        Confident[
            Literal[
                "original",
                "proforma",
                "copy",
                "cancelled",
            ]
        ]
    ] = Field(
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
    """
    )
    document_exception: Optional[
        Confident[
            Literal[
                "condominio",
                "insurance",
                "extract"
            ]
        ]
    ] = Field(
        default=None,
        description="""
    Optional exceptions that should be populated when a document is a receipt. 
    Condomínio refers to service charges of buildings. 
    Insurance refers to receipts from insurance companies. 
    Extract refers to bank extract. 
    If none of the above applies, assume None. SHOULD BE NONE BY DEFAULT
    """,   
    ) 


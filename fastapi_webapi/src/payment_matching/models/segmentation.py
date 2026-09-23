from pydantic import BaseModel, Field


class PaymentDocumentBoundary(BaseModel):
    """Boundary of a single payment document inside a PDF.

    Pages are 1-based and inclusive on both ends.
    """

    start_page: int = Field(description="1-based page where this document starts (inclusive).")
    end_page: int = Field(description="1-based page where this document ends (inclusive).")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Certainty (0-1) that these boundaries are correct.",
    )


class PaymentSegmentation(BaseModel):
    """The independent documents found in one PDF, in reading order.

    The total page count is passed into the prompt as authoritative and is
    deliberately not part of this schema.
    """

    documents: list[PaymentDocumentBoundary] = Field(
        description="Independent documents contained in the PDF, in page order."
    )

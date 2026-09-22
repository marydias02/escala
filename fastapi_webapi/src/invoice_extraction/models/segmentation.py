from pydantic import BaseModel, Field


class DocumentBoundary(BaseModel):
    """
    Boundary of a single independent accounting document inside a PDF.

    Pages are 1-based and inclusive on both ends.
    """

    start_page: int = Field(description="1-based page where this document starts (inclusive).")
    end_page: int = Field(description="1-based page where this document ends (inclusive).")
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Certainty (0-1) that these boundaries are correct.",
    )


class DocumentSegmentation(BaseModel):
    """
    Segmentation result: the independent accounting documents found in the
    PDF, in reading order.

    The total page count is known deterministically (pypdf) and is deliberately
    NOT part of this schema — a VLM cannot reliably count PDF pages. The count is
    passed INTO the prompt as authoritative and the model only assigns boundaries
    within that known 1..total_pages range.
    """

    documents: list[DocumentBoundary] = Field(
        description="Independent accounting documents contained in the PDF, in page order."
    )

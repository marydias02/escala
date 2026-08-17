"""SAP booking — ingesting a validated document into SAP.

Stub today: no SAP integration exists in this repo. book_in_sap logs what it
would book and returns a BookResult.
"""

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class BookResult:
    status: Literal["booked", "failed"]
    document_number: Optional[str]
    error: Optional[str] = None


async def book_in_sap(
    document_number: Optional[str],
    document_type: str,
    document_content: dict,
) -> BookResult:
    """Book one document in SAP. STUB: logs the payload, always returns status="booked"."""
    print(f"  🏦 [STUB] would book in SAP: document_number={document_number!r} type={document_type!r}")
    print(f"            content={document_content!r}")
    return BookResult(status="booked", document_number=document_number)

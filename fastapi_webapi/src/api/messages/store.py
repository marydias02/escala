from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel
from typing_extensions import TypedDict

class PercentageWithDeltaDict(TypedDict):
    pct: float
    delta_pp: float


class ValueWithDeltaDict(TypedDict):
    value: int
    delta_pp: float


class ExtractionBigNumbersDict(TypedDict):
    pending_manual_validation: ValueWithDeltaDict
    auto_ingested: PercentageWithDeltaDict
    returned_to_supplier: PercentageWithDeltaDict


class ValidationBigNumbersDict(TypedDict):
    non_conforming_received: ValueWithDeltaDict
    needs_manual_validation: ValueWithDeltaDict
    processed_by_agent: ValueWithDeltaDict
    with_buyer: ValueWithDeltaDict


class DocumentRead(BaseModel):
    document_id: UUID
    document_number: Optional[str] = None
    supplier_name: Optional[str] = None
    bu_name: Optional[str] = None
    sender_email: Optional[str] = None
    email_subject: Optional[str] = None
    total_amount: Optional[float] = None
    issue_date: Optional[date] = None
    created_at: datetime
    action: Optional[str] = None
    status: Optional[str] = None


class ValidationDocumentRead(BaseModel):
    reference_no: Optional[str] = None
    supplier_name: Optional[str] = None
    bu_name: Optional[str] = None
    doc_id: Optional[str] = None
    total_amount: Optional[float] = None
    document_date: Optional[date] = None
    is_financial: Optional[bool] = None
    last_interaction: Optional[str] = None
    last_interaction_datetime: Optional[datetime] = None
    status: Optional[str] = None
    issue: Optional[str] = None
    owner: Optional[str] = None
    reconciled: Optional[bool] = None


class SapMessageRead(BaseModel):
    internal_id: str
    timestamp: Optional[datetime] = None
    sender: Optional[str] = None
    recipient: Optional[str] = None
    content: Optional[str] = None


class NextPriorityDocumentRead(BaseModel):
    eligible: bool
    next_document_id: Optional[UUID] = None


class DocumentUpdate(BaseModel):
    document_id: UUID
    alerts_list: list[str]
    document_content: dict[str, Any]
    action: Optional[str] = None
    status: Optional[str] = None
    last_modified_by: Optional[str] = None


class ConfidentValue(BaseModel):
    value: Optional[str | float] = None
    confidence: Optional[float] = None


class DocumentDetailRead(BaseModel):
    document_id: UUID
    alerts: list[str]
    fields: dict[str, Optional[ConfidentValue]]
    po_list: list[ConfidentValue]
    action: Optional[str] = None
    status: Optional[str] = None
    # Only a manual send to SAP sets these; a plain read leaves them False.
    sap_booked: bool = False
    process_closed: bool = False


class DocumentEmailRead(BaseModel):
    sender_email: str
    email_subject: Optional[str] = None
    email_content: Optional[str] = None
    reception_date: Optional[datetime] = None

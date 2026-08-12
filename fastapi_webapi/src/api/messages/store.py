from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel
from typing_extensions import TypedDict


class ItemSchema(BaseModel):
    code: str
    description: str
    category: str
    status: str
    score: float


class ItemCreate(BaseModel):
    code: str
    description: str
    category: str
    score: float


class ItemUpdate(BaseModel):
    description: Optional[str] = None
    category: Optional[str] = None
    score: Optional[float] = None
    status: Optional[str] = None


class ItemRead(ItemSchema):
    id: int


class ItemStatisticsDict(TypedDict):
    total_items: int
    average_score: float
    by_status: dict[str, int]
    by_category: dict[str, int]


class ProcessRead(BaseModel):
    process_id: UUID
    sender_email: str
    email_subject: Optional[str] = None
    email_content: Optional[str] = None
    reception_date: Optional[datetime] = None


class PercentageWithDeltaDict(TypedDict):
    pct: float
    delta_pp: float


class ExtractionBigNumbersDict(TypedDict):
    pending_manual_validation: int
    auto_ingested: PercentageWithDeltaDict
    returned_to_supplier: PercentageWithDeltaDict


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


class DocumentEmailRead(BaseModel):
    sender_email: str
    email_subject: Optional[str] = None
    email_content: Optional[str] = None
    reception_date: Optional[datetime] = None

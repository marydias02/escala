from datetime import date, datetime
from datetime import date as DateType
from typing import Any
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
    document_number: str | None = None
    supplier_name: str | None = None
    bu_name: str | None = None
    sender_email: str | None = None
    email_subject: str | None = None
    total_amount: float | None = None
    issue_date: date | None = None
    created_at: datetime
    action: str | None = None
    status: str | None = None


class ValidationDocumentRead(BaseModel):
    reference_no: str | None = None
    supplier_name: str | None = None
    bu_name: str | None = None
    doc_id: str | None = None
    total_amount: float | None = None
    document_date: date | None = None
    is_financial: bool | None = None
    last_interaction: str | None = None
    last_interaction_datetime: datetime | None = None
    status: str | None = None
    issue: str | None = None
    owner: str | None = None
    reconciled: bool | None = None


class SapMessageRead(BaseModel):
    internal_id: str
    timestamp: datetime | None = None
    sender: str | None = None
    recipient: str | None = None
    content: str | None = None


class NextPriorityDocumentRead(BaseModel):
    eligible: bool
    next_document_id: UUID | None = None


class DocumentUpdate(BaseModel):
    document_id: UUID
    alerts_list: list[str]
    document_content: dict[str, Any]
    action: str | None = None
    status: str | None = None
    last_modified_by: str | None = None


class ConfidentValue(BaseModel):
    value: str | float | None = None
    confidence: float | None = None


class DocumentDetailRead(BaseModel):
    document_id: UUID
    alerts: list[str]
    fields: dict[str, ConfidentValue | None]
    po_list: list[ConfidentValue]
    action: str | None = None
    status: str | None = None
    # Only a manual send to SAP sets these; a plain read leaves them False.
    sap_booked: bool = False
    process_closed: bool = False


class DocumentEmailRead(BaseModel):
    sender_email: str
    email_subject: str | None = None
    email_content: str | None = None
    reception_date: datetime | None = None


class SupplierSearchRead(BaseModel):
    supplier_id: str
    name: str
    vat: str | None = None
    country: str | None = None
    is_financial: int | None = None


class BusinessUnitSearchRead(BaseModel):
    bu_id: str
    name: str
    vat: str | None = None
    country: str | None = None


class PurchaseOrderSearchRead(BaseModel):
    po_code: str
    supplier_id: str | None = None
    bu_id: str | None = None
    # Annotated via the alias: the field name shadows `date` inside the class body.
    date: DateType | None = None
    value: float | None = None  # Coerces asyncpg's Decimal, as DocumentRead.total_amount does.
    currency: str | None = None
    # Resolved from the dim tables so selecting a PO can fill the party fields.
    # Null when the PO names a party the current snapshot has not loaded.
    supplier_name: str | None = None
    supplier_vat: str | None = None
    bu_name: str | None = None
    bu_vat: str | None = None

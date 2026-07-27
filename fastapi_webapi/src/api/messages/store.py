from datetime import datetime
from typing import Optional
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


from datetime import datetime, date
from pydantic import BaseModel, Field
from typing import Optional

class DocumentCreate(BaseModel):
    qr_id: str = Field(..., min_length=1, max_length=255)
    title: Optional[str] = None

class AssignInput(BaseModel):
    recipient: str
    distributed_by: Optional[str] = None
    distributed_at: Optional[datetime] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None

class ReturnInput(BaseModel):
    returned_by: Optional[str] = None
    returned_at: Optional[datetime] = None
    notes: Optional[str] = None

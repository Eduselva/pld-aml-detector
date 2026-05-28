from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CaseCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CaseUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CaseOut(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    investigation_ids: list[str] = []
    investigation_count: int = 0

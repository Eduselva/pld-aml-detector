from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import re


class InvestigationCreate(BaseModel):
    entity_name: str
    entity_type: str  # "cpf", "cnpj", or "apelido"
    entity_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    nickname: Optional[str] = None

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        if v not in ("cpf", "cnpj", "apelido"):
            raise ValueError("entity_type must be 'cpf', 'cnpj', or 'apelido'")
        return v

    @field_validator("entity_id", mode="before")
    @classmethod
    def validate_entity_id(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        cleaned = re.sub(r"[.\-/]", "", v)
        if not cleaned.isdigit():
            raise ValueError("entity_id must contain only digits (and optional formatting)")
        return cleaned

    @field_validator("entity_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("entity_name must have at least 2 characters")
        return v


class InvestigationResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    status: str
    entity_type: str
    entity_id: Optional[str] = None
    entity_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    nickname: Optional[str] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class InvestigationListResponse(BaseModel):
    investigations: list[InvestigationResponse]
    total: int

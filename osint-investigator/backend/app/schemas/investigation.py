from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime
import re


class InvestigationCreate(BaseModel):
    entity_name: Optional[str] = None
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

    @field_validator("entity_name", mode="before")
    @classmethod
    def clean_name(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip()
        return v if v else None

    @field_validator("nickname", mode="before")
    @classmethod
    def clean_nickname(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        v = v.strip()
        return v if v else None

    @model_validator(mode="after")
    def require_at_least_one_identifier(self) -> "InvestigationCreate":
        has_name = bool(self.entity_name)
        has_id = bool(self.entity_id)
        has_nickname = bool(self.nickname)
        if not has_name and not has_id and not has_nickname:
            raise ValueError("Informe ao menos um dado: nome, documento ou apelido")
        return self


class InvestigationResponse(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    status: str
    entity_type: str
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
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

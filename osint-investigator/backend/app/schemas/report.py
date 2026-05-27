from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class SourceFinding(BaseModel):
    source_name: str
    status: str
    findings: Optional[dict[str, Any]] = None
    risk_contribution: float
    collected_at: Optional[datetime] = None
    error_message: Optional[str] = None


class RiskScore(BaseModel):
    total: float
    level: str  # low/medium/high/critical
    corporate: float
    media: float
    lists: float
    government: float
    legal: float
    social: float
    email: float


class Alert(BaseModel):
    severity: str  # info/warning/danger/critical
    message: str
    source: str


class DossierReport(BaseModel):
    investigation_id: str
    entity_name: str
    entity_type: str
    entity_id: Optional[str] = None
    email: Optional[str] = None
    status: str
    created_at: datetime
    risk_score: Optional[RiskScore] = None
    alerts: list[Alert] = []
    sources: list[SourceFinding] = []


class HistoryEntry(BaseModel):
    id: str
    created_at: datetime
    risk_score: Optional[float]
    risk_level: Optional[str]
    alerts: list[Alert] = []
    source_scores: dict[str, float] = {}


class InvestigationHistory(BaseModel):
    entries: list[HistoryEntry]  # all investigations for same entity, newest first (includes current)

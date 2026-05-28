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


class GraphNodeOut(BaseModel):
    id: str
    type: str
    label: str
    value: str
    investigation_id: Optional[str] = None
    risk_level: Optional[str] = None
    risk_score: Optional[float] = None


class GraphEdgeOut(BaseModel):
    id: str
    source_id: str
    target_id: str
    label: str
    relationship_type: str = "auto"
    is_manual: bool = False


class GraphEdgeCreate(BaseModel):
    source_node_id: str
    target_node_id: str
    relationship_type: str
    label: str


class GraphStats(BaseModel):
    subjects: int
    companies: int
    partners: int
    shared_entities: int


class GraphResponse(BaseModel):
    nodes: list[GraphNodeOut]
    edges: list[GraphEdgeOut]
    stats: GraphStats

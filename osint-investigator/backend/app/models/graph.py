import uuid
from typing import Optional
from sqlalchemy import String, Float, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class GraphNode(Base):
    __tablename__ = "graph_nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    type: Mapped[str] = mapped_column(String(20))  # subject / company / partner
    value: Mapped[str] = mapped_column(String(255))  # normalized CNPJ/CPF/name
    label: Mapped[str] = mapped_column(String(255))  # display name
    investigation_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class GraphEdge(Base):
    __tablename__ = "graph_edges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("graph_nodes.id"))
    target_id: Mapped[str] = mapped_column(String(36), ForeignKey("graph_nodes.id"))
    label: Mapped[str] = mapped_column(String(100))
    # "auto" = detected via shared entity; others = manual relationship types
    relationship_type: Mapped[str] = mapped_column(
        String(50), default="auto", server_default="auto"
    )
    is_manual: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0"
    )

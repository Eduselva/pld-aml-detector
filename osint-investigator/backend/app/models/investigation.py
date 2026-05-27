import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/complete/failed
    entity_type: Mapped[str] = mapped_column(String(10))  # cpf/cnpj
    entity_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    entity_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    nickname: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # low/medium/high/critical
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    source_results: Mapped[list["SourceResult"]] = relationship(
        "SourceResult", back_populates="investigation", cascade="all, delete-orphan"
    )


class SourceResult(Base):
    __tablename__ = "source_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    investigation_id: Mapped[str] = mapped_column(String(36), ForeignKey("investigations.id"), nullable=False)
    source_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/running/complete/failed
    findings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    risk_contribution: Mapped[float] = mapped_column(Float, default=0.0)
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="source_results")

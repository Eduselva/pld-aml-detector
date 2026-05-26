import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Consolidates SourceResults into a structured DossierReport."""

    def generate(
        self,
        investigation_id: str,
        entity_name: str,
        entity_type: str,
        entity_id: str,
        email: Optional[str],
        status: str,
        created_at: datetime,
        risk_score: Optional[float],
        risk_level: Optional[str],
        source_results: list,
    ) -> dict:
        """
        Build a complete dossier dict from raw source results.
        This is a utility for assembling the report structure.
        """
        alerts = []
        sources_summary = []

        for sr in source_results:
            findings = sr.get("findings") or {}
            source_alerts = findings.get("alerts", [])
            alerts.extend(source_alerts)

            sources_summary.append({
                "source_name": sr.get("source_name"),
                "status": sr.get("status"),
                "risk_contribution": sr.get("risk_contribution", 0.0),
                "summary": findings.get("summary", ""),
                "data": findings.get("data", {}),
            })

        # Sort by severity
        severity_order = {"critical": 0, "danger": 1, "warning": 2, "info": 3}
        alerts.sort(key=lambda a: severity_order.get(a.get("severity", "info"), 99))

        risk_score_summary = None
        if risk_score is not None and risk_level is not None:
            risk_score_summary = {
                "total": risk_score,
                "level": risk_level,
            }

        return {
            "investigation_id": investigation_id,
            "entity_name": entity_name,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "email": email,
            "status": status,
            "created_at": created_at.isoformat() if created_at else None,
            "risk_score": risk_score_summary,
            "alerts": alerts[:20],
            "sources": sources_summary,
        }

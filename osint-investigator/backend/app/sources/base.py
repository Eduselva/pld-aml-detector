from abc import ABC, abstractmethod
from typing import Optional, Any


class BaseSource(ABC):
    """Abstract base class for all OSINT sources."""

    source_name: str = "base"
    timeout: float = 15.0

    @abstractmethod
    async def collect(
        self,
        entity_id: str,
        entity_name: str,
        email: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """
        Collect data from this source.

        Returns a dict with at least:
        - source: str
        - raw_score: float (0-100)
        - summary: str
        - alerts: list[dict] (severity, message, source)
        - data: dict (source-specific findings)
        """
        ...

    def _make_result(
        self,
        raw_score: float,
        summary: str,
        alerts: list,
        data: dict,
    ) -> dict:
        return {
            "source": self.source_name,
            "raw_score": raw_score,
            "summary": summary,
            "alerts": alerts,
            "data": data,
        }

    def _make_alert(self, severity: str, message: str) -> dict:
        """severity: info | warning | danger | critical"""
        return {"severity": severity, "message": message, "source": self.source_name}

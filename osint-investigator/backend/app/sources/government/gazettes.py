"""
Querido Diário — municipal official gazette search (queridodiario.ok.org.br)

Free, open API by Open Knowledge Brasil. No authentication required.
Searches full text of Brazilian municipal official gazettes by keyword.
Detects administrative sanctions, formal appointments, and government references.
"""
import logging
from typing import Optional, Any
from datetime import date, timedelta

import httpx

from app.sources.base import BaseSource

logger = logging.getLogger(__name__)

BASE_URL = "https://api.queridodiario.ok.org.br"
SINCE_YEARS = 5  # Search gazette publications from the last 5 years


class GazettesSource(BaseSource):
    source_name = "gazettes"
    timeout = 20.0

    async def collect(
        self,
        entity_id: Optional[str],
        entity_name: Optional[str] = None,
        nickname: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        search_terms = []
        if entity_name and entity_name.strip():
            search_terms.append(entity_name.strip())
        if nickname and nickname.strip() and nickname.strip() != entity_name:
            search_terms.append(nickname.strip())
        if entity_id and len(entity_id) == 14:
            search_terms.append(entity_id)

        if not search_terms:
            return self._make_result(
                raw_score=0.0,
                summary="Sem termos de busca disponíveis para diários oficiais.",
                alerts=[],
                data={"results": [], "total_found": 0},
            )

        since = (date.today() - timedelta(days=365 * SINCE_YEARS)).isoformat()
        all_excerpts: list[dict] = []
        seen_urls: set[str] = set()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for term in search_terms[:2]:
                excerpts = await self._search(client, term, since)
                for exc in excerpts:
                    url = exc.get("url", "")
                    if url not in seen_urls:
                        seen_urls.add(url)
                        all_excerpts.append(exc)

        raw_score, alerts = self._compute_score(all_excerpts)
        total = len(all_excerpts)
        if total == 0:
            summary = "Nenhuma publicação encontrada em diários oficiais municipais."
        else:
            summary = f"{total} publicação(ões) encontrada(s) em diários oficiais municipais (últimos {SINCE_YEARS} anos)."

        return self._make_result(
            raw_score=raw_score,
            summary=summary,
            alerts=alerts,
            data={
                "results": all_excerpts[:15],
                "total_found": total,
                "since": since,
            },
        )

    async def _search(self, client: httpx.AsyncClient, term: str, since: str) -> list[dict]:
        try:
            resp = await client.get(
                f"{BASE_URL}/gazettes",
                params={
                    "querystring": term,
                    "since": since,
                    "size": 10,
                    "sort_by": "relevance",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                gazettes = data.get("gazettes", [])
                excerpts = []
                for g in gazettes:
                    for excerpt in g.get("excerpts", [])[:2]:
                        excerpts.append({
                            "date": g.get("date", ""),
                            "territory_name": g.get("territory_name", ""),
                            "state_code": g.get("state_code", ""),
                            "excerpt": excerpt,
                            "url": g.get("url", ""),
                            "edition": g.get("edition_number", ""),
                        })
                return excerpts
            logger.debug(f"Querido Diário: HTTP {resp.status_code} para '{term}'")
        except Exception as e:
            logger.debug(f"Querido Diário falhou: {e}")
        return []

    def _compute_score(self, excerpts: list) -> tuple[float, list]:
        total = len(excerpts)
        if total == 0:
            return 0.0, []

        alerts = []
        if total >= 10:
            score = 60.0
            alerts.append(self._make_alert(
                "danger",
                f"{total} menções em diários oficiais municipais — presença administrativa relevante"
            ))
        elif total >= 4:
            score = 40.0
            alerts.append(self._make_alert(
                "warning",
                f"{total} menções encontradas em diários oficiais municipais"
            ))
        else:
            score = 20.0
            alerts.append(self._make_alert(
                "info",
                f"{total} menção(ões) em diários oficiais municipais"
            ))

        return score, alerts

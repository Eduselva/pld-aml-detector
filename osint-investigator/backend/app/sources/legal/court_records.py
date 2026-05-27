"""
DataJud — CNJ public court records API (api-publica.datajud.cnj.jus.br)

Searches federal courts (STJ, TRF1-5) for judicial processes involving the subject.
Requires env var: DATAJUD_API_KEY (free, register at cnj.jus.br/sistemas/datajud)
"""
import asyncio
import logging
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource
from app.config import settings

logger = logging.getLogger(__name__)

DATAJUD_BASE = "https://api-publica.datajud.cnj.jus.br"

# Federal courts — most relevant for financial crime investigations
FEDERAL_COURTS = ["stj", "trf1", "trf2", "trf3", "trf4", "trf5"]


class CourtRecordsSource(BaseSource):
    source_name = "court_records"
    timeout = 25.0

    async def collect(
        self,
        entity_id: Optional[str],
        entity_name: Optional[str] = None,
        nickname: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        if not settings.datajud_api_key:
            return self._make_result(
                raw_score=0.0,
                summary="Chave DATAJUD_API_KEY não configurada.",
                alerts=[],
                data={"skipped": True},
            )

        headers = {
            "Authorization": f"ApiKey {settings.datajud_api_key}",
            "Content-Type": "application/json",
        }

        search_terms = []
        if entity_name and entity_name.strip():
            search_terms.append(entity_name.strip().upper())
        if nickname and nickname.strip() and nickname.strip() != entity_name:
            search_terms.append(nickname.strip().upper())

        if not search_terms and not entity_id:
            return self._make_result(
                raw_score=0.0,
                summary="Sem dados suficientes para busca judicial.",
                alerts=[],
                data={"processes": [], "total": 0},
            )

        all_processes: list[dict] = []
        seen_numbers: set[str] = set()

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            court_tasks = [
                self._search_court(client, court, search_terms, entity_id)
                for court in FEDERAL_COURTS
            ]
            results = await asyncio.gather(*court_tasks, return_exceptions=True)

        for court_procs in results:
            if isinstance(court_procs, list):
                for proc in court_procs:
                    num = proc.get("numero", "")
                    if num and num not in seen_numbers:
                        seen_numbers.add(num)
                        all_processes.append(proc)

        raw_score, alerts = self._compute_score(all_processes)
        total = len(all_processes)
        if total == 0:
            summary = "Nenhum processo encontrado nos tribunais federais."
        else:
            summary = f"{total} processo(s) judicial(is) encontrado(s) nos tribunais federais."

        return self._make_result(
            raw_score=raw_score,
            summary=summary,
            alerts=alerts,
            data={
                "processes": all_processes[:20],
                "total": total,
                "courts_searched": FEDERAL_COURTS,
            },
        )

    async def _search_court(
        self,
        client: httpx.AsyncClient,
        court: str,
        search_terms: list[str],
        entity_id: Optional[str],
    ) -> list[dict]:
        processes: list[dict] = []
        for term in search_terms[:1]:
            query: dict = {
                "query": {
                    "bool": {
                        "should": [
                            {"match": {"partes.nome": term}},
                        ],
                        "minimum_should_match": 1,
                    }
                },
                "size": 10,
                "_source": [
                    "numero", "classe", "tribunal", "dataAjuizamento",
                    "partes", "assuntos", "movimentos",
                ],
            }
            if entity_id and len(entity_id) in (11, 14):
                query["query"]["bool"]["should"].append(
                    {"match": {"partes.cpfCnpj": entity_id}}
                )

            try:
                resp = await client.post(
                    f"{DATAJUD_BASE}/api_publica_{court}/_search",
                    json=query,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    hits = data.get("hits", {}).get("hits", [])
                    for hit in hits:
                        src = hit.get("_source", {})
                        assuntos = src.get("assuntos", [])
                        classe = src.get("classe", {})
                        processes.append({
                            "numero": src.get("numero", ""),
                            "tribunal": court.upper(),
                            "classe": classe.get("nome", "") if isinstance(classe, dict) else str(classe),
                            "data_ajuizamento": src.get("dataAjuizamento", ""),
                            "assuntos": [
                                a.get("nome", "") if isinstance(a, dict) else str(a)
                                for a in assuntos[:3]
                            ],
                            "url": f"https://www.cnj.jus.br/busca-ativa-de-processos/{src.get('numero', '')}",
                        })
                elif resp.status_code == 401:
                    logger.warning(f"DataJud {court}: chave inválida")
                    break
                else:
                    logger.debug(f"DataJud {court}: HTTP {resp.status_code}")
            except Exception as e:
                logger.debug(f"DataJud {court} falhou: {e}")

        return processes

    def _compute_score(self, processes: list) -> tuple[float, list]:
        total = len(processes)
        if total == 0:
            return 0.0, []

        alerts = []
        if total >= 6:
            score = 70.0
            alerts.append(self._make_alert(
                "danger",
                f"{total} processos judiciais federais encontrados — histórico processual elevado"
            ))
        elif total >= 3:
            score = 50.0
            alerts.append(self._make_alert(
                "warning",
                f"{total} processos judiciais federais encontrados"
            ))
        else:
            score = 30.0
            alerts.append(self._make_alert(
                "info",
                f"{total} processo(s) judicial(is) federal(is) encontrado(s)"
            ))

        return score, alerts

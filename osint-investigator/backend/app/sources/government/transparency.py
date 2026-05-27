"""
Portal da Transparência (api.portaldatransparencia.gov.br)

Searches:
  - /pep            — Politically Exposed Persons (federal)
  - /servidores     — Active federal public servants
  - /ceis           — Ineligible companies/persons (suspended from federal contracts)
  - /cnep           — Penalised companies/persons (CNEP register)

Requires env var: TRANSPARENCIA_API_KEY (free, register at portaldatransparencia.gov.br)
"""
import logging
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource
from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"


class TransparencySource(BaseSource):
    source_name = "transparency_gov"
    timeout = 20.0

    async def collect(
        self,
        entity_id: Optional[str],
        entity_name: Optional[str] = None,
        nickname: Optional[str] = None,
        entity_type: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        if not settings.transparencia_api_key:
            return self._make_result(
                raw_score=0.0,
                summary="Chave TRANSPARENCIA_API_KEY não configurada.",
                alerts=[],
                data={"skipped": True},
            )

        headers = {
            "chave-api-dados": settings.transparencia_api_key,
            "Accept": "application/json",
        }

        results: dict = {
            "pep": [],
            "servidores": [],
            "ceis": [],
            "cnep": [],
        }

        is_company = entity_type == "cnpj"
        search_names = []
        if entity_name and entity_name.strip():
            search_names.append(entity_name.strip())
        if nickname and nickname.strip() and nickname.strip() != entity_name:
            search_names.append(nickname.strip())

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            if not is_company and search_names:
                # PEP and servidores — person only
                for name in search_names[:1]:
                    results["pep"] += await self._get(client, "/pep", {"nome": name, "pagina": 1})
                    results["servidores"] += await self._get(
                        client, "/servidores",
                        {"nome": name, "situacaoServidor": 1, "pagina": 1},
                    )
                    if entity_id and len(entity_id) == 11:
                        results["pep"] += await self._get(client, "/pep", {"cpf": entity_id, "pagina": 1})

            # CEIS and CNEP — both person and company
            for name in search_names[:1]:
                results["ceis"] += await self._get(client, "/ceis", {"nomeSancionado": name, "pagina": 1})
                results["cnep"] += await self._get(client, "/cnep", {"nomeSancionado": name, "pagina": 1})
            if entity_id:
                param_key = "cnpjCpfSancionado"
                results["ceis"] += await self._get(client, "/ceis", {param_key: entity_id, "pagina": 1})
                results["cnep"] += await self._get(client, "/cnep", {param_key: entity_id, "pagina": 1})

        # Deduplicate by id/name
        results["pep"] = _dedup(results["pep"], "id")
        results["servidores"] = _dedup(results["servidores"], "id")
        results["ceis"] = _dedup(results["ceis"], "id")
        results["cnep"] = _dedup(results["cnep"], "id")

        raw_score, alerts = self._compute_score(results)

        total = sum(len(v) for v in results.values())
        if total == 0:
            summary = "Nenhum registro encontrado no Portal da Transparência."
        else:
            parts = []
            if results["pep"]:
                parts.append(f"{len(results['pep'])} PEP")
            if results["servidores"]:
                parts.append(f"{len(results['servidores'])} servidor(es) federal(is)")
            if results["ceis"]:
                parts.append(f"{len(results['ceis'])} sanção CEIS")
            if results["cnep"]:
                parts.append(f"{len(results['cnep'])} sanção CNEP")
            summary = "Encontrado no Portal da Transparência: " + ", ".join(parts) + "."

        return self._make_result(
            raw_score=raw_score,
            summary=summary,
            alerts=alerts,
            data=results,
        )

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict) -> list:
        try:
            resp = await client.get(BASE_URL + path, params=params)
            if resp.status_code == 200:
                data = resp.json()
                return data if isinstance(data, list) else []
            if resp.status_code == 401:
                logger.warning("Transparência API: chave inválida ou não autorizada")
            else:
                logger.debug(f"Transparência {path}: HTTP {resp.status_code}")
        except Exception as e:
            logger.debug(f"Transparência {path} falhou: {e}")
        return []

    def _compute_score(self, results: dict) -> tuple[float, list]:
        alerts = []
        score = 0.0

        if results["ceis"] or results["cnep"]:
            score = max(score, 90.0)
            sanctions = results["ceis"] + results["cnep"]
            sample = ", ".join(
                s.get("tipoPena", s.get("descricaoTipoPena", "Sanção")) or "Sanção"
                for s in sanctions[:2]
            )
            alerts.append(self._make_alert(
                "critical",
                f"{len(sanctions)} sanção(ões) federal(is) (CEIS/CNEP): {sample}"
            ))

        if results["pep"]:
            score = max(score, 80.0)
            roles = ", ".join(
                p.get("funcaoDescricao", p.get("descricaoFuncao", "PEP")) or "PEP"
                for p in results["pep"][:2]
            )
            alerts.append(self._make_alert(
                "danger",
                f"Pessoa Politicamente Exposta (PEP): {roles}"
            ))

        if results["servidores"]:
            score = max(score, 25.0)
            organs = ", ".join(
                s.get("orgaoNome", s.get("nomeOrgao", "Órgão federal")) or "Órgão federal"
                for s in results["servidores"][:2]
            )
            alerts.append(self._make_alert(
                "info",
                f"Servidor público federal ativo em: {organs}"
            ))

        return min(score, 100.0), alerts


def _dedup(items: list, key: str) -> list:
    seen: set = set()
    out = []
    for item in items:
        k = item.get(key)
        if k is None or k not in seen:
            if k is not None:
                seen.add(k)
            out.append(item)
    return out

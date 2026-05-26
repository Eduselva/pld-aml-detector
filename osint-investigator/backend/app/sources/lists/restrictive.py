import csv
import io
import logging
import os
import unicodedata
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource
from app.config import settings

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.85
OFAC_CSV_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
CGU_PEP_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/pep"

# Cache de dados OFAC em memória
_ofac_cache: list[dict] = []
_ofac_loaded_at: Optional[datetime] = None
_OFAC_TTL = timedelta(hours=24)


def normalize_name(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


async def _load_ofac_list() -> list[dict]:
    """Baixa e parseia a lista SDN do OFAC (treasury.gov). Cache de 24h."""
    global _ofac_cache, _ofac_loaded_at

    now = datetime.utcnow()
    if _ofac_cache and _ofac_loaded_at and (now - _ofac_loaded_at) < _OFAC_TTL:
        return _ofac_cache

    logger.info("Baixando lista OFAC SDN de treasury.gov...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(OFAC_CSV_URL)
        if resp.status_code != 200:
            logger.warning(f"OFAC download falhou: HTTP {resp.status_code}")
            return _ofac_cache  # retorna cache antigo se houver

        entries = []
        reader = csv.reader(io.StringIO(resp.text))
        for row in reader:
            if len(row) < 3:
                continue
            name = row[1].strip().strip('"')
            sdn_type = row[2].strip().lower() if len(row) > 2 else ""
            program = row[3].strip() if len(row) > 3 else ""
            remarks = row[11].strip() if len(row) > 11 else ""
            if name and name != "SDN_Name":
                entries.append({
                    "name": name,
                    "type": sdn_type,
                    "program": program,
                    "reason": remarks[:200] if remarks else "Sanção OFAC/SDN",
                    "list": "OFAC/SDN",
                })

        _ofac_cache = entries
        _ofac_loaded_at = now
        logger.info(f"Lista OFAC carregada: {len(entries)} entradas.")
        return entries

    except Exception as e:
        logger.error(f"Erro ao baixar lista OFAC: {e}")
        return _ofac_cache  # retorna cache antigo se houver


async def _search_cgu_pep(name: str) -> list[dict]:
    """Busca PEP na API da CGU/Transparência Brasil."""
    if not settings.cgu_api_key:
        return []

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                CGU_PEP_URL,
                params={"nome": name, "pagina": 1},
                headers={"chave-api-dados": settings.cgu_api_key},
            )
        if resp.status_code == 401:
            logger.warning("CGU API: chave inválida ou sem permissão.")
            return []
        if resp.status_code != 200:
            logger.warning(f"CGU API retornou HTTP {resp.status_code}")
            return []

        data = resp.json()
        results = []
        for item in (data if isinstance(data, list) else data.get("data", [])):
            results.append({
                "name": item.get("nome", ""),
                "role": item.get("funcao", "") or item.get("cargo", ""),
                "cpf_partial": item.get("cpf", ""),
                "reason": "Pessoa Politicamente Exposta — base CGU",
                "list": "PEP/CGU",
            })
        return results

    except Exception as e:
        logger.warning(f"Erro na API CGU PEP: {e}")
        return []


def _load_local_pep(name: str) -> list[dict]:
    """Fallback: busca fuzzy no CSV local de PEPs."""
    data_dir = getattr(settings, "data_dir", "/app/data")
    pep_path = os.path.join(data_dir, "pep_sample.csv")
    if not os.path.exists(pep_path):
        local_data = os.path.join(os.path.dirname(__file__), "../../../../data")
        pep_path = os.path.join(local_data, "pep_sample.csv")

    entries = []
    try:
        with open(pep_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                entries.append(row)
    except FileNotFoundError:
        pass
    return entries


class RestrictiveListsSource(BaseSource):
    source_name = "restrictive_lists"
    timeout = 30.0

    async def collect(self, entity_id: Optional[str], entity_name: str,
                      email: Optional[str] = None, **kwargs: Any) -> dict:
        normalized = normalize_name(entity_name)
        matches = []
        alerts = []
        sources_checked = []

        # — OFAC SDN (download automático) —
        ofac_entries = await _load_ofac_list()
        sources_checked.append(f"OFAC/SDN ({len(ofac_entries)} entradas)")

        for entry in ofac_entries:
            entry_norm = normalize_name(entry["name"])
            ratio = fuzzy_ratio(normalized, entry_norm)
            if ratio >= MATCH_THRESHOLD:
                match_type = "exato" if ratio >= 0.98 else "fuzzy"
                matches.append({
                    "list": entry["list"],
                    "name": entry["name"],
                    "reason": entry.get("reason", ""),
                    "nationality": entry.get("nationality", ""),
                    "match_score": round(ratio, 3),
                    "match_type": match_type,
                })
                alerts.append(self._make_alert(
                    "critical" if ratio >= 0.98 else "danger",
                    f"Correspondência OFAC/SDN ({match_type}): {entry['name']} — {entry.get('reason', '')[:80]}"
                ))

        # — PEP Brasil: CGU API (tempo real) ou CSV local —
        cgu_results = await _search_cgu_pep(entity_name)
        if cgu_results:
            sources_checked.append("PEP/CGU (API tempo real)")
            for item in cgu_results:
                item_norm = normalize_name(item["name"])
                ratio = fuzzy_ratio(normalized, item_norm)
                if ratio >= MATCH_THRESHOLD:
                    match_type = "exato" if ratio >= 0.98 else "fuzzy"
                    matches.append({
                        "list": "PEP/CGU",
                        "name": item["name"],
                        "role": item.get("role", ""),
                        "cpf_partial": item.get("cpf_partial", ""),
                        "reason": item["reason"],
                        "match_score": round(ratio, 3),
                        "match_type": match_type,
                    })
                    alerts.append(self._make_alert(
                        "critical" if ratio >= 0.98 else "danger",
                        f"PEP identificado (CGU): {item['name']} — {item.get('role', '')}"
                    ))
        else:
            # Fallback: CSV local
            local_peps = _load_local_pep(entity_name)
            sources_checked.append(f"PEP/local ({len(local_peps)} entradas)")
            for entry in local_peps:
                entry_norm = normalize_name(entry.get("name", ""))
                ratio = fuzzy_ratio(normalized, entry_norm)
                if ratio >= MATCH_THRESHOLD:
                    match_type = "exato" if ratio >= 0.98 else "fuzzy"
                    matches.append({
                        "list": "PEP",
                        "name": entry.get("name", ""),
                        "role": entry.get("role", ""),
                        "cpf_partial": entry.get("cpf_partial", ""),
                        "reason": entry.get("reason", ""),
                        "match_score": round(ratio, 3),
                        "match_type": match_type,
                    })
                    alerts.append(self._make_alert(
                        "critical" if ratio >= 0.98 else "danger",
                        f"Possível PEP ({match_type}): {entry.get('name')} — {entry.get('role', '')}"
                    ))

        raw_score = self._compute_score(matches)
        summary = (
            "Nenhuma correspondência em listas restritivas."
            if not matches
            else f"{len(matches)} correspondência(s): {', '.join(set(m['list'] for m in matches))}"
        )

        return self._make_result(
            raw_score=raw_score,
            summary=summary,
            alerts=alerts,
            data={
                "matches": matches,
                "total_matches": len(matches),
                "sources_checked": sources_checked,
                "cgu_realtime": bool(cgu_results),
            },
        )

    def _compute_score(self, matches: list[dict]) -> float:
        if not matches:
            return 0.0
        return 100.0 if any(m["match_score"] >= 0.98 for m in matches) else 70.0

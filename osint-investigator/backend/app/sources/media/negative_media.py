import logging
import unicodedata

import httpx

from app.sources.base import BaseSource
from app.config import settings

logger = logging.getLogger(__name__)

GOOGLE_URL = "https://www.googleapis.com/customsearch/v1"
SERPER_URL = "https://google.serper.dev/search"

FRAUD_TERMS_PT = ["fraude", "golpe", "estelionato", "lavagem de dinheiro", "COAF",
                  "preso", "condenado", "investigado", "corrupção", "operação policial"]
FRAUD_TERMS_EN = ["fraud", "scam", "money laundering", "arrested", "corruption"]


def _remove_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _name_variants(name: str | None, nickname: str | None) -> list[str]:
    variants = []
    if name and name.strip():
        n = name.strip()
        variants.append(n)
        no_accent = _remove_accents(n)
        if no_accent != n:
            variants.append(no_accent)
        parts = n.split()
        if len(parts) >= 3:
            variants.append(f"{parts[0]} {parts[-1]}")
    if nickname and nickname.strip():
        nick = nickname.strip()
        if nick not in variants:
            variants.append(nick)
        no_acc_nick = _remove_accents(nick)
        if no_acc_nick != nick and no_acc_nick not in variants:
            variants.append(no_acc_nick)
    return list(dict.fromkeys(variants))


def _build_queries(name: str | None, nickname: str | None) -> list[str]:
    variants = _name_variants(name, nickname)
    queries = []
    for variant in variants:
        pt_block = " OR ".join(f'"{t}"' if " " in t else t for t in FRAUD_TERMS_PT)
        queries.append(f'"{variant}" ({pt_block})')
        en_block = " OR ".join(f'"{t}"' if " " in t else t for t in FRAUD_TERMS_EN)
        queries.append(f'"{variant}" ({en_block})')
    return queries


class NegativeMediaSource(BaseSource):
    source_name = "negative_media"
    timeout = 15.0

    async def collect(self, entity_id: str | None, entity_name: str | None, email=None,
                      nickname=None, phone=None, **kwargs) -> dict:
        use_serper = bool(settings.serper_api_key)
        use_google = bool(settings.google_search_api_key and settings.google_search_cx)

        if not use_serper and not use_google:
            return self._make_result(
                raw_score=0.0,
                summary="Busca de mídia negativa indisponível: configure SERPER_API_KEY ou GOOGLE_SEARCH_API_KEY + GOOGLE_SEARCH_CX.",
                alerts=[self._make_alert("warning", "Nenhum motor de busca configurado — mídia negativa desativada")],
                data={"total_results": 0, "results": [], "engine_used": "none", "queries_run": [], "errors": []},
            )

        queries = _build_queries(entity_name, nickname)
        if not queries:
            return self._make_result(
                raw_score=0.0,
                summary="Nenhum termo de busca disponível.",
                alerts=[],
                data={"total_results": 0, "results": [], "engine_used": "none", "queries_run": [], "errors": []},
            )

        engine_used = "serper" if use_serper else "google"

        all_results: list[dict] = []
        seen_urls: set[str] = set()
        errors = []
        queries_run = []

        for query in queries:
            try:
                if use_serper:
                    results, err = await self._serper_search(query)
                else:
                    results, err = await self._google_search(query)

                if err:
                    if not errors:  # log only first error to avoid spam
                        logger.warning(f"Search error [{query[:50]}]: {err}")
                    errors.append(err)

                queries_run.append(query)
                for r in results:
                    if r["url"] not in seen_urls:
                        all_results.append(r)
                        seen_urls.add(r["url"])
            except Exception as e:
                logger.warning(f"Search failed [{query[:50]}]: {e}")
                errors.append(str(e))

        raw_score, alerts = self._compute_score(all_results)
        num = len(all_results)
        summary = (
            "Nenhuma mídia negativa encontrada." if num == 0
            else f"{num} resultado(s) de mídia negativa encontrado(s)."
        )

        return self._make_result(
            raw_score=raw_score,
            summary=summary,
            alerts=alerts,
            data={
                "total_results": num,
                "results": all_results[:20],
                "engine_used": engine_used,
                "queries_run": queries_run,
                "nickname_searched": bool(nickname),
                "errors": errors[:5],
            },
        )

    async def _serper_search(self, query: str) -> tuple[list[dict], str | None]:
        headers = {
            "X-API-KEY": settings.serper_api_key,
            "Content-Type": "application/json",
        }
        payload = {"q": query, "gl": "br", "hl": "pt", "num": 10}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(SERPER_URL, json=payload, headers=headers)
            if resp.status_code != 200:
                error_msg = f"Serper HTTP {resp.status_code}"
                try:
                    body = resp.json()
                    error_msg += f": {body.get('message', '')}"
                except Exception:
                    pass
                return [], error_msg
            data = resp.json()
            results = []
            for item in data.get("organic", []):
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                    "display_url": item.get("displayLink", ""),
                })
            return results, None
        except Exception as e:
            return [], str(e)

    async def _google_search(self, query: str) -> tuple[list[dict], str | None]:
        params = {
            "key": settings.google_search_api_key,
            "cx": settings.google_search_cx,
            "q": query,
            "lr": "lang_pt",
            "num": 10,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(GOOGLE_URL, params=params)
            if resp.status_code != 200:
                error_msg = f"Google CSE HTTP {resp.status_code}"
                try:
                    body = resp.json()
                    error_msg += f": {body.get('error', {}).get('message', '')}"
                except Exception:
                    pass
                return [], error_msg
            data = resp.json()
            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                    "display_url": item.get("displayLink", ""),
                })
            return results, None
        except Exception as e:
            return [], str(e)

    def _compute_score(self, results: list[dict]) -> tuple[float, list]:
        num = len(results)
        if num == 0:
            return 0.0, []
        score = 30.0 if num <= 2 else 60.0 if num <= 5 else 90.0
        severity = "warning" if num <= 2 else "danger" if num <= 5 else "critical"
        alerts = [self._make_alert(severity, f"{num} resultado(s) de mídia negativa encontrado(s)")]
        serious_kw = ["lavagem", "coaf", "preso", "condenado", "operação",
                      "fraude", "golpe", "estelionato"]
        hits = set()
        for r in results:
            text = (r.get("title", "") + " " + r.get("snippet", "")).lower()
            for kw in serious_kw:
                if kw in text:
                    hits.add(kw)
        if hits:
            alerts.append(self._make_alert(
                "critical" if score >= 60 else "danger",
                f"Termos críticos detectados: {', '.join(list(hits)[:4])}"
            ))
        return min(score, 100.0), alerts

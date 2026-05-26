import logging
import re
import unicodedata
from urllib.parse import urlencode, unquote

import httpx
from bs4 import BeautifulSoup

from app.sources.base import BaseSource
from app.config import settings

logger = logging.getLogger(__name__)

DDG_URL = "https://html.duckduckgo.com/html/"
GOOGLE_URL = "https://www.googleapis.com/customsearch/v1"

# Individual fraud terms — used to build simple per-term queries
FRAUD_TERMS_PT = ["fraude", "golpe", "estelionato", "lavagem de dinheiro", "COAF",
                  "preso", "condenado", "investigado", "corrupção", "operação policial"]
FRAUD_TERMS_EN = ["fraud", "scam", "money laundering", "arrested", "corruption"]


def _remove_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _name_variants(name: str, nickname: str | None) -> list[str]:
    """Return search name variants to try."""
    variants = [name]
    no_accent = _remove_accents(name)
    if no_accent != name:
        variants.append(no_accent)
    parts = name.strip().split()
    if len(parts) >= 3:
        variants.append(f"{parts[0]} {parts[-1]}")
    if nickname and nickname.strip():
        variants.append(nickname.strip())
        no_acc_nick = _remove_accents(nickname.strip())
        if no_acc_nick != nickname.strip():
            variants.append(no_acc_nick)
    return list(dict.fromkeys(variants))  # deduplicate preserving order


def _build_queries(name: str, nickname: str | None) -> list[str]:
    """Build simple human-like queries — one name variant + one term at a time."""
    variants = _name_variants(name, nickname)
    queries = []
    # For each variant, search with a combined PT block and EN block
    for variant in variants:
        pt_block = " OR ".join(f'"{t}"' if " " in t else t for t in FRAUD_TERMS_PT)
        queries.append(f'"{variant}" ({pt_block})')
        en_block = " OR ".join(f'"{t}"' if " " in t else t for t in FRAUD_TERMS_EN)
        queries.append(f'"{variant}" ({en_block})')
    return queries


class NegativeMediaSource(BaseSource):
    source_name = "negative_media"
    timeout = 15.0

    async def collect(self, entity_id: str, entity_name: str, email=None,
                      nickname=None, phone=None, **kwargs) -> dict:
        use_google = bool(settings.google_search_api_key and settings.google_search_cx)
        queries = _build_queries(entity_name, nickname)

        all_results: list[dict] = []
        seen_urls: set[str] = set()
        errors = []
        queries_run = []
        engine_used = "google"

        if not use_google:
            return self._make_result(
                raw_score=0.0,
                summary="Busca de mídia negativa indisponível: configure GOOGLE_SEARCH_API_KEY e GOOGLE_SEARCH_CX.",
                alerts=[self._make_alert("warning", "Google CSE não configurado — busca de mídia negativa desativada")],
                data={"total_results": 0, "results": [], "engine_used": "none", "queries_run": []},
            )

        for query in queries:
            try:
                results = await self._google_search(query)
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
                "errors": errors,
            },
        )

    async def _google_search(self, query: str) -> list[dict]:
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
                logger.warning(f"Google CSE returned {resp.status_code}")
                return []
            data = resp.json()
            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "url": item.get("link", ""),
                    "display_url": item.get("displayLink", ""),
                })
            return results
        except Exception as e:
            logger.exception(f"Google CSE error: {e}")
            return []

    async def _ddg_search(self, query: str) -> list[dict]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://duckduckgo.com/",
        }
        payload = urlencode({"q": query, "b": "", "kl": "br-pt"})
        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers,
                                         follow_redirects=True) as client:
                resp = await client.post(DDG_URL, content=payload)
            if resp.status_code != 200:
                return []
            return self._parse_ddg_html(resp.text)
        except Exception as e:
            logger.exception(f"DuckDuckGo search error: {e}")
            return []

    def _parse_ddg_html(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for div in soup.select(".result"):
            title_el = div.select_one(".result__title a")
            snippet_el = div.select_one(".result__snippet")
            url_el = div.select_one(".result__url")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            url = title_el.get("href", "")
            display_url = url_el.get_text(strip=True) if url_el else ""
            if url.startswith("//duckduckgo.com/l/?"):
                m = re.search(r"uddg=([^&]+)", url)
                if m:
                    url = unquote(m.group(1))
            if title and url:
                results.append({"title": title, "snippet": snippet,
                                 "url": url, "display_url": display_url})
        return results

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

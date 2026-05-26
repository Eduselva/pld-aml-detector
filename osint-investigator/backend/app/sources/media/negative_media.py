import logging
import re
import unicodedata
from typing import Optional, Any
from urllib.parse import urlencode, unquote

import httpx
from bs4 import BeautifulSoup

from app.sources.base import BaseSource

logger = logging.getLogger(__name__)

DDG_URL = "https://html.duckduckgo.com/html/"

FRAUD_TERMS_PT = "fraude OR golpe OR estelionato OR \"lavagem de dinheiro\" OR COAF OR investigado OR preso OR condenado OR corrupção OR desvio"
FRAUD_TERMS_EN = "fraud OR scam OR \"money laundering\" OR arrested OR corruption"


def _remove_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _build_queries(name: str, nickname: Optional[str]) -> list[tuple[str, str]]:
    """Return list of (label, query) tuples to run."""
    queries = []
    # Exact name with fraud terms
    queries.append(("name_fraud_pt", f'"{name}" ({FRAUD_TERMS_PT})'))
    # Name without accents (catches different spellings)
    name_no_accent = _remove_accents(name)
    if name_no_accent != name:
        queries.append(("name_no_accent", f'"{name_no_accent}" ({FRAUD_TERMS_PT})'))
    # First + last name only (broader match for compound names)
    parts = name.strip().split()
    if len(parts) >= 3:
        short_name = f"{parts[0]} {parts[-1]}"
        queries.append(("short_name_fraud", f'"{short_name}" ({FRAUD_TERMS_PT})'))
    # English terms
    queries.append(("name_fraud_en", f'"{name}" ({FRAUD_TERMS_EN})'))
    # Nickname queries
    if nickname and nickname.strip():
        queries.append(("nickname_fraud_pt", f'"{nickname.strip()}" ({FRAUD_TERMS_PT})'))
    return queries


class NegativeMediaSource(BaseSource):
    source_name = "negative_media"
    timeout = 15.0

    async def collect(self, entity_id: str, entity_name: str, email=None, nickname=None, phone=None, **kwargs) -> dict:
        queries = _build_queries(entity_name, nickname)
        all_results: list[dict] = []
        seen_urls: set[str] = set()
        errors = []
        queries_run = []

        for label, query in queries:
            try:
                results = await self._ddg_search(query)
                queries_run.append(query)
                for r in results:
                    if r["url"] not in seen_urls:
                        all_results.append(r)
                        seen_urls.add(r["url"])
            except Exception as e:
                logger.warning(f"Search [{label}] failed: {e}")
                errors.append(f"{label}: {str(e)}")

        raw_score, alerts = self._compute_score(all_results)
        num = len(all_results)

        if num == 0:
            summary = "Nenhuma mídia negativa encontrada."
        elif num == 1:
            summary = "1 resultado de mídia negativa encontrado."
        else:
            summary = f"{num} resultados de mídia negativa encontrados."

        return self._make_result(
            raw_score=raw_score,
            summary=summary,
            alerts=alerts,
            data={
                "total_results": num,
                "results": all_results[:20],
                "queries_run": queries_run,
                "nickname_searched": bool(nickname),
                "errors": errors,
            },
        )

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
            async with httpx.AsyncClient(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
                resp = await client.post(DDG_URL, content=payload)
            if resp.status_code != 200:
                logger.warning(f"DDG returned {resp.status_code} for query: {query[:60]}")
                return []
            return self._parse_ddg_html(resp.text)
        except Exception as e:
            logger.exception(f"DuckDuckGo search error: {e}")
            return []

    def _parse_ddg_html(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        results = []
        for result_div in soup.select(".result"):
            title_el = result_div.select_one(".result__title a")
            snippet_el = result_div.select_one(".result__snippet")
            url_el = result_div.select_one(".result__url")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            url = title_el.get("href", "")
            display_url = url_el.get_text(strip=True) if url_el else ""
            if url.startswith("//duckduckgo.com/l/?"):
                url_match = re.search(r"uddg=([^&]+)", url)
                if url_match:
                    url = unquote(url_match.group(1))
            if title and url:
                results.append({"title": title, "snippet": snippet, "url": url, "display_url": display_url})
        return results

    def _compute_score(self, results: list[dict]) -> tuple[float, list]:
        num = len(results)
        if num == 0:
            return 0.0, []
        score = 30.0 if num <= 2 else 60.0 if num <= 5 else 90.0
        severity = "warning" if num <= 2 else "danger" if num <= 5 else "critical"
        alerts = [self._make_alert(severity, f"{num} resultado(s) de mídia negativa encontrado(s)")]

        serious_keywords = ["lavagem", "coaf", "preso", "condenado", "operação", "fraude", "golpe", "estelionato"]
        hits = set()
        for r in results:
            text = (r.get("title", "") + " " + r.get("snippet", "")).lower()
            for kw in serious_keywords:
                if kw in text:
                    hits.add(kw)
        if hits:
            alerts.append(self._make_alert(
                "critical" if score >= 60 else "danger",
                f"Termos críticos detectados: {', '.join(list(hits)[:4])}"
            ))
        return min(score, 100.0), alerts

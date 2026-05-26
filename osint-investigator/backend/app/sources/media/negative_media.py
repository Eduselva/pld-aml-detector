import logging
import re
from typing import Optional, Any
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from app.sources.base import BaseSource

logger = logging.getLogger(__name__)

DDG_URL = "https://html.duckduckgo.com/html/"

PT_TERMS = [
    "fraude",
    "lavagem de dinheiro",
    "COAF",
    "preso",
    "golpe",
    "estelionato",
    "operação policial",
    "corrupção",
    "desvio",
    "investigado",
]

EN_TERMS = [
    "fraud",
    "money laundering",
    "arrested",
    "corruption",
    "scam",
]


class NegativeMediaSource(BaseSource):
    source_name = "negative_media"
    timeout = 15.0

    async def collect(
        self,
        entity_id: str,
        entity_name: str,
        email: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        all_results: list[dict] = []
        errors = []

        # PT search
        try:
            pt_query = f'"{entity_name}" AND ({" OR ".join(PT_TERMS)})'
            pt_results = await self._ddg_search(pt_query)
            all_results.extend(pt_results)
        except Exception as e:
            logger.warning(f"PT media search failed: {e}")
            errors.append(str(e))

        # EN search
        try:
            en_query = f'"{entity_name}" AND ({" OR ".join(EN_TERMS)})'
            en_results = await self._ddg_search(en_query)
            existing_urls = {r["url"] for r in all_results}
            for r in en_results:
                if r["url"] not in existing_urls:
                    all_results.append(r)
                    existing_urls.add(r["url"])
        except Exception as e:
            logger.warning(f"EN media search failed: {e}")
            errors.append(str(e))

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
                "search_terms_pt": PT_TERMS,
                "search_terms_en": EN_TERMS,
                "errors": errors,
            },
        )

    async def _ddg_search(self, query: str) -> list[dict]:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = urlencode({"q": query, "b": "", "kl": "br-pt"})
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers=headers,
                follow_redirects=True,
            ) as client:
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
                    from urllib.parse import unquote
                    url = unquote(url_match.group(1))
            if title and url:
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "url": url,
                    "display_url": display_url,
                })
        return results

    def _compute_score(self, results: list[dict]) -> tuple[float, list]:
        alerts = []
        num = len(results)
        if num == 0:
            return 0.0, []
        elif num <= 2:
            score = 30.0
            alerts.append(self._make_alert("warning", f"{num} resultado(s) de mídia negativa encontrado(s)"))
        elif num <= 5:
            score = 60.0
            alerts.append(self._make_alert("danger", f"{num} resultados de mídia negativa encontrados"))
        else:
            score = 90.0
            alerts.append(self._make_alert("critical", f"{num} resultados de mídia negativa encontrados"))

        serious_keywords = ["lavagem", "coaf", "preso", "condenado", "operação", "fraude"]
        serious_hits = []
        for r in results:
            text = (r.get("title", "") + " " + r.get("snippet", "")).lower()
            for kw in serious_keywords:
                if kw in text:
                    serious_hits.append(kw)
                    break
        if serious_hits:
            unique_hits = list(set(serious_hits))[:3]
            alerts.append(self._make_alert(
                "critical" if score >= 60 else "danger",
                f"Termos críticos detectados: {', '.join(unique_hits)}"
            ))
        return min(score, 100.0), alerts

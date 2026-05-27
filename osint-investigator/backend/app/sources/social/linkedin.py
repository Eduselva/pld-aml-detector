import logging
from typing import Optional, Any
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from app.sources.base import BaseSource
from app.config import settings

logger = logging.getLogger(__name__)

DDG_URL = "https://html.duckduckgo.com/html/"
SERPER_URL = "https://google.serper.dev/search"


class LinkedInSource(BaseSource):
    source_name = "social_linkedin"
    timeout = 15.0

    async def collect(
        self,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        email: Optional[str] = None,
        nickname: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        # Build search terms: name and/or nickname
        terms = []
        if entity_name and entity_name.strip():
            terms.append(entity_name.strip())
        if nickname and nickname.strip() and nickname.strip() != entity_name:
            terms.append(nickname.strip())

        if not terms:
            return self._make_result(
                raw_score=0.0,
                summary="Sem nome ou apelido para buscar no LinkedIn.",
                alerts=[],
                data={"profiles": [], "total_found": 0},
            )

        profiles = []
        error = None

        try:
            if settings.serper_api_key:
                profiles = await self._serper_search_linkedin(terms)
            else:
                profiles = await self._ddg_search_linkedin(terms[0])
        except Exception as e:
            logger.exception(f"LinkedIn search failed: {e}")
            error = str(e)

        if profiles:
            summary = f"{len(profiles)} perfil(is) LinkedIn encontrado(s)"
            alerts = [self._make_alert("info", f"Perfil LinkedIn encontrado: {profiles[0].get('title', '')}")]
        else:
            summary = "Nenhum perfil LinkedIn encontrado"
            alerts = []

        return self._make_result(
            raw_score=0.0,
            summary=summary,
            alerts=alerts,
            data={
                "profiles": profiles[:5],
                "total_found": len(profiles),
                "error": error,
            },
        )

    async def _serper_search_linkedin(self, terms: list[str]) -> list[dict]:
        or_clause = " OR ".join(f'"{t}"' for t in terms)
        query = f"site:linkedin.com/in ({or_clause})"
        headers = {
            "X-API-KEY": settings.serper_api_key,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                SERPER_URL,
                json={"q": query, "gl": "br", "hl": "pt", "num": 10},
                headers=headers,
            )
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for item in data.get("organic", []):
            url = item.get("link", "")
            if "linkedin.com/in" in url:
                results.append({
                    "title": item.get("title", ""),
                    "url": url,
                    "snippet": item.get("snippet", ""),
                })
        return results

    async def _ddg_search_linkedin(self, entity_name: str) -> list[dict]:
        query = f'site:linkedin.com/in "{entity_name}"'
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = urlencode({"q": query, "b": "", "kl": "br-pt"})
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers, follow_redirects=True) as client:
            resp = await client.post(DDG_URL, content=payload)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for result_div in soup.select(".result"):
            title_el = result_div.select_one(".result__title a")
            snippet_el = result_div.select_one(".result__snippet")
            if not title_el:
                continue
            url = title_el.get("href", "")
            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            if "linkedin.com/in" in url:
                results.append({"title": title, "url": url, "snippet": snippet})
        return results

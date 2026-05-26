import logging
from typing import Optional, Any
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from app.sources.base import BaseSource
from app.sources.social.resolver import generate_candidate_usernames

logger = logging.getLogger(__name__)

DDG_URL = "https://html.duckduckgo.com/html/"


class LinkedInSource(BaseSource):
    source_name = "social_linkedin"
    timeout = 15.0

    async def collect(
        self,
        entity_id: str,
        entity_name: str,
        email: Optional[str] = None,
        nickname: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        profiles = []
        error = None

        try:
            profiles = await self._google_search_linkedin(entity_name)
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
            raw_score=0.0,  # LinkedIn presence is not inherently risky
            summary=summary,
            alerts=alerts,
            data={
                "profiles": profiles[:5],
                "total_found": len(profiles),
                "error": error,
            },
        )

    async def _google_search_linkedin(self, entity_name: str) -> list[dict]:
        query = f'site:linkedin.com/in "{entity_name}"'
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = urlencode({"q": query, "b": "", "kl": "br-pt"})

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=headers,
            follow_redirects=True,
        ) as client:
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
            if "linkedin.com/in" in url or "linkedin.com/in" in title.lower():
                results.append({"title": title, "url": url, "snippet": snippet})

        return results

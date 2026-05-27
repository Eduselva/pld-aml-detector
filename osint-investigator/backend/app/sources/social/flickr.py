import logging
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource
from app.sources.social.resolver import generate_candidate_usernames
from app.config import settings

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"


class FlickrSource(BaseSource):
    source_name = "social_flickr"
    timeout = 15.0

    async def collect(
        self,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        email: Optional[str] = None,
        nickname: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        terms = []
        if entity_name and entity_name.strip():
            terms.append(entity_name.strip())
        if nickname and nickname.strip() and nickname.strip() != entity_name:
            terms.append(nickname.strip())

        if not terms:
            return self._make_result(
                raw_score=0.0,
                summary="Sem nome ou apelido para buscar no Flickr.",
                alerts=[],
                data={"found_profiles": [], "total_found": 0},
            )

        profiles: list[dict] = []

        # Primary: direct URL check using candidate usernames
        candidates = generate_candidate_usernames(entity_name, email, nickname=nickname)
        if candidates:
            profiles = await self._direct_check(candidates[:6])

        # Fallback: Serper
        if not profiles and settings.serper_api_key:
            profiles = await self._serper_search(terms)

        if profiles:
            summary = f"{len(profiles)} perfil(is) Flickr encontrado(s)"
            alerts = [self._make_alert("info", f"Perfil Flickr encontrado: {profiles[0].get('username', '')}")]
        else:
            summary = "Nenhum perfil Flickr encontrado"
            alerts = []

        return self._make_result(
            raw_score=0.0,
            summary=summary,
            alerts=alerts,
            data={
                "found_profiles": profiles[:5],
                "total_found": len(profiles),
            },
        )

    async def _direct_check(self, candidates: list[str]) -> list[dict]:
        found = []
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
                    "Accept-Language": "pt-BR,pt;q=0.9",
                },
                follow_redirects=True,
            ) as client:
                for username in candidates:
                    url = f"https://www.flickr.com/photos/{username}/"
                    try:
                        resp = await client.get(url)
                        if resp.status_code == 200 and username.lower() in resp.text.lower():
                            found.append({
                                "username": username,
                                "url": url,
                                "platform": "Flickr",
                            })
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Flickr direct check failed: {e}")
        return found

    async def _serper_search(self, terms: list[str]) -> list[dict]:
        or_clause = " OR ".join(f'"{t}"' for t in terms)
        query = f'site:flickr.com/photos ({or_clause})'
        headers = {
            "X-API-KEY": settings.serper_api_key,
            "Content-Type": "application/json",
        }
        try:
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
                if "flickr.com" in url:
                    path_parts = [p for p in url.rstrip("/").split("/") if p]
                    username = path_parts[-1] if path_parts else ""
                    results.append({
                        "username": username,
                        "url": url,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "platform": "Flickr",
                    })
            return results
        except Exception as e:
            logger.debug(f"Flickr Serper search failed: {e}")
            return []

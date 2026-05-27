import logging
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource
from app.config import settings

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"


class FacebookSource(BaseSource):
    source_name = "social_facebook"
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
                summary="Sem nome ou apelido para buscar no Facebook.",
                alerts=[],
                data={"found_profiles": [], "total_found": 0},
            )

        if not settings.serper_api_key:
            return self._make_result(
                raw_score=0.0,
                summary="Busca Facebook indisponível — configure SERPER_API_KEY.",
                alerts=[],
                data={"found_profiles": [], "total_found": 0},
            )

        profiles = await self._serper_search(terms)

        if profiles:
            summary = f"{len(profiles)} perfil(is) Facebook encontrado(s)"
            alerts = [self._make_alert("info", f"Perfil Facebook encontrado: {profiles[0].get('title', '')}")]
        else:
            summary = "Nenhum perfil Facebook encontrado"
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

    async def _serper_search(self, terms: list[str]) -> list[dict]:
        or_clause = " OR ".join(f'"{t}"' for t in terms)
        query = f"site:facebook.com ({or_clause})"
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
                if "facebook.com" in url:
                    results.append({
                        "username": url.rstrip("/").split("/")[-1],
                        "url": url,
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "platform": "Facebook",
                    })
            return results
        except Exception as e:
            logger.debug(f"Facebook Serper search failed: {e}")
            return []

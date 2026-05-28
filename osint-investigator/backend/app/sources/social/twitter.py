import logging
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource
from app.sources.social.resolver import generate_candidate_usernames
from app.config import settings

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"


class TwitterSource(BaseSource):
    source_name = "social_twitter"
    timeout = 15.0

    async def collect(
        self,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        email: Optional[str] = None,
        nickname: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        candidates = generate_candidate_usernames(entity_name, email, nickname=nickname)
        found_profiles = []
        checked = []
        error = None

        try:
            if settings.serper_api_key:
                found_profiles, checked = await self._serper_search(
                    candidates[:3], entity_name or nickname or ""
                )
            else:
                found_profiles, checked = await self._url_check(candidates[:2])
        except Exception as e:
            logger.exception(f"Twitter check failed: {e}")
            error = str(e)

        if found_profiles:
            summary = f"{len(found_profiles)} perfil(is) Twitter/X encontrado(s)"
            alerts = [self._make_alert("info", f"Perfil Twitter/X encontrado: @{found_profiles[0]['username']}")]
        else:
            summary = "Nenhum perfil Twitter/X encontrado"
            alerts = []

        return self._make_result(
            raw_score=0.0,
            summary=summary,
            alerts=alerts,
            data={
                "found_profiles": found_profiles,
                "candidates_checked": checked,
                "error": error,
            },
        )

    async def _serper_search(
        self, candidates: list[str], entity_name: str
    ) -> tuple[list[dict], list[dict]]:
        """Search via Serper; accept profile only if snippet/title contains the name."""
        found: list[dict] = []
        checked: list[dict] = []
        name_parts = [p.lower() for p in entity_name.split() if len(p) > 2]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for username in candidates:
                query = f'site:twitter.com/{username} OR site:x.com/{username} "{entity_name}"'
                try:
                    resp = await client.post(
                        SERPER_URL,
                        json={"q": query, "gl": "br", "hl": "pt", "num": 3},
                        headers={
                            "X-API-KEY": settings.serper_api_key,
                            "Content-Type": "application/json",
                        },
                    )
                    if resp.status_code != 200:
                        checked.append({"username": username, "status": resp.status_code})
                        continue

                    data = resp.json()
                    organic = data.get("organic", [])
                    matched = False
                    for item in organic:
                        url = item.get("link", "").lower()
                        title = item.get("title", "").lower()
                        snippet = item.get("snippet", "").lower()
                        text = title + " " + snippet

                        username_lower = username.lower()
                        if (
                            f"twitter.com/{username_lower}" not in url
                            and f"x.com/{username_lower}" not in url
                        ):
                            continue
                        if any(part in text for part in name_parts):
                            found.append({
                                "username": username,
                                "url": f"https://twitter.com/{username}",
                                "x_url": f"https://x.com/{username}",
                                "platform": "Twitter/X",
                                "title": item.get("title", ""),
                                "snippet": item.get("snippet", ""),
                            })
                            matched = True
                            break

                    checked.append({"username": username, "status": "serper", "matched": matched})
                except Exception as e:
                    checked.append({"username": username, "status": "error", "error": str(e)})

        return found, checked

    async def _url_check(self, candidates: list[str]) -> tuple[list[dict], list[dict]]:
        """Fallback: direct HTTP check (top 2 candidates only)."""
        found: list[dict] = []
        checked: list[dict] = []
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
            },
            follow_redirects=True,
        ) as client:
            for username in candidates:
                url = f"https://x.com/{username}"
                try:
                    resp = await client.get(url)
                    exists = resp.status_code == 200 and "This account doesn" not in resp.text
                    checked.append({"username": username, "status": resp.status_code})
                    if exists:
                        found.append({
                            "username": username,
                            "url": f"https://twitter.com/{username}",
                            "x_url": url,
                            "platform": "Twitter/X",
                        })
                except Exception as e:
                    checked.append({"username": username, "status": "error", "error": str(e)})
        return found, checked

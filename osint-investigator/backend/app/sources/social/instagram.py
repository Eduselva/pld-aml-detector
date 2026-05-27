import logging
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource
from app.sources.social.resolver import generate_candidate_usernames

logger = logging.getLogger(__name__)


class InstagramSource(BaseSource):
    source_name = "social_instagram"
    timeout = 10.0

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
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                    "Accept-Language": "pt-BR,pt;q=0.9",
                },
                follow_redirects=False,
            ) as client:
                for username in candidates[:5]:
                    url = f"https://www.instagram.com/{username}/"
                    try:
                        resp = await client.get(url)
                        exists = resp.status_code == 200
                        checked.append({"username": username, "status": resp.status_code})
                        if exists:
                            found_profiles.append({
                                "username": username,
                                "url": url,
                                "platform": "Instagram",
                            })
                    except Exception as e:
                        checked.append({"username": username, "status": "error", "error": str(e)})
        except Exception as e:
            logger.exception(f"Instagram check failed: {e}")
            error = str(e)

        if found_profiles:
            summary = f"{len(found_profiles)} perfil(is) Instagram encontrado(s)"
            alerts = [self._make_alert("info", f"Perfil Instagram encontrado: @{found_profiles[0]['username']}")]
        else:
            summary = "Nenhum perfil Instagram encontrado"
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

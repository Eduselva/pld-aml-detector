import logging
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource
from app.sources.social.resolver import generate_candidate_usernames

logger = logging.getLogger(__name__)


class TwitterSource(BaseSource):
    source_name = "social_twitter"
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
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
                    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
                },
                follow_redirects=True,
            ) as client:
                for username in candidates[:5]:
                    # Check both twitter.com and x.com
                    url = f"https://x.com/{username}"
                    try:
                        resp = await client.get(url)
                        exists = resp.status_code == 200 and "This account doesn" not in resp.text
                        checked.append({"username": username, "status": resp.status_code})
                        if exists:
                            found_profiles.append({
                                "username": username,
                                "url": f"https://twitter.com/{username}",
                                "x_url": url,
                                "platform": "Twitter/X",
                            })
                    except Exception as e:
                        checked.append({"username": username, "status": "error", "error": str(e)})
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

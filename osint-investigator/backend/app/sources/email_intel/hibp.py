import logging
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource
from app.config import settings

logger = logging.getLogger(__name__)

HIBP_BASE = "https://haveibeenpwned.com/api/v3"


class HIBPSource(BaseSource):
    source_name = "hibp"
    timeout = 10.0

    async def collect(
        self,
        entity_id: str,
        entity_name: str,
        email: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        if not email:
            return self._make_result(
                raw_score=0.0,
                summary="E-mail não fornecido.",
                alerts=[],
                data={"skipped": True},
            )

        breaches = []
        error = None

        try:
            breaches = await self._check_breaches(email)
        except Exception as e:
            logger.exception(f"HIBP check failed for {email}: {e}")
            error = str(e)

        raw_score, alerts = self._compute_score(breaches)

        num = len(breaches)
        if error:
            summary = f"Erro ao verificar e-mail no HIBP: {error}"
        elif num == 0:
            summary = f"E-mail {email} não encontrado em vazamentos conhecidos."
        elif num == 1:
            summary = f"E-mail {email} encontrado em 1 vazamento de dados."
        else:
            summary = f"E-mail {email} encontrado em {num} vazamentos de dados."

        return self._make_result(
            raw_score=raw_score,
            summary=summary,
            alerts=alerts,
            data={
                "email": email,
                "total_breaches": num,
                "breaches": breaches[:30],
                "error": error,
            },
        )

    async def _check_breaches(self, email: str) -> list[dict]:
        headers = {
            "User-Agent": "OSINTInvestigator/1.0",
            "Accept": "application/json",
        }
        if settings.hibp_api_key:
            headers["hibp-api-key"] = settings.hibp_api_key

        url = f"{HIBP_BASE}/breachedaccount/{email}?truncateResponse=false"

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers=headers,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)

        if resp.status_code == 404:
            return []  # Not found in any breach
        if resp.status_code == 401:
            logger.warning("HIBP API key required but not configured")
            return []
        if resp.status_code == 429:
            logger.warning("HIBP rate limit hit")
            return []
        if resp.status_code != 200:
            logger.warning(f"HIBP returned {resp.status_code}")
            return []

        data = resp.json()
        return [
            {
                "name": b.get("Name", ""),
                "title": b.get("Title", ""),
                "breach_date": b.get("BreachDate", ""),
                "pwn_count": b.get("PwnCount", 0),
                "description": b.get("Description", "")[:300],
                "data_classes": b.get("DataClasses", []),
                "is_sensitive": b.get("IsSensitive", False),
                "is_verified": b.get("IsVerified", False),
            }
            for b in data
        ]

    def _compute_score(self, breaches: list[dict]) -> tuple[float, list]:
        alerts = []
        num = len(breaches)
        if num == 0:
            return 0.0, []
        elif num <= 2:
            score = 30.0
            alerts.append(self._make_alert("warning", f"E-mail encontrado em {num} vazamento(s) de dados"))
        else:
            score = 70.0
            alerts.append(self._make_alert("danger", f"E-mail encontrado em {num} vazamentos de dados"))

        sensitive = [b for b in breaches if b.get("is_sensitive")]
        if sensitive:
            alerts.append(self._make_alert("danger", f"{len(sensitive)} vazamento(s) sensível(is) detectado(s)"))
            score = min(score + 15, 100)

        # Check if passwords were leaked
        password_breaches = [
            b for b in breaches
            if "Passwords" in b.get("data_classes", [])
        ]
        if password_breaches:
            alerts.append(self._make_alert("warning", f"Senha(s) comprometida(s) em {len(password_breaches)} vazamento(s)"))

        return score, alerts

"""
QSA Search — finds companies where the investigated person is a partner/owner.

Primary:   brasil.io socios dataset (Receita Federal open data, free)
Secondary: Serper web search for company association mentions
"""
import logging
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource
from app.config import settings

logger = logging.getLogger(__name__)

BRASILIO_URL = "https://brasil.io/api/dataset/socios-brasil/socios/data/"
BRASILAPI_CNPJ_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
SERPER_URL = "https://google.serper.dev/search"

CNPJ_RE = re.compile(r"\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[\/\s]?\d{4}[-\s]?\d{2}")


def _cnpj_detail_url(cnpj: str) -> str:
    """Return a public, human-readable CNPJ lookup URL."""
    d = re.sub(r"\D", "", cnpj)
    # econodata.com.br accepts raw 14-digit CNPJ and shows full company details
    return f"https://www.econodata.com.br/empresas/{d}"

# High-risk CNAE codes (narcotráfico, cambistas, etc.) — very basic list
HIGH_RISK_CNAES = {"6492", "6499", "6611", "6619", "6622", "6629", "6810", "6820"}


def _normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    cleaned = "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()
    return " ".join(cleaned.replace(",", " ").split())


def _fuzzy(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _best_score(query: str, entry: str) -> float:
    direct = _fuzzy(query, entry)
    q_sorted = " ".join(sorted(query.split()))
    e_sorted = " ".join(sorted(entry.split()))
    token_sort = _fuzzy(q_sorted, e_sorted)
    substring = 0.90 if (query in entry or entry in query) else 0.0
    q_tokens = set(query.split())
    e_tokens = set(entry.split())
    token_subset = 0.88 if (q_tokens and q_tokens.issubset(e_tokens)) else 0.0
    return max(direct, token_sort, substring, token_subset)


class QSASearchSource(BaseSource):
    source_name = "qsa_search"
    timeout = 15.0

    async def collect(
        self,
        entity_id: Optional[str],
        entity_name: Optional[str] = None,
        nickname: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        search_terms = []
        if entity_name and entity_name.strip():
            search_terms.append(entity_name.strip())
        if nickname and nickname.strip() and nickname.strip() != entity_name:
            search_terms.append(nickname.strip())

        if not search_terms:
            return self._make_result(
                raw_score=0.0,
                summary="Sem nome ou apelido para buscar vínculos societários.",
                alerts=[],
                data={"companies": [], "total": 0, "source": "none"},
            )

        companies: list[dict] = []
        source_used = "none"

        # ── 1. Brasil.io QSA dataset ──────────────────────────────────────────
        for term in search_terms:
            results = await self._brasilio_search(term)
            if results is not None:
                source_used = "brasil.io"
                for item in results:
                    entry_norm = _normalize(item.get("nome_socio", ""))
                    term_norm = _normalize(term)
                    score = _best_score(term_norm, entry_norm)
                    if score >= 0.80:
                        cnpj = item.get("cnpj", "")
                        if not any(c["cnpj"] == cnpj for c in companies):
                            companies.append({
                                "cnpj": cnpj,
                                "razao_social": item.get("razao_social", ""),
                                "nome_socio_encontrado": item.get("nome_socio", ""),
                                "qualificacao": item.get("qualificacao_socio", ""),
                                "data_entrada": item.get("data_entrada_sociedade", ""),
                                "situacao": None,  # enriched below
                                "match_score": round(score, 3),
                                "detail_url": _cnpj_detail_url(cnpj),
                            })
                if companies:
                    break

        # ── 2. Serper fallback (or complement when brasil.io returns nothing) ─
        if not companies and settings.serper_api_key:
            serper_companies = await self._serper_qsa_search(search_terms)
            if serper_companies:
                source_used = "serper"
                companies = serper_companies

        # ── 3. Enrich top companies with status from BrasilAPI ────────────────
        for company in companies[:5]:
            cnpj = company.get("cnpj", "")
            if cnpj and not company.get("situacao"):
                status = await self._fetch_cnpj_status(cnpj)
                if status:
                    company["situacao"] = status

        # Safety net: every company must have a consultation link
        for company in companies:
            if not company.get("detail_url") and company.get("cnpj"):
                company["detail_url"] = _cnpj_detail_url(company["cnpj"])

        raw_score, alerts = self._compute_score(companies)
        total = len(companies)
        summary = (
            "Nenhum vínculo societário encontrado."
            if total == 0
            else f"{total} empresa(s) com vínculo societário identificada(s)."
        )

        return self._make_result(
            raw_score=raw_score,
            summary=summary,
            alerts=alerts,
            data={
                "companies": companies[:20],
                "total": total,
                "source": source_used,
                "terms_searched": search_terms,
            },
        )

    async def _brasilio_search(self, name: str) -> list[dict] | None:
        headers = {"User-Agent": "OSINTInvestigator/1.0"}
        brasilio_token = getattr(settings, "brasilio_token", "")
        if brasilio_token:
            headers["Authorization"] = f"Token {brasilio_token}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    BRASILIO_URL,
                    params={"search": name, "format": "json"},
                    headers=headers,
                )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
            if resp.status_code in (429, 401, 403):
                logger.warning(f"brasil.io QSA: HTTP {resp.status_code} para '{name}'")
                return None
            logger.debug(f"brasil.io QSA: HTTP {resp.status_code}")
            return None
        except Exception as e:
            logger.debug(f"brasil.io QSA falhou: {e}")
            return None

    async def _serper_qsa_search(self, terms: list[str]) -> list[dict]:
        companies = []
        seen_cnpjs: set[str] = set()
        headers = {
            "X-API-KEY": settings.serper_api_key,
            "Content-Type": "application/json",
        }
        for term in terms[:2]:
            query = f'"{term}" sócio empresa CNPJ site:cnpj.info OR site:consulta.cnpj.net OR site:econodata.com.br OR site:empresas.net.br'
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        SERPER_URL,
                        json={"q": query, "gl": "br", "hl": "pt", "num": 10},
                        headers=headers,
                    )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for item in data.get("organic", []):
                    snippet = item.get("snippet", "") + " " + item.get("title", "")
                    for match in CNPJ_RE.findall(snippet):
                        cnpj_clean = re.sub(r"\D", "", match)
                        if len(cnpj_clean) == 14 and cnpj_clean not in seen_cnpjs:
                            seen_cnpjs.add(cnpj_clean)
                            companies.append({
                                "cnpj": cnpj_clean,
                                "razao_social": item.get("title", ""),
                                "nome_socio_encontrado": term,
                                "qualificacao": "",
                                "data_entrada": "",
                                "situacao": None,
                                "match_score": 0.0,
                                "source_url": item.get("link", ""),
                                "detail_url": _cnpj_detail_url(cnpj_clean),
                            })
            except Exception as e:
                logger.debug(f"Serper QSA falhou: {e}")
        return companies

    async def _fetch_cnpj_status(self, cnpj: str) -> str | None:
        try:
            async with httpx.AsyncClient(
                timeout=8.0,
                headers={"User-Agent": "Mozilla/5.0 (compatible; OSINTInvestigator/1.0)"},
                follow_redirects=True,
            ) as client:
                resp = await client.get(BRASILAPI_CNPJ_URL.format(cnpj=cnpj))
            if resp.status_code == 200:
                data = resp.json()
                return data.get("descricao_situacao_cadastral", "")
        except Exception:
            pass
        return None

    def _compute_score(self, companies: list[dict]) -> tuple[float, list]:
        if not companies:
            return 0.0, []

        alerts = []
        score = 0.0

        total = len(companies)
        if total >= 10:
            score = 60.0
            alerts.append(self._make_alert("danger", f"Pessoa vinculada a {total} empresas — perfil atípico"))
        elif total >= 5:
            score = 30.0
            alerts.append(self._make_alert("warning", f"Pessoa vinculada a {total} empresas"))
        else:
            score = 10.0

        irregular = [
            c for c in companies
            if c.get("situacao") and any(
                s in (c["situacao"] or "").upper()
                for s in ("INAPTA", "BAIXADA", "SUSPENSA", "NULA")
            )
        ]
        if irregular:
            score = min(score + 30, 100)
            alerts.append(self._make_alert(
                "critical" if len(irregular) >= 2 else "danger",
                f"{len(irregular)} empresa(s) com situação irregular: "
                + ", ".join(c["razao_social"] or c["cnpj"] for c in irregular[:3])
            ))

        return min(score, 100.0), alerts

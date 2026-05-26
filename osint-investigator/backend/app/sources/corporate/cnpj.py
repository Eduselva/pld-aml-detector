import logging
from datetime import datetime, date
from typing import Optional, Any

import httpx

from app.sources.base import BaseSource

logger = logging.getLogger(__name__)

BRASILA_CNPJ_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

RISKY_STATUSES = {"BAIXADA", "SUSPENSA", "INAPTA", "NULA"}


class CNPJSource(BaseSource):
    source_name = "cnpj"
    timeout = 10.0

    async def collect(
        self,
        entity_id: str,
        entity_name: str,
        email: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        cnpj = entity_id.replace(".", "").replace("/", "").replace("-", "")

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0 (compatible; OSINTInvestigator/1.0)"},
                follow_redirects=True,
            ) as client:
                resp = await client.get(BRASILA_CNPJ_URL.format(cnpj=cnpj))

            if resp.status_code == 404:
                return self._make_result(
                    raw_score=30.0,
                    summary="CNPJ não encontrado na base da Receita Federal.",
                    alerts=[self._make_alert("warning", "CNPJ não localizado na base da Receita Federal")],
                    data={"error": "CNPJ não encontrado"},
                )
            if resp.status_code != 200:
                return self._make_result(
                    raw_score=0.0,
                    summary=f"Erro ao consultar CNPJ (HTTP {resp.status_code}).",
                    alerts=[],
                    data={"error": f"HTTP {resp.status_code}"},
                )

            data = resp.json()
        except Exception as e:
            logger.exception(f"Erro ao consultar CNPJ {cnpj}: {e}")
            return self._make_result(
                raw_score=0.0,
                summary=f"Falha na consulta CNPJ: {e}",
                alerts=[],
                data={"error": str(e)},
            )

        raw_score, alerts = self._compute_score(data)

        company_name = data.get("razao_social", entity_name)
        status = data.get("descricao_situacao_cadastral", "Desconhecida")
        summary = f"{company_name} — Situação: {status}"

        partners = data.get("qsa", []) or []
        partner_names = [p.get("nome_socio", "") for p in partners if p.get("nome_socio")]

        opening_date_str = data.get("data_inicio_atividade", "")
        is_recently_opened = False
        if opening_date_str:
            try:
                opening_date = datetime.strptime(opening_date_str, "%Y-%m-%d").date()
                months_old = (date.today() - opening_date).days / 30
                if months_old < 24:
                    is_recently_opened = True
                    if months_old < 6:
                        alerts.append(self._make_alert("warning", f"Empresa aberta há menos de 6 meses ({opening_date_str})"))
                    else:
                        alerts.append(self._make_alert("info", f"Empresa relativamente nova — aberta em {opening_date_str}"))
            except ValueError:
                pass

        activities = data.get("cnae_fiscal_descricao", "")
        secondary_activities = [
            a.get("descricao", "") for a in (data.get("cnaes_secundarios") or [])
        ]

        return self._make_result(
            raw_score=raw_score,
            summary=summary,
            alerts=alerts,
            data={
                "razao_social": company_name,
                "nome_fantasia": data.get("nome_fantasia", ""),
                "cnpj": cnpj,
                "situacao_cadastral": status,
                "data_situacao_cadastral": data.get("data_situacao_cadastral", ""),
                "motivo_situacao_cadastral": data.get("descricao_motivo_situacao_cadastral", ""),
                "data_inicio_atividade": opening_date_str,
                "is_recently_opened": is_recently_opened,
                "atividade_principal": activities,
                "atividades_secundarias": secondary_activities[:5],
                "natureza_juridica": data.get("descricao_natureza_juridica", ""),
                "capital_social": data.get("capital_social", 0),
                "porte": data.get("descricao_porte", ""),
                "municipio": data.get("municipio", ""),
                "uf": data.get("uf", ""),
                "socios": [
                    {
                        "nome": p.get("nome_socio", ""),
                        "qualificacao": p.get("qualificacao_socio", ""),
                        "pais_origem": p.get("pais_origem", ""),
                    }
                    for p in partners
                ],
                "partner_names": partner_names,
                "num_socios": len(partners),
            },
        )

    def _compute_score(self, data: dict) -> tuple[float, list]:
        alerts = []
        score = 0.0

        status_code = str(data.get("codigo_situacao_cadastral", "2"))
        status_desc = data.get("descricao_situacao_cadastral", "ATIVA").upper()

        if "INAPTA" in status_desc:
            score = 80.0
            alerts.append(self._make_alert("critical", f"Empresa INAPTA: {status_desc}"))
        elif any(s in status_desc for s in ("BAIXADA", "SUSPENSA", "NULA")):
            score = 40.0
            alerts.append(self._make_alert("danger", f"Empresa com situação irregular: {status_desc}"))
        elif "ATIVA" in status_desc:
            score = 0.0
        else:
            score = 20.0
            alerts.append(self._make_alert("info", f"Situação cadastral: {status_desc}"))

        # Capital social muito baixo pode ser sinal de empresa de fachada
        capital = data.get("capital_social", 0) or 0
        if 0 < capital < 1000:
            score = min(score + 10, 100)
            alerts.append(self._make_alert("info", f"Capital social muito baixo: R$ {capital:.2f}"))

        # Muitos sócios pode ser sinal
        partners = data.get("qsa", []) or []
        if len(partners) > 10:
            score = min(score + 10, 100)
            alerts.append(self._make_alert("info", f"Empresa possui {len(partners)} sócios"))

        # Sócio estrangeiro
        foreign_partners = [p for p in partners if p.get("pais_origem") and p.get("pais_origem") != "Brasil"]
        if foreign_partners:
            alerts.append(self._make_alert("info", f"{len(foreign_partners)} sócio(s) de origem estrangeira"))

        return score, alerts

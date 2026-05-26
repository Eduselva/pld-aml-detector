import csv
import logging
import os
import unicodedata
from difflib import SequenceMatcher
from typing import Optional, Any

from app.sources.base import BaseSource
from app.config import settings

logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.85


def normalize_name(name: str) -> str:
    """Remove accents and lowercase."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return ascii_str.lower().strip()


def fuzzy_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


class RestrictiveListsSource(BaseSource):
    source_name = "restrictive_lists"
    timeout = 5.0

    def __init__(self):
        self._pep_list: list[dict] = []
        self._ofac_list: list[dict] = []
        self._loaded = False

    def _load_lists(self):
        if self._loaded:
            return
        data_dir = getattr(settings, "data_dir", "/app/data")
        pep_path = os.path.join(data_dir, "pep_sample.csv")
        ofac_path = os.path.join(data_dir, "ofac_sample.csv")

        # Fallback to relative path for local dev
        if not os.path.exists(pep_path):
            local_data = os.path.join(os.path.dirname(__file__), "../../../../data")
            pep_path = os.path.join(local_data, "pep_sample.csv")
            ofac_path = os.path.join(local_data, "ofac_sample.csv")

        try:
            with open(pep_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self._pep_list = list(reader)
        except FileNotFoundError:
            logger.warning(f"PEP list not found at {pep_path}")
            self._pep_list = []

        try:
            with open(ofac_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self._ofac_list = list(reader)
        except FileNotFoundError:
            logger.warning(f"OFAC list not found at {ofac_path}")
            self._ofac_list = []

        self._loaded = True

    async def collect(
        self,
        entity_id: str,
        entity_name: str,
        email: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        self._load_lists()
        normalized_name = normalize_name(entity_name)

        matches = []
        alerts = []

        # Check PEP list
        for entry in self._pep_list:
            entry_name = normalize_name(entry.get("name", ""))
            ratio = fuzzy_ratio(normalized_name, entry_name)
            if ratio >= MATCH_THRESHOLD:
                match_type = "exato" if ratio >= 0.98 else "fuzzy"
                matches.append({
                    "list": "PEP",
                    "name": entry.get("name", ""),
                    "reason": entry.get("reason", ""),
                    "role": entry.get("role", ""),
                    "cpf_partial": entry.get("cpf_partial", ""),
                    "match_score": round(ratio, 3),
                    "match_type": match_type,
                })
                severity = "critical" if ratio >= 0.98 else "danger"
                alerts.append(self._make_alert(
                    severity,
                    f"Possível PEP ({match_type}): {entry.get('name')} — {entry.get('role', '')} ({entry.get('reason', '')})"
                ))

        # Check OFAC/SDN list
        for entry in self._ofac_list:
            entry_name = normalize_name(entry.get("name", ""))
            ratio = fuzzy_ratio(normalized_name, entry_name)
            if ratio >= MATCH_THRESHOLD:
                match_type = "exato" if ratio >= 0.98 else "fuzzy"
                matches.append({
                    "list": entry.get("list", "OFAC"),
                    "name": entry.get("name", ""),
                    "nationality": entry.get("nationality", ""),
                    "reason": entry.get("reason", ""),
                    "match_score": round(ratio, 3),
                    "match_type": match_type,
                })
                alerts.append(self._make_alert(
                    "critical",
                    f"Correspondência em lista restritiva ({entry.get('list', 'OFAC')}): {entry.get('name')} — {entry.get('reason', '')}"
                ))

        raw_score = self._compute_score(matches)

        if not matches:
            summary = "Nenhuma correspondência em listas restritivas (PEP/OFAC)."
        else:
            summary = f"{len(matches)} correspondência(s) em listas restritivas: " + ", ".join(
                m["list"] for m in matches
            )

        return self._make_result(
            raw_score=raw_score,
            summary=summary,
            alerts=alerts,
            data={
                "matches": matches,
                "total_matches": len(matches),
                "lists_checked": ["PEP", "OFAC/SDN", "COAF", "ONU"],
                "pep_entries_checked": len(self._pep_list),
                "ofac_entries_checked": len(self._ofac_list),
            },
        )

    def _compute_score(self, matches: list[dict]) -> float:
        if not matches:
            return 0.0
        max_score = max(m["match_score"] for m in matches)
        if max_score >= 0.98:
            return 100.0
        return 70.0

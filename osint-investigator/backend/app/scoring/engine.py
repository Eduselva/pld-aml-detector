WEIGHTS = {
    "corporate": 0.15,
    "media": 0.25,
    "lists": 0.15,
    "government": 0.20,
    "legal": 0.10,
    "social": 0.10,
    "email": 0.05,
}

SOURCE_CATEGORY_MAP = {
    "cnpj": "corporate",
    "qsa_search": "corporate",
    "negative_media": "media",
    "gazettes": "media",
    "restrictive_lists": "lists",
    "transparency_gov": "government",
    "court_records": "legal",
    "social_linkedin": "social",
    "social_instagram": "social",
    "social_twitter": "social",
    "social_tiktok": "social",
    "social_facebook": "social",
    "social_pinterest": "social",
    "social_flickr": "social",
    "hibp": "email",
}


class ScoringEngine:
    def compute_final_score(self, source_scores: dict) -> tuple:
        """
        Compute weighted final risk score from individual source scores.

        source_scores: dict mapping source_name -> raw_score (0-100)
        Returns: (total_score, risk_level)
        """
        category_scores = {cat: [] for cat in WEIGHTS}

        for source_name, score in source_scores.items():
            category = SOURCE_CATEGORY_MAP.get(source_name)
            if category:
                category_scores[category].append(float(score))

        aggregated = {
            cat: max(scores) if scores else 0.0
            for cat, scores in category_scores.items()
        }

        total = sum(
            aggregated.get(cat, 0.0) * weight
            for cat, weight in WEIGHTS.items()
        )
        total = min(max(total, 0.0), 100.0)

        # Government sanctions always push to at least "high"
        if aggregated.get("government", 0.0) >= 90.0:
            total = max(total, 51.0)
        # Exact match on restrictive lists (PEP/OFAC) is always at least "high"
        if aggregated.get("lists", 0.0) >= 100.0:
            total = max(total, 51.0)
        # Fuzzy match on lists is always at least "medium"
        elif aggregated.get("lists", 0.0) >= 70.0:
            total = max(total, 26.0)

        risk_level = self._score_to_level(total)
        return round(total, 2), risk_level

    def _score_to_level(self, score: float) -> str:
        if score <= 25:
            return "low"
        elif score <= 50:
            return "medium"
        elif score <= 75:
            return "high"
        else:
            return "critical"

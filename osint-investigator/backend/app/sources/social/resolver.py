import re
import unicodedata
from typing import Optional


def normalize_part(s: str) -> str:
    """Remove accents and non-alpha chars, lowercase."""
    nfkd = unicodedata.normalize("NFKD", s)
    ascii_str = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", ascii_str.lower())


def extract_username_from_email(email: str) -> Optional[str]:
    """Extract the local part of an email."""
    if "@" in email:
        local = email.split("@")[0]
        return local.lower()
    return None


def generate_candidate_usernames(
    entity_name: Optional[str] = None,
    email: Optional[str] = None,
    nickname: Optional[str] = None,
) -> list[str]:
    """
    Generate a ranked list of candidate usernames from name, email, and nickname.
    Nickname candidates are prioritised (placed near the top) since people
    often register under their known alias rather than their legal name.
    """
    candidates: list[str] = []

    # 1. Email-derived username — highest signal when present
    if email:
        email_user = extract_username_from_email(email)
        if email_user:
            candidates.append(email_user)

    # 2. Nickname variants — prioritised over legal name
    if nickname and nickname.strip():
        nick = nickname.strip()
        nick_norm = normalize_part(nick)
        nick_lower = nick.lower().replace(" ", "")
        nick_dot = nick.lower().replace(" ", ".")
        nick_under = nick.lower().replace(" ", "_")
        for nc in [nick_norm, nick_lower, nick_dot, nick_under]:
            if nc and nc not in candidates:
                candidates.append(nc)

    # 3. Legal name variants
    if entity_name and entity_name.strip():
        parts = entity_name.strip().split()
        normalized_parts = [normalize_part(p) for p in parts if normalize_part(p)]
        if normalized_parts:
            first = normalized_parts[0]
            last = normalized_parts[-1] if len(normalized_parts) > 1 else ""
            middle_parts = normalized_parts[1:-1] if len(normalized_parts) > 2 else []

            if first and last:
                for variant in [
                    f"{first}.{last}",    # joao.silva
                    f"{first}{last}",      # joaosilva
                    f"{first}_{last}",     # joao_silva
                    f"{first[0]}{last}",   # jsilva
                    f"{last}.{first}",     # silva.joao
                    f"{last}{first}",      # silvajoao
                    f"{first[0]}.{last}",  # j.silva
                    f"{first}{last[0]}",   # joaos
                    f"{last}_{first}",     # silva_joao
                ]:
                    if variant not in candidates:
                        candidates.append(variant)

                if middle_parts:
                    mid = middle_parts[0][0] if middle_parts[0] else ""
                    if mid:
                        variant = f"{first}{mid}{last}"
                        if variant not in candidates:
                            candidates.append(variant)
            elif first:
                if first not in candidates:
                    candidates.append(first)

    # Deduplicate preserving order
    seen: set[str] = set()
    result = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            result.append(c)

    return result[:10]

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
    entity_name: str,
    email: Optional[str] = None,
    nickname: Optional[str] = None,
) -> list[str]:
    """
    Generate a ranked list of candidate usernames from name and email.
    """
    parts = entity_name.strip().split()
    if not parts:
        return []

    normalized_parts = [normalize_part(p) for p in parts if normalize_part(p)]
    if not normalized_parts:
        return []

    candidates: list[str] = []

    first = normalized_parts[0]
    last = normalized_parts[-1] if len(normalized_parts) > 1 else ""
    middle_parts = normalized_parts[1:-1] if len(normalized_parts) > 2 else []

    if first and last:
        candidates.append(f"{first}.{last}")         # joao.silva
        candidates.append(f"{first}{last}")           # joaosilva
        candidates.append(f"{first}_{last}")          # joao_silva
        candidates.append(f"{first[0]}{last}")        # jsilva
        candidates.append(f"{first}{last[0]}")        # joaos
        candidates.append(f"{last}.{first}")          # silva.joao
        candidates.append(f"{last}{first}")           # silvajoao
        candidates.append(f"{last}_{first}")          # silva_joao
        candidates.append(f"{first[0]}.{last}")       # j.silva

    if first and not last:
        candidates.append(first)

    if middle_parts and first and last:
        mid_initial = middle_parts[0][0] if middle_parts[0] else ""
        if mid_initial:
            candidates.append(f"{first}{mid_initial}{last}")   # joaomsilva

    # From nickname
    if nickname and nickname.strip():
        nick = nickname.strip()
        nick_lower = nick.lower().replace(" ", "")
        nick_dot = nick.lower().replace(" ", ".")
        nick_underscore = nick.lower().replace(" ", "_")
        nick_normalized = normalize_part(nick)
        for nc in [nick_lower, nick_dot, nick_underscore, nick_normalized]:
            if nc and nc not in candidates:
                candidates.append(nc)

    # From email
    if email:
        email_user = extract_username_from_email(email)
        if email_user and email_user not in candidates:
            candidates.insert(0, email_user)

    # Deduplicate preserving order
    seen = set()
    result = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            result.append(c)

    return result[:10]

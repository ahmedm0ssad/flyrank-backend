import re
from typing import Any

_DISPOSABLE_DOMAINS: set[str] = {
    "mailinator.com",
    "guerrillamail.com",
    "tempmail.com",
    "throwaway.email",
    "yopmail.com",
    "sharklasers.com",
    "maildrop.cc",
    "getnada.com",
    "10minutemail.com",
    "trashmail.com",
}

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")


def _check_url_in_fields(form_data: dict[str, Any]) -> list[str]:
    reasons = []
    for v in form_data.values():
        if isinstance(v, str) and _URL_RE.search(v):
            reasons.append("url_in_field")
            break
    return reasons


def _check_all_fields_identical(form_data: dict[str, Any]) -> list[str]:
    values = [v for v in form_data.values() if isinstance(v, str) and v.strip()]
    if len(values) >= 2 and all(v == values[0] for v in values):
        return ["all_fields_identical"]
    return []


def _check_non_ascii_avalanche(form_data: dict[str, Any]) -> list[str]:
    reasons = []
    for v in form_data.values():
        if isinstance(v, str) and len(v) > 0:
            non_ascii_count = len(_NON_ASCII_RE.findall(v))
            if non_ascii_count > len(v) * 0.5:
                reasons.append("non_ascii_avalanche")
                break
    return reasons


def _check_phone_pattern(form_data: dict[str, Any]) -> list[str]:
    phone = form_data.get("phone", "")
    if phone and not re.match(r"^\+?[1-9]\d{6,14}$", phone):
        return ["phone_pattern_mismatch"]
    return []


def _check_email_blacklist(form_data: dict[str, Any]) -> list[str]:
    email = form_data.get("email", "")
    if email:
        domain = email.split("@")[-1].lower()
        if domain in _DISPOSABLE_DOMAINS:
            return ["disposable_email_domain"]
    return []


SPAM_WEIGHTS: dict[str, float] = {
    "url_in_field": 0.2,
    "all_fields_identical": 0.3,
    "non_ascii_avalanche": 0.2,
    "phone_pattern_mismatch": 0.1,
    "disposable_email_domain": 0.4,
}

SPAM_THRESHOLD = 0.5


def score_submission(form_data: dict[str, Any]) -> tuple[float, list[str]]:
    all_reasons: list[str] = []
    all_reasons.extend(_check_url_in_fields(form_data))
    all_reasons.extend(_check_all_fields_identical(form_data))
    all_reasons.extend(_check_non_ascii_avalanche(form_data))
    all_reasons.extend(_check_phone_pattern(form_data))
    all_reasons.extend(_check_email_blacklist(form_data))

    score = sum(SPAM_WEIGHTS.get(r, 0.0) for r in all_reasons)
    score = min(score, 1.0)
    return score, all_reasons

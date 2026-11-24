from __future__ import annotations

import re
from urllib.parse import urlparse

_SUFFIXES = re.compile(
    r"\b(plc|ltd|limited|nigeria|nig|ng|company|co|inc|llc|group|holdings|services|the)\b\.?",
    re.I,
)


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    host = urlparse(url).hostname or ""
    host = host.lower().removeprefix("www.")
    return host or None


ABBREVIATIONS = {
    r"\bhmo\b": "health maintenance organisation",
    r"\bhealth maintenance organization\b": "health maintenance organisation",
    r"\bmfb\b": "microfinance bank",
    r"\bmicro finance\b": "microfinance",
    r"\bmicro-finance\b": "microfinance",
    r"\bassur(ance)?\b": "assurance",
    r"\bintl\b": "international",
    r"\bhosp\b": "hospital",
}


def normalize_name(name: str) -> str:
    n = name.lower().replace("&", " and ")
    for pat, rep in ABBREVIATIONS.items():
        n = re.sub(pat, rep, n)
    n = re.sub(r"[^a-z0-9 ]+", " ", n)
    n = _SUFFIXES.sub(" ", n)
    return re.sub(r"\s+", " ", n).strip()


def normalize_rc(rc: str | None) -> str | None:
    if not rc:
        return None
    digits = re.sub(r"\D", "", rc)
    return digits or None

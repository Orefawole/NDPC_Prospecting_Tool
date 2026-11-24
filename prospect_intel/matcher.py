"""Cross-check a business against imported NDPC lists.

Outcomes:
  Verified       strong match (RC number, domain, or near-identical name)
  Manual review  plausible but uncertain match, several candidates, or no list loaded
  Unmatched      a list was checked and nothing close was found

Unmatched means "we did not find a record", never "not registered" or
"non-compliant". Lists can be incomplete, out of date, or use a different name.
"""
from __future__ import annotations

from dataclasses import dataclass

from rapidfuzz import fuzz

from .db import NdpcRecord
from .util import normalize_name, normalize_rc

VERIFIED_NAME = 93
REVIEW_NAME = 80


@dataclass
class MatchResult:
    status: str
    record_name: str | None = None
    score: float | None = None
    basis: str | None = None


def match(name: str, domain: str | None, rc_number: str | None, records: list[NdpcRecord]) -> MatchResult:
    records = [r for r in records if r.list_name == "dcmi"]
    if not records:
        return MatchResult("Manual review", basis="no NDPC register loaded")

    rc = normalize_rc(rc_number)
    if rc:
        for r in records:
            if r.rc_number and r.rc_number == rc:
                return MatchResult("Verified", r.name, 100.0, "RC number")
    if domain:
        for r in records:
            if r.domain and r.domain == domain:
                return MatchResult("Verified", r.name, 100.0, "website domain")

    target = normalize_name(name)
    scored = sorted(
        ((fuzz.token_sort_ratio(target, normalize_name(r.name)), r) for r in records),
        key=lambda x: x[0],
        reverse=True,
    )
    best_score, best = scored[0]
    close = [s for s, _ in scored if s >= REVIEW_NAME and best_score - s <= 3]
    if best_score >= VERIFIED_NAME and len(close) == 1:
        return MatchResult("Verified", best.name, float(best_score), "name")
    if best_score >= REVIEW_NAME:
        basis = "several similar names" if len(close) > 1 else "similar name"
        return MatchResult("Manual review", best.name, float(best_score), basis)
    # Same distinctive first word and one name contained in the other
    # (e.g. "Wellguard" vs "Wellguard Health Services"): worth a human look.
    first = target.split(" ")[0] if target else ""
    for _, r in scored[:5]:
        other = normalize_name(r.name)
        if first and len(first) > 3 and other.split(" ")[0] == first and fuzz.token_set_ratio(target, other) >= 90:
            return MatchResult("Manual review", r.name, float(fuzz.token_set_ratio(target, other)), "name contained in record")
    return MatchResult("Unmatched", None, float(best_score), "no close name, RC or domain match")

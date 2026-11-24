"""Transparent lead score, 0-100. See docs/SCORING.md for the rationale."""
from __future__ import annotations

SECTOR_BASE = {"health": 22, "finance": 18, "insurance": 18}
TIER_POINTS = {"UHL": 20, "EHL": 14, "OHL": 8, "unknown": 3}
MATCH_POINTS = {"Unmatched": 20, "Manual review": 12, "Verified": 6}


def score(sector: str, sensitive: list[str], categories: list[str], tier: str, ndpc_status: str,
          gaps: list[str], has_email: bool, has_phone: bool, has_contact_page: bool,
          pages_crawled: int) -> tuple[int, dict]:
    b: dict[str, int] = {}
    # 1. Data sensitivity (max 35)
    sens = SECTOR_BASE.get(sector, 10)
    sens += min(8, 4 * len([x for x in sensitive if "inference" not in x]))
    sens += min(5, len(categories))
    b["data_sensitivity"] = min(35, sens)
    # 2. Likely regulatory weight (max 20)
    b["likely_tier"] = TIER_POINTS.get(tier, 3)
    # 3. NDPC record status (max 20): an open question is more worth a conversation
    b["ndpc_status"] = MATCH_POINTS.get(ndpc_status, 10)
    # 4. Observed gap signals (max 15); none counted when we could not crawl
    b["gap_signals"] = min(15, 5 * len(gaps)) if pages_crawled else 0
    # 5. Reachability (max 10)
    b["reachability"] = (5 if has_email else 0) + (3 if has_phone else 0) + (2 if has_contact_page else 0)
    return sum(b.values()), b


def next_step(total: int, ndpc_status: str, pages_crawled: int, has_email: bool) -> str:
    if pages_crawled == 0:
        return "Website not crawled. Check the site by hand before scoring or outreach."
    if ndpc_status == "Manual review":
        prefix = "Confirm the NDPC record by hand (search the NDPC register for the legal name). "
    elif ndpc_status == "Unmatched":
        prefix = "No NDPC record found in the lists checked; confirm before any outreach mentions registration. "
    else:
        prefix = "NDPC record found; position annual audit, DPO support or training. "
    if total >= 70:
        action = "High priority: send a tailored intro on their sector's NDPA obligations" + ("" if has_email else " via phone or contact form") + "."
    elif total >= 50:
        action = "Medium priority: add to a sector newsletter or webinar invite."
    else:
        action = "Low priority: keep on watchlist."
    return prefix + action

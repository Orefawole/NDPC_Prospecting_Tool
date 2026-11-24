"""Turn evidence into an assessment: what personal data the business likely
processes, a likely NDPC registration tier, and neutral gap notes.

Claude does this when ANTHROPIC_API_KEY is set; otherwise a transparent rule set
does. Both produce the same shape so the rest of the pipeline is unchanged.
"""
from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field

from .config import settings
from .signals import SiteFindings, gap_signals

log = logging.getLogger(__name__)

Tier = Literal["UHL", "EHL", "OHL", "unknown"]

# Tier anchors from the NDPC Guidance Notice on registration of Data
# Controllers/Processors of Major Importance (Dec 2024), para 3(1).
SUBSECTOR_TIER: dict[str, tuple[Tier, str]] = {
    "commercial_bank": ("UHL", "Commercial banks are named in the UHL tier"),
    "fintech": ("UHL", "Fintechs are named in the UHL tier"),
    "payment_service": ("UHL", "Payment gateway providers are named in the UHL tier"),
    "insurer": ("UHL", "Insurance companies are named in the UHL tier"),
    "hmo": ("UHL", "HMOs process health data of large enrollee bases (>5,000 in 6 months likely)"),
    "microfinance_bank": ("EHL", "Microfinance banks are named in the EHL tier"),
    "mortgage_bank": ("EHL", "Mortgage banks are named in the EHL tier"),
    "hospital": ("EHL", "Secondary/tertiary hospitals are named in the EHL tier"),
    "investment_firm": ("EHL", "Volume-based estimate (1,000-5,000 data subjects in 6 months)"),
    "insurance_broker": ("OHL", "Volume-based estimate (200-1,000 data subjects in 6 months)"),
    "diagnostic_lab": ("OHL", "Independent medical laboratories are named in the OHL tier"),
    "specialist_clinic": ("OHL", "Processes sensitive (health) data of >200 data subjects commercially"),
    "fertility_clinic": ("OHL", "Processes sensitive (health) data of >200 data subjects commercially"),
    "pharmacy": ("OHL", "Volume-based estimate; may hold prescription (health) data"),
}

SENSITIVE_FROM_SIGNAL = {
    "health_data": "health",
    "biometric_data": "biometric",
    "children_data": "children's data",
}
CATEGORY_FROM_SIGNAL = {
    "account_signup": "account/identity details",
    "appointment_booking": "contact and appointment details",
    "financial_identifiers": "financial identifiers (BVN, account/card)",
    "national_id": "government ID numbers (NIN, passport)",
    "kyc_onboarding": "KYC documents",
    "loan_or_credit": "credit and income information",
    "insurance_claims": "policy and claims information",
    "payment_gateway": "payment transaction data",
    "analytics_trackers": "online identifiers (cookies, device data)",
    "file_upload": "uploaded documents",
}


class GapNote(BaseModel):
    note: str = Field(description="Neutral observation, e.g. 'No DPO contact found on pages visited'")
    evidence_url: str | None = None


class Assessment(BaseModel):
    data_categories: list[str]
    sensitive_data: list[str] = Field(description="NDPA s.30 sensitive categories evidenced, e.g. health, biometric")
    likely_tier: Tier
    tier_reason: str
    gap_signals: list[GapNote]
    summary: str = Field(description="2-3 sentences, neutral, for a consultant deciding whether to reach out")


SYSTEM = """You assess Nigerian businesses for a data protection consultant, using only the public evidence supplied.

Rules:
- Base every claim on the evidence given. If evidence is thin, say so and use likely_tier "unknown".
- Never state or imply that the business is non-compliant, unregistered, or in breach. Gap signals are neutral observations about what was or was not seen on the pages visited.
- Do not infer anything about individual people. You are describing an organisation's processing.
- Sensitive data follows NDPA 2023 s.30 (health, biometric, genetic, religious/political belief, sex life, ethnicity, trade union, etc.). Treat children's data as a separate flag.
- Likely tier uses the NDPC Guidance Notice on registration of DCPMIs:
  UHL: commercial banks, insurers, fintechs, payment gateways, telcos, or >5,000 data subjects in 6 months.
  EHL: microfinance banks, mortgage banks, secondary/tertiary hospitals, higher institutions, or 1,000-5,000 in 6 months.
  OHL: primary health centres, independent labs, small hotels, processors of sensitive data of >200 data subjects commercially, or 200-1,000 in 6 months.
- Keep the summary short and factual."""


def _heuristic(business: dict, findings: SiteFindings, pages_crawled: int) -> Assessment:
    names = {s.signal for s in findings.signals}
    urls = {s.signal: s.url for s in findings.signals}
    sensitive = sorted({v for k, v in SENSITIVE_FROM_SIGNAL.items() if k in names})
    if business.get("sector") == "health" and "health" not in sensitive:
        sensitive.append("health (sector inference)")
    categories = sorted({v for k, v in CATEGORY_FROM_SIGNAL.items() if k in names})
    tier, reason = SUBSECTOR_TIER.get(business.get("subsector") or "", ("unknown", "No subsector anchor; needs manual sizing"))
    gaps = [GapNote(note=g, evidence_url=urls.get("privacy_policy")) for g in gap_signals(names, pages_crawled)]
    summary = (
        f"{business['name']} ({business.get('subsector') or business.get('sector')}) shows "
        f"{len(categories)} personal data collection signal(s)"
        + (f" and sensitive data indicators ({', '.join(sensitive)})" if sensitive else "")
        + f". Likely NDPC tier: {tier}."
        + ("" if pages_crawled else " Website not crawled, so evidence is limited.")
    )
    return Assessment(
        data_categories=categories,
        sensitive_data=sensitive,
        likely_tier=tier,
        tier_reason=reason,
        gap_signals=gaps,
        summary=summary,
    )


def _claude(business: dict, findings: SiteFindings, pages_crawled: int) -> Assessment | None:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    evidence = [{"signal": s.signal, "detail": s.detail, "url": s.url} for s in findings.signals]
    anchor = SUBSECTOR_TIER.get(business.get("subsector") or "")
    payload = {
        "business": {k: business.get(k) for k in ("name", "sector", "subsector", "city", "website")},
        "subsector_tier_anchor": anchor,
        "pages_crawled": pages_crawled,
        "rule_based_gap_notes": gap_signals({s.signal for s in findings.signals}, pages_crawled),
        "evidence": evidence,
        "privacy_page_excerpt": findings.privacy_text[:6000],
        "site_text_excerpt": findings.page_text[:8000],
    }
    try:
        resp = client.beta.messages.parse(
            model=settings.claude_model,
            max_tokens=16000,
            system=SYSTEM,
            output_config={"effort": settings.claude_effort},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{"role": "user", "content": "Assess this business.\n\n" + json.dumps(payload, ensure_ascii=False)}],
            output_format=Assessment,
        )
    except anthropic.RateLimitError:
        log.warning("Claude rate limited for %s; using rule-based analysis", business["name"])
        return None
    except anthropic.APIStatusError as e:
        log.warning("Claude API error %s for %s; using rule-based analysis", e.status_code, business["name"])
        return None
    except anthropic.APIConnectionError:
        log.warning("Claude unreachable for %s; using rule-based analysis", business["name"])
        return None
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        return None
    return resp.parsed_output


def assess(business: dict, findings: SiteFindings, pages_crawled: int, use_claude: bool = True) -> tuple[Assessment, str]:
    if use_claude and settings.anthropic_api_key:
        result = _claude(business, findings, pages_crawled)
        if result is not None:
            return result, "claude"
    return _heuristic(business, findings, pages_crawled), "heuristic"

"""Rule-based evidence extraction from public web pages.

Each signal is a neutral observation ("no cookie consent banner detected on the
pages we visited"), never a legal finding.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from .crawler import Page

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+234|0)[789][01]\d[\s-]?\d{3}[\s-]?\d{4}")

# (signal, regex over visible text + html, short label)
TEXT_SIGNALS: list[tuple[str, str]] = [
    ("health_data", r"medical (history|record)|patient (portal|record|registration)|diagnos(is|tic)|genotype|blood group|HIV|lab(oratory)? results?"),
    ("biometric_data", r"biometric|fingerprint|facial (recognition|verification)|liveness"),
    ("financial_identifiers", r"\bBVN\b|bank verification number|account number|card details"),
    ("national_id", r"\bNIN\b|national identification number|international passport|voter'?s card"),
    ("kyc_onboarding", r"\bKYC\b|know your customer|upload (your )?(id|identification)|selfie"),
    ("loan_or_credit", r"loan application|apply for (a )?loan|credit score|salary advance"),
    ("insurance_claims", r"(file|submit|make) a claim|claims? form|policy ?holder|enrollee"),
    ("children_data", r"\bpaediatric|\bpediatric|child(ren)?'?s? (health|clinic|record)"),
    ("appointment_booking", r"book (an|your) appointment|schedule (a|an) (visit|consultation)|request appointment"),
    ("account_signup", r"sign ?up|create (an|your) account|open (an|a) account|register now|get started"),
    ("ndpa_reference", r"Nigeria Data Protection Act|\bNDPA\b|NDP Act"),
    ("ndpr_reference", r"Nigeria Data Protection Regulation|\bNDPR\b"),
    ("dpo_contact", r"data protection officer|\bDPO\b|dpo@|privacy@|dataprotection@"),
]

HTML_SIGNALS: list[tuple[str, str]] = [
    ("payment_gateway", r"paystack|flutterwave|interswitch|remita|monnify|opay|squadco"),
    ("analytics_trackers", r"googletagmanager|google-analytics|gtag\(|fbq\(|connect\.facebook\.net|hotjar|clarity\.ms"),
    ("cookie_consent_tool", r"cookiebot|onetrust|cookieyes|cookie-?consent|cookie-?notice|termly|osano|accept (all )?cookies"),
    ("mobile_app", r"play\.google\.com/store/apps|apps\.apple\.com"),
    ("file_upload", r"type=[\"']file[\"']"),
    ("password_field", r"type=[\"']password[\"']"),
]


@dataclass
class Signal:
    signal: str
    detail: str
    url: str


@dataclass
class SiteFindings:
    signals: list[Signal]
    emails: list[str]
    phones: list[str]
    contact_page: str | None
    privacy_page: str | None
    privacy_text: str  # trimmed, for the AI step
    page_text: str  # trimmed combined text, for the AI step


def _snippet(text: str, m: re.Match, width: int = 70) -> str:
    s, e = max(0, m.start() - width), min(len(text), m.end() + width)
    return re.sub(r"\s+", " ", text[s:e]).strip()


def extract(pages: list[Page]) -> SiteFindings:
    found: dict[str, Signal] = {}
    emails: set[str] = set()
    phones: set[str] = set()
    contact_page = privacy_page = None
    privacy_text = ""
    texts: list[str] = []

    for p in pages:
        soup = BeautifulSoup(p.html, "html.parser")
        for t in soup(["script", "style", "noscript"]):
            t.extract()
        text = soup.get_text(" ", strip=True)
        texts.append(f"[{p.url}]\n{text[:3000]}")
        lower_url = p.url.lower()

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("mailto:"):
                emails.add(href[7:].split("?")[0].strip().lower())
            elif href.startswith("tel:"):
                phones.add(href[4:].strip())
            label = (a.get_text(" ", strip=True) + " " + href).lower()
            if "privacy" in label and "privacy_policy" not in found:
                found["privacy_policy"] = Signal("privacy_policy", a.get_text(" ", strip=True)[:80] or href, p.url)

        if re.search(r"privacy|data-protection|ndpa", lower_url):
            privacy_page = privacy_page or p.url
            privacy_text = privacy_text or text[:12000]
            found.setdefault("privacy_policy", Signal("privacy_policy", "privacy page reached", p.url))
        if "contact" in lower_url:
            contact_page = contact_page or p.url

        emails.update(e.lower() for e in EMAIL_RE.findall(text))
        phones.update(PHONE_RE.findall(text))

        for name, pat in TEXT_SIGNALS:
            if name in found:
                continue
            m = re.search(pat, text, re.I)
            if m:
                found[name] = Signal(name, _snippet(text, m), p.url)
        for name, pat in HTML_SIGNALS:
            if name in found:
                continue
            m = re.search(pat, p.html, re.I)
            if m:
                found[name] = Signal(name, m.group(0)[:80], p.url)

    # Keep business contact emails only; drop asset filenames that look like emails.
    emails = {e for e in emails if not re.search(r"\.(png|jpe?g|gif|svg|webp)$", e)}
    return SiteFindings(
        signals=list(found.values()),
        emails=sorted(emails),
        phones=sorted(phones),
        contact_page=contact_page,
        privacy_page=privacy_page,
        privacy_text=privacy_text,
        page_text="\n\n".join(texts)[:15000],
    )


def gap_signals(signal_names: set[str], pages_crawled: int) -> list[str]:
    """Neutral 'not observed' notes. Only meaningful when we actually crawled."""
    if pages_crawled == 0:
        return []
    gaps = []
    if "privacy_policy" not in signal_names:
        gaps.append("No privacy policy link found on the pages visited")
    if "analytics_trackers" in signal_names and "cookie_consent_tool" not in signal_names:
        gaps.append("Analytics or ad trackers present but no cookie consent tool detected")
    if "dpo_contact" not in signal_names:
        gaps.append("No Data Protection Officer contact found on the pages visited")
    if "ndpr_reference" in signal_names and "ndpa_reference" not in signal_names:
        gaps.append("Privacy text cites the NDPR but not the NDP Act 2023")
    return gaps

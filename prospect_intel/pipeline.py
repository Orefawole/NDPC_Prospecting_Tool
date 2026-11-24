"""Pipeline steps: add businesses (deduped), then crawl, analyse, match, score."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import analyzer, matcher, scoring, signals
from .crawler import Crawler
from .db import Business, Evidence, Lead, NdpcRecord, audit
from .util import domain_of, normalize_name

log = logging.getLogger(__name__)


def add_business(s: Session, **fields) -> tuple[Business, bool]:
    """Insert unless a duplicate exists (same source ref, domain, or name+city)."""
    domain = domain_of(fields.get("website"))
    q = select(Business)
    if fields.get("source_ref"):
        hit = s.scalar(q.where(Business.source_ref == fields["source_ref"]))
        if hit:
            return hit, False
    if domain:
        hit = s.scalar(q.where(Business.domain == domain))
        if hit:
            return hit, False
    key = normalize_name(fields["name"])
    for b in s.scalars(q.where(Business.city == fields.get("city"))):
        if normalize_name(b.name) == key:
            return b, False
    b = Business(domain=domain, **fields)
    s.add(b)
    s.flush()
    return b, True


def process_business(s: Session, b: Business, crawler: Crawler, records: list[NdpcRecord], use_claude: bool = True) -> Lead:
    pages, skip = crawler.crawl_site(b.website) if b.website else ([], "no website listed")
    findings = signals.extract(pages)

    b.evidence.clear()
    for sig in findings.signals:
        b.evidence.append(Evidence(signal=sig.signal, detail=sig.detail[:500], url=sig.url))
    if skip:
        b.evidence.append(Evidence(signal="crawl_skipped", detail=skip, url=b.website or ""))

    info = {"name": b.name, "sector": b.sector, "subsector": b.subsector, "city": b.city, "website": b.website}
    assessment, method = analyzer.assess(info, findings, len(pages), use_claude=use_claude)
    m = matcher.match(b.name, b.domain, b.rc_number, records)

    email = next((e for e in findings.emails if b.domain and e.endswith(b.domain)), None) or (findings.emails[0] if findings.emails else None)
    phone = b.phone or (findings.phones[0] if findings.phones else None)
    gaps = [g.note for g in assessment.gap_signals]
    total, breakdown = scoring.score(
        b.sector, assessment.sensitive_data, assessment.data_categories, assessment.likely_tier,
        m.status, gaps, bool(email), bool(phone), bool(findings.contact_page), len(pages),
    )

    lead = b.lead or Lead(business=b)
    lead.data_categories = assessment.data_categories
    lead.sensitive_data = assessment.sensitive_data
    lead.likely_tier = assessment.likely_tier
    lead.tier_reason = assessment.tier_reason
    lead.gap_signals = [g.model_dump() for g in assessment.gap_signals]
    lead.analysis_summary = assessment.summary
    lead.analysis_method = method
    lead.ndpc_status = m.status
    lead.ndpc_match_name = m.record_name
    lead.ndpc_match_score = m.score
    lead.ndpc_match_basis = m.basis
    lead.public_email = email
    lead.public_phone = phone
    lead.contact_page = findings.contact_page
    lead.score = total
    lead.score_breakdown = breakdown
    lead.next_step = scoring.next_step(total, m.status, len(pages), bool(email))
    s.add(lead)
    audit(s, "lead_scored", f"{b.name}: {total} ({method}, {m.status}, {len(pages)} pages)")
    return lead


def run(s: Session, crawler: Crawler | None = None, limit: int | None = None, refresh: bool = False,
        use_claude: bool = True, sector: str | None = None) -> int:
    crawler = crawler or Crawler()
    records = list(s.scalars(select(NdpcRecord)))
    q = select(Business)
    if sector:
        q = q.where(Business.sector == sector)
    done = 0
    for b in s.scalars(q).all():
        if b.lead and not refresh:
            continue
        try:
            process_business(s, b, crawler, records, use_claude)
            s.commit()
            done += 1
            log.info("scored %s", b.name)
        except Exception:  # keep the batch going, log the failure
            s.rollback()
            log.exception("failed on %s", b.name)
        if limit and done >= limit:
            break
    return done

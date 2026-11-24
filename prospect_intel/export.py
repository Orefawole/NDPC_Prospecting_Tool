from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Business, Lead


def leads_frame(s: Session) -> pd.DataFrame:
    rows = []
    for lead, b in s.execute(select(Lead, Business).join(Business)).all():
        rows.append(
            {
                "score": lead.score,
                "name": b.name,
                "sector": b.sector,
                "subsector": b.subsector,
                "city": b.city,
                "website": b.website,
                "public_email": lead.public_email,
                "public_phone": lead.public_phone,
                "contact_page": lead.contact_page,
                "ndpc_status": lead.ndpc_status,
                "ndpc_match": lead.ndpc_match_name,
                "ndpc_match_basis": lead.ndpc_match_basis,
                "likely_tier": lead.likely_tier,
                "tier_reason": lead.tier_reason,
                "sensitive_data": "; ".join(lead.sensitive_data or []),
                "data_categories": "; ".join(lead.data_categories or []),
                "gap_signals": "; ".join(g["note"] for g in lead.gap_signals or []),
                "summary": lead.analysis_summary,
                "next_step": lead.next_step,
                "evidence_urls": " ".join(sorted({e.url for e in b.evidence if e.url})),
                "analysis_method": lead.analysis_method,
                "source": b.source,
            }
        )
    df = pd.DataFrame(rows)
    return df.sort_values("score", ascending=False) if not df.empty else df

"""Lead dashboard. Run: streamlit run dashboard/app.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from sqlalchemy import select  # noqa: E402

from prospect_intel import db  # noqa: E402
from prospect_intel.db import Business  # noqa: E402
from prospect_intel.export import leads_frame  # noqa: E402

st.set_page_config(page_title="NDPC Prospect Intelligence", layout="wide")
db.init_db()

st.title("NDPC Prospect Intelligence")
st.caption(
    "Leads are built from public information only. **Unmatched** means no record was found in the NDPC lists "
    "loaded, not that the business is unregistered or non-compliant. Gap signals are observations about the "
    "pages visited, not legal findings. Verify before outreach."
)

with db.session() as s:
    df = leads_frame(s)

if df.empty:
    st.info("No leads yet. Run `python -m prospect_intel demo` for fictional sample data, or discover and run the pipeline.")
    st.stop()

with st.sidebar:
    st.header("Filters")
    sectors = st.multiselect("Sector", sorted(df.sector.dropna().unique()), default=sorted(df.sector.dropna().unique()))
    cities = st.multiselect("City", sorted(df.city.dropna().unique()), default=sorted(df.city.dropna().unique()))
    statuses = st.multiselect("NDPC status", ["Verified", "Unmatched", "Manual review"], default=["Verified", "Unmatched", "Manual review"])
    tiers = st.multiselect("Likely tier", ["UHL", "EHL", "OHL", "unknown"], default=["UHL", "EHL", "OHL", "unknown"])
    min_score = st.slider("Minimum score", 0, 100, 0)
    sensitive_only = st.checkbox("Sensitive data evidenced only")

f = df[
    df.sector.isin(sectors)
    & (df.city.isin(cities) | df.city.isna())
    & df.ndpc_status.isin(statuses)
    & df.likely_tier.isin(tiers)
    & (df.score >= min_score)
]
if sensitive_only:
    f = f[f.sensitive_data.fillna("").str.len() > 0]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Leads", len(f))
c2.metric("Score 70+", int((f.score >= 70).sum()))
c3.metric("Needs manual review", int((f.ndpc_status == "Manual review").sum()))
c4.metric("Sensitive data", int((f.sensitive_data.fillna("").str.len() > 0).sum()))

st.dataframe(
    f[["score", "name", "sector", "subsector", "city", "likely_tier", "ndpc_status", "sensitive_data", "public_email", "public_phone", "next_step"]],
    use_container_width=True,
    hide_index=True,
    column_config={"score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d")},
)
st.download_button("Download CSV", f.to_csv(index=False).encode(), "ndpc_leads.csv", "text/csv")

st.subheader("Lead detail")
pick = st.selectbox("Business", f.name.tolist())
if pick:
    row = f[f.name == pick].iloc[0]
    with db.session() as s:
        b = s.scalar(select(Business).where(Business.name == pick))
        lead = b.lead
        left, right = st.columns([2, 1])
        with left:
            st.markdown(f"**{b.name}** · {b.subsector or b.sector} · {b.city or ''}")
            if b.website:
                st.markdown(f"Website: {b.website}")
            st.markdown(f"**Summary** ({lead.analysis_method}): {lead.analysis_summary}")
            st.markdown(f"**Likely NDPC tier:** {lead.likely_tier}. {lead.tier_reason or ''}")
            st.markdown(f"**NDPC status:** {lead.ndpc_status}" + (f" (closest record: {lead.ndpc_match_name}, basis: {lead.ndpc_match_basis})" if lead.ndpc_match_name else f" ({lead.ndpc_match_basis})"))
            if lead.gap_signals:
                st.markdown("**Gap signals (observations)**")
                for g in lead.gap_signals:
                    st.markdown(f"- {g['note']}")
            st.markdown(f"**Next step:** {lead.next_step}")
        with right:
            st.markdown("**Score breakdown**")
            st.dataframe(pd.DataFrame(lead.score_breakdown.items(), columns=["factor", "points"]), hide_index=True)
            st.markdown("**Public contact**")
            st.write({"email": lead.public_email, "phone": lead.public_phone, "contact page": lead.contact_page})
        st.markdown("**Evidence**")
        st.dataframe(
            pd.DataFrame([{"signal": e.signal, "detail": e.detail, "url": e.url} for e in b.evidence]),
            use_container_width=True, hide_index=True,
        )

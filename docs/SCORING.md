# Lead score (0-100)

| Factor | Max | How it is scored |
|---|---|---|
| Data sensitivity | 35 | Sector base (health 22, finance 18, insurance 18) + 4 per evidenced sensitive category (max 8) + 1 per personal data category seen (max 5) |
| Likely NDPC tier | 20 | UHL 20, EHL 14, OHL 8, unknown 3 |
| NDPC record status | 20 | Unmatched 20, Manual review 12, Verified 6 |
| Gap signals | 15 | 5 per neutral gap observation (only when the site was crawled) |
| Reachability | 10 | Public email 5, phone 3, contact page 2 |

**Why Unmatched scores higher than Verified:** an open question about registration is a natural reason to talk. A Verified business still scores, because registered controllers need annual Compliance Audit Returns, DPO support and training.

**Bands and next steps**

- 70+: high priority, tailored intro on the sector's NDPA obligations.
- 50-69: medium, newsletter or webinar invite.
- Under 50: watchlist.
- Every Unmatched or Manual review lead is told to confirm the NDPC record by hand first. A lead whose site was not crawled is told to check the site by hand.

**Tier anchors** (NDPC Guidance Notice NDPC/HQ/GN/VOL.03/B/24, Dec 2024, para 3(1)):

- UHL (N250,000): commercial banks, insurers, fintechs, payment gateways, telcos, or more than 5,000 data subjects in 6 months.
- EHL (N100,000): microfinance banks, mortgage banks, secondary/tertiary hospitals, higher institutions, MDAs, or 1,000-5,000.
- OHL (N10,000): primary health centres, independent medical labs, schools, small hotels, commercial processors of sensitive data of more than 200 people, or 200-1,000.

Subsectors in this MVP map to those anchors in `prospect_intel/analyzer.py` (`SUBSECTOR_TIER`). HMOs, investment firms, brokers and pharmacies are volume-based estimates and are marked as such.

Weights live in `prospect_intel/scoring.py`. Change them there; the dashboard shows the breakdown per lead.

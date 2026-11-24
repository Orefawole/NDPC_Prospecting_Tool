# NDPC Prospect Intelligence (MVP)

Finds Nigerian businesses in **Finance, Health and Insurance** (default cities: **Lagos and Abuja**) that show public signs of processing personal data, checks them against NDPC public lists, and ranks them for verification and outreach by Data Protection Officers, licensed DPCOs and consultants.

Every lead carries business info, public contact channels, evidence links, an NDPC status of **Verified / Unmatched / Manual review**, a likely NDPC registration tier, a 0-100 score and a recommended next step. An absent NDPC record is never treated as proof of non-compliance.

## How it works

1. **Discover**: Google Places Text Search per sector/subsector and city, or import a CSV you're permitted to use. Duplicates are merged by place ID, domain, or name+city.
2. **Crawl**: up to 6 public pages per site (privacy, cookie, contact, booking, signup, about), robots.txt respected, 2 s delay, own domain only, no form submission.
3. **Extract signals**: booking/signup forms, BVN/NIN/KYC, health, biometric, payment gateways, trackers, cookie consent tools, privacy policy, NDPA vs NDPR wording, DPO contact, public email/phone.
4. **Analyse**: Claude (`claude-opus-5-5`, structured output) reads the evidence and returns data categories, sensitive data, likely tier (per the NDPC Guidance Notice) and neutral gap notes. Without an API key, or if a call fails, a transparent rule set produces the same fields.
5. **NDPC cross-check**: RC number, then website domain, then fuzzy name match against the imported register. See `docs/NDPC_SOURCES.md`.
6. **Score and recommend**: see `docs/SCORING.md`.
7. **Review**: Streamlit dashboard with filters, evidence and CSV download; `export` writes CSV for Sheets.
8. **Audit log**: every import, discovery run and scoring is logged in the `audit_log` table.

## Quick start (no keys needed)

```bash
pip install -r requirements.txt
python -m prospect_intel demo          # fictional businesses on .example domains
streamlit run dashboard/app.py
```

## Real run

```bash
cp .env.example .env                   # add ANTHROPIC_API_KEY and GOOGLE_PLACES_API_KEY
python -m prospect_intel fetch-ndpc --list dcmi --out data/ndpc_dcmi.csv   # or export the table by hand
python -m prospect_intel import-ndpc data/ndpc_dcmi.csv --list dcmi
python -m prospect_intel discover --sectors finance health insurance --cities Lagos Abuja
python -m prospect_intel run --limit 50
python -m prospect_intel export --out data/exports/leads.csv
streamlit run dashboard/app.py
```

Also: `import-businesses your.csv` (columns `name,sector` plus optional `subsector,city,address,website,phone,rc_number`), `run --refresh`, `run --no-claude`, `run --sector health`.

Set `DATABASE_URL` to a Postgres URL for a hosted deployment (add `psycopg[binary]`).

## Tests

```bash
pytest -q
```

## Guardrails built in

- Wording: "Unmatched" and "gap signals" are observations; tests fail if output text says non-compliant, in breach, violation or unregistered.
- No gap signals or gap points are claimed for a site we could not crawl.
- Business contact channels only; nothing is inferred about individual people.
- robots.txt honoured; 401/403 on robots.txt is treated as "do not crawl".
- Your own NDPA obligations for the contact data you hold: see `docs/LAWFUL_BASIS.md`.

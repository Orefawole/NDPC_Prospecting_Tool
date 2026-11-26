# NDPC Prospect Intelligence (MVP)

Finds Nigerian businesses in **Finance, Health and Insurance** across Nigeria that show public signs of processing personal data, checks them against NDPC public lists, and ranks them for verification and outreach by Data Protection Officers, licensed DPCOs and consultants.

Every lead carries business info, public contact channels, evidence links, an NDPC status of **Verified / Unmatched / Manual review**, a likely NDPC registration tier, a 0-100 score and a recommended next step. An absent NDPC record is never treated as proof of non-compliance.

## How it works

1. **Discover**: OpenStreetMap via the free Overpass API (no key, all 36 states + FCT, state by state), Google Places if you have a key, or a CSV you're permitted to use. Bank branches collapse to one entry per brand per state. Duplicates are merged by source ID, domain, or name+location.
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

## Real run on Windows (PowerShell, venv active)

```powershell
Copy-Item .env.example .env            # then open .env and add ANTHROPIC_API_KEY (Google key optional)
python -m prospect_intel init
python -m prospect_intel discover --cities Lagos                  # one state first, ~1-2 min
python -m prospect_intel discover                                 # all of Nigeria, ~20-40 min
python -m prospect_intel import-businesses data\businesses_template.csv   # or your own CSV
python -m prospect_intel run --limit 25
python -m prospect_intel export --out data\exports\leads.csv
streamlit run dashboard\app.py
```

`discover` uses OpenStreetMap automatically when no Google key is set (`--source osm` forces it). `--cities` takes state names or big-city names (Port Harcourt, Ibadan, Kano...), or `all`. Add `--include-no-website` to keep OSM entries without a website; they can't be crawled and land in "check by hand". OSM data is (c) OpenStreetMap contributors, ODbL: keep that credit on shared exports.

## Real run (macOS/Linux)

```bash
cp .env.example .env                   # add ANTHROPIC_API_KEY; GOOGLE_PLACES_API_KEY is optional
python -m prospect_intel fetch-ndpc --list dcmi --out data/ndpc_dcmi.csv   # or export the table by hand
python -m prospect_intel import-ndpc data/ndpc_dcmi.csv --list dcmi
python -m prospect_intel discover --sectors finance health insurance --cities Lagos Abuja
python -m prospect_intel run --limit 50
python -m prospect_intel export --out data/exports/leads.csv
streamlit run dashboard/app.py
```

See RUNBOOK.md for step-by-step Windows instructions and troubleshooting.

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

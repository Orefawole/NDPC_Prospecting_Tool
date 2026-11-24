# NDPC public sources

| Source | URL | Use |
|---|---|---|
| Registered Data Controllers/Processors of Major Importance | https://services.ndpc.gov.ng/repo/?flp=dcmi | Main cross-check list. Columns: Name, Category, Year |
| Licensed DPCOs | https://services.ndpc.gov.ng/repo/?flp=dpco | Competitor/partner context; not used for matching |
| Guidance Notice on registration (Dec 2024) | https://ndpc.gov.ng/wp-content/uploads/2025/07/Updated-Guidance-Notice-on-Registtration-2024.pdf | Tier anchors |
| GAID 2025 | https://ndpc.gov.ng/wp-content/uploads/2025/07/NDP-ACT-GAID-2025-MARCH-20TH.pdf | Obligations to reference in outreach |
| NDPC news (investigations, sanctions) | https://ndpc.gov.ng | Optional `enforcement` list, imported by hand |

**Caveats**

- The NIMP tables load rows with JavaScript. `fetch-ndpc` uses headless Chromium to read them; it was not testable from the build environment (the host was unreachable there), so check its first output by eye. If it fails, copy the table into a CSV with a `name` column (plus `category`, `year`, optional `rc_number`, `website`) and use `import-ndpc`.
- The register lists names only, so most matches rely on fuzzy names. That is why near matches go to Manual review rather than Verified.
- A business may be registered under its legal name, a parent company or a group entity. Unmatched leads must be checked by hand before any outreach mentions registration.
- The Guidance Notice does not describe a public verification service. Treat the register as indicative.

**Matching thresholds** (`prospect_intel/matcher.py`): exact RC or domain is Verified; name similarity 93+ with a single candidate is Verified; 80-92, several close candidates, or a contained name is Manual review; below that is Unmatched. With no register loaded, every lead is Manual review.

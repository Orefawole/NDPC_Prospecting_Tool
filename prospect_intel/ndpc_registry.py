"""Load NDPC public lists into the database.

Known public sources (checked Nov 2026):
- Registered Data Controllers/Processors of Major Importance:
  https://services.ndpc.gov.ng/repo/?flp=dcmi   (columns: Name | Category | Year)
- Licensed DPCOs: https://services.ndpc.gov.ng/repo/?flp=dpco
  (columns: Name | License Date | Email | Phone | State | Status)
- NDPC news/press releases on investigations and sanctions: https://ndpc.gov.ng

The NIMP tables load their rows with JavaScript, so `fetch_nimp` drives a
headless browser. If that is blocked or the page changes, export the table to
CSV by hand and use `load_csv`.
"""
from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .db import NdpcRecord, audit
from .util import domain_of, normalize_rc

NIMP_URLS = {
    "dcmi": "https://services.ndpc.gov.ng/repo/?flp=dcmi",
    "dpco": "https://services.ndpc.gov.ng/repo/?flp=dpco",
}


def load_csv(s: Session, path: str | Path, list_name: str, source_url: str, replace: bool = True) -> int:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [{k.strip().lower(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(f)]
    if replace:
        s.execute(delete(NdpcRecord).where(NdpcRecord.list_name == list_name))
    for r in rows:
        if not r.get("name"):
            continue
        s.add(
            NdpcRecord(
                list_name=list_name,
                name=r["name"],
                category=r.get("category") or None,
                year=r.get("year") or None,
                rc_number=normalize_rc(r.get("rc_number")),
                domain=domain_of(r.get("website") or r.get("domain")),
                source_url=r.get("source_url") or source_url,
            )
        )
    audit(s, "ndpc_import", f"{list_name}: {len(rows)} rows from {path}")
    s.commit()
    return len(rows)


def fetch_nimp(list_name: str, out_csv: str | Path) -> int:
    """Scrape a NIMP public table to CSV using Playwright. Experimental."""
    from playwright.sync_api import sync_playwright

    url = NIMP_URLS[list_name]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        headers = [h.strip().lower() for h in page.eval_on_selector_all("table thead th", "els => els.map(e => e.innerText)")]
        rows: list[list[str]] = []
        while True:
            rows += page.eval_on_selector_all(
                "table tbody tr", "trs => trs.map(tr => [...tr.querySelectorAll('td')].map(td => td.innerText.trim()))"
            )
            nxt = page.query_selector("a.paginate_button.next:not(.disabled), li.next:not(.disabled) a")
            if not nxt:
                break
            nxt.click()
            page.wait_for_timeout(1200)
        browser.close()
    rows = [r for r in rows if len(r) == len(headers) and any(r)]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers + ["source_url"])
        for r in rows:
            w.writerow(r + [url])
    return len(rows)

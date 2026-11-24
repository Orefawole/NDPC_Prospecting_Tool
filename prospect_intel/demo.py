"""Offline demo with fictional businesses on reserved .example domains.

Nothing here is real: names, sites and the NDPC sample register are invented so
the pipeline and dashboard can be tried without API keys or network access.
"""
from __future__ import annotations

from pathlib import Path

import httpx
from sqlalchemy.orm import Session

from . import ndpc_registry, pipeline
from .config import ROOT
from .crawler import Crawler
from .sources import csv_seed

DEMO = ROOT / "data" / "demo_sites"


def _handler(request: httpx.Request) -> httpx.Response:
    host = request.url.host
    path = request.url.path.strip("/") or "index"
    if path == "robots.txt":
        f = DEMO / host / "robots.txt"
        return httpx.Response(200, text=f.read_text()) if f.exists() else httpx.Response(404)
    f = DEMO / host / f"{path}.html"
    if not f.exists():
        return httpx.Response(404, text="not found")
    return httpx.Response(200, text=f.read_text(), headers={"content-type": "text/html"})


def demo_crawler() -> Crawler:
    client = httpx.Client(transport=httpx.MockTransport(_handler), follow_redirects=True)
    return Crawler(client=client, delay=0, max_pages=6, user_agent="ProspectIntelBot/0.1")


def load_demo(s: Session) -> int:
    ndpc_registry.load_csv(s, ROOT / "data" / "sample_ndpc_dcmi.csv", "dcmi", "demo://sample-register")
    for row in csv_seed.read_rows(ROOT / "data" / "sample_businesses.csv"):
        pipeline.add_business(
            s, name=row["name"], sector=row["sector"], subsector=row.get("subsector") or None,
            city=row.get("city") or None, website=row.get("website") or None, phone=row.get("phone") or None,
            rc_number=row.get("rc_number") or None, source="demo", source_ref=None,
        )
    s.commit()
    return pipeline.run(s, crawler=demo_crawler(), refresh=True, use_claude=False)

"""Import businesses from a CSV you are permitted to use (directory exports,
your own CRM, manual research). Required column: name, sector.
Optional: subsector, city, address, website, phone, rc_number."""
from __future__ import annotations

import csv
from pathlib import Path


def read_rows(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = [{k.strip().lower(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(f)]
    missing = [i for i, r in enumerate(rows, 2) if not r.get("name") or not r.get("sector")]
    if missing:
        raise ValueError(f"{path}: rows {missing[:10]} lack name or sector")
    return rows

"""Command line: python -m prospect_intel <command>"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import db, ndpc_registry, pipeline
from .config import ROOT, settings
from .sources import csv_seed


def main(argv=None):
    p = argparse.ArgumentParser(prog="prospect_intel")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create database tables")

    d = sub.add_parser("discover", help="find businesses (OpenStreetMap by default, or Google Places)")
    d.add_argument("--source", choices=["osm", "google"], default=None,
                   help="osm needs no key (default unless GOOGLE_PLACES_API_KEY is set)")
    d.add_argument("--sectors", nargs="*", default=list(settings.sectors))
    d.add_argument("--cities", nargs="*", default=None,
                   help="osm: state names or 'all' (default: all of Nigeria). google: cities (default Lagos Abuja)")
    d.add_argument("--pages", type=int, default=1, help="Google only: result pages (20 each) per query")
    d.add_argument("--include-no-website", action="store_true",
                   help="osm only: also keep entries without a website (they cannot be crawled)")

    ib = sub.add_parser("import-businesses", help="add businesses from a CSV")
    ib.add_argument("csv")

    inn = sub.add_parser("import-ndpc", help="load an NDPC list from CSV")
    inn.add_argument("csv")
    inn.add_argument("--list", default="dcmi", choices=["dcmi", "dpco", "enforcement"])
    inn.add_argument("--source-url", default=ndpc_registry.NIMP_URLS["dcmi"])

    fn = sub.add_parser("fetch-ndpc", help="scrape an NDPC NIMP table to CSV (experimental)")
    fn.add_argument("--list", default="dcmi", choices=list(ndpc_registry.NIMP_URLS))
    fn.add_argument("--out", default=str(ROOT / "data" / "ndpc_dcmi.csv"))

    r = sub.add_parser("run", help="crawl, analyse, match and score")
    r.add_argument("--limit", type=int)
    r.add_argument("--refresh", action="store_true")
    r.add_argument("--no-claude", action="store_true")
    r.add_argument("--sector")

    e = sub.add_parser("export", help="write leads to CSV")
    e.add_argument("--out", default=str(ROOT / "data" / "exports" / "leads.csv"))

    sub.add_parser("demo", help="load fictional demo data and score it offline")

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    db.init_db()

    with db.session() as s:
        if a.cmd == "init":
            print(f"Database ready at {settings.database_url}")
        elif a.cmd == "discover":
            source = a.source or ("google" if settings.google_places_api_key else "osm")
            new = 0
            if source == "google":
                from .sources import places

                found = places.discover(a.sectors, a.cities or list(settings.cities), a.pages)
                for pr in found:
                    _, created = pipeline.add_business(
                        s, name=pr.name, sector=pr.sector, subsector=pr.subsector, city=pr.city,
                        address=pr.address, website=pr.website, phone=pr.phone, source="google_places",
                        source_ref=pr.place_id, review_count=pr.review_count,
                    )
                    new += created
            else:
                from .sources import osm

                states = osm.resolve_states(a.cities)
                print(f"Querying OpenStreetMap for {len(states)} state(s) x {len(a.sectors)} sector(s). "
                      "All of Nigeria takes roughly 20-40 minutes. Results are saved as each step finishes.")
                found, failed = [], []
                for state, sector, batch, err in osm.discover_batches(
                    a.sectors, states, website_only=not a.include_no_website, progress=print
                ):
                    if err:
                        failed.append(f"{state} {sector}")
                        print(f"  could not get {state} {sector}: {err}")
                        continue
                    added = 0
                    for r in batch:
                        _, created = pipeline.add_business(
                            s, name=r.name, sector=r.sector, subsector=r.subsector, city=r.city,
                            address=r.address, website=r.website, phone=r.phone, source="openstreetmap",
                            source_ref=r.osm_id,
                        )
                        added += created
                    s.commit()
                    new += added
                    found.extend(batch)
                    print(f"  saved {added} new")
                if failed:
                    print("These steps failed because the OpenStreetMap servers were busy. Run each again later:")
                    for f in failed:
                        st, sec = f.rsplit(" ", 1)
                        print(f'  python -m prospect_intel discover --cities "{st}" --sectors {sec}')
            db.audit(s, "discover", f"{source}: {len(found)} results, {new} new")
            s.commit()
            print(f"{len(found)} results, {new} new businesses")
        elif a.cmd == "import-businesses":
            rows = csv_seed.read_rows(a.csv)
            new = 0
            for i, row in enumerate(rows):
                _, created = pipeline.add_business(
                    s, name=row["name"], sector=row["sector"].lower(), subsector=row.get("subsector") or None,
                    city=row.get("city") or None, address=row.get("address") or None,
                    website=row.get("website") or None, phone=row.get("phone") or None,
                    rc_number=row.get("rc_number") or None, source=f"csv:{Path(a.csv).name}", source_ref=None,
                )
                new += created
            db.audit(s, "import_businesses", f"{a.csv}: {len(rows)} rows, {new} new")
            s.commit()
            print(f"{len(rows)} rows, {new} new businesses")
        elif a.cmd == "import-ndpc":
            n = ndpc_registry.load_csv(s, a.csv, a.list, a.source_url)
            print(f"Loaded {n} {a.list} records")
        elif a.cmd == "fetch-ndpc":
            n = ndpc_registry.fetch_nimp(a.list, a.out)
            print(f"Saved {n} rows to {a.out}. Check it, then run import-ndpc.")
        elif a.cmd == "run":
            n = pipeline.run(s, limit=a.limit, refresh=a.refresh, use_claude=not a.no_claude, sector=a.sector)
            print(f"Scored {n} businesses")
        elif a.cmd == "export":
            from .export import leads_frame

            out = Path(a.out)
            out.parent.mkdir(parents=True, exist_ok=True)
            df = leads_frame(s)
            df.to_csv(out, index=False)
            print(f"Wrote {len(df)} leads to {out}")
        elif a.cmd == "demo":
            from .demo import load_demo

            n = load_demo(s)
            print(f"Demo: scored {n} fictional businesses. Run: streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()

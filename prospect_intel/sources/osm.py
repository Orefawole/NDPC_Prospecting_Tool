"""Discovery from OpenStreetMap through the free Overpass API. No API key needed.

Data (c) OpenStreetMap contributors, ODbL. Keep the attribution if you share
exports. Be gentle with the public Overpass servers: one query per sector and
city, with a pause between them.

OSM coverage in Nigeria is uneven: many entries have a name but no website, and
banks appear once per branch. We collapse branches into one business per brand
per city and, by default, keep only entries that list a website, since the
crawler needs one to collect evidence.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

import httpx

from ..config import settings
from ..util import domain_of, normalize_name

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# ISO 3166-2 codes for all 36 states and the FCT. Querying state by state
# keeps each Overpass request small enough to finish on the public servers.
STATE_AREAS = {
    "Abia": "NG-AB", "Adamawa": "NG-AD", "Akwa Ibom": "NG-AK", "Anambra": "NG-AN",
    "Bauchi": "NG-BA", "Bayelsa": "NG-BY", "Benue": "NG-BE", "Borno": "NG-BO",
    "Cross River": "NG-CR", "Delta": "NG-DE", "Ebonyi": "NG-EB", "Edo": "NG-ED",
    "Ekiti": "NG-EK", "Enugu": "NG-EN", "Abuja": "NG-FC", "Gombe": "NG-GO",
    "Imo": "NG-IM", "Jigawa": "NG-JI", "Kaduna": "NG-KD", "Kano": "NG-KN",
    "Katsina": "NG-KT", "Kebbi": "NG-KE", "Kogi": "NG-KO", "Kwara": "NG-KW",
    "Lagos": "NG-LA", "Nasarawa": "NG-NA", "Niger": "NG-NI", "Ogun": "NG-OG",
    "Ondo": "NG-ON", "Osun": "NG-OS", "Oyo": "NG-OY", "Plateau": "NG-PL",
    "Rivers": "NG-RI", "Sokoto": "NG-SO", "Taraba": "NG-TA", "Yobe": "NG-YO",
    "Zamfara": "NG-ZA",
}
ALIASES = {"fct": "Abuja", "federal capital territory": "Abuja", "port harcourt": "Rivers",
           "ibadan": "Oyo", "benin": "Edo", "benin city": "Edo", "calabar": "Cross River",
           "uyo": "Akwa Ibom", "owerri": "Imo", "jos": "Plateau", "ilorin": "Kwara",
           "abeokuta": "Ogun", "akure": "Ondo", "warri": "Delta", "asaba": "Delta"}


def resolve_states(names) -> list[str]:
    """None or ["all"] means every state. Accepts state names and big-city aliases."""
    if not names or [n.lower() for n in names] in (["all"], ["nigeria"]):
        return list(STATE_AREAS)
    lookup = {k.lower(): k for k in STATE_AREAS}
    out = []
    for n in names:
        key = n.strip().lower()
        state = lookup.get(key) or ALIASES.get(key) or lookup.get(key.removesuffix(" state"))
        if not state:
            raise ValueError(f"Unknown state '{n}'. Use a state name, e.g. Lagos, Rivers, Kano, or 'all'.")
        if state not in out:
            out.append(state)
    return out

# Overpass filters per sector
SECTOR_FILTERS = {
    "health": [
        '["amenity"="hospital"]',
        '["amenity"="clinic"]',
        '["amenity"="doctors"]',
        '["amenity"="pharmacy"]',
        '["healthcare"="laboratory"]',
        '["healthcare"="centre"]',
    ],
    "finance": [
        '["amenity"="bank"]',
        '["office"="financial"]',
        '["office"="financial_advisor"]',
        '["office"="company"]["name"~"microfinance|mfb|fintech|pay|capital|finance|asset management",i]',
    ],
    "insurance": [
        '["office"="insurance"]',
        '["name"~"insurance|assurance|HMO|health maintenance",i]["amenity"!~"hospital|clinic"]',
    ],
}


@dataclass
class OsmResult:
    osm_id: str
    name: str
    address: str | None
    website: str | None
    phone: str | None
    sector: str
    subsector: str
    city: str


def build_query(sector: str, iso: str, timeout: int = 120) -> str:
    parts = "".join(f"nwr{f}(area.a);" for f in SECTOR_FILTERS[sector])
    return f'[out:json][timeout:{timeout}];area["ISO3166-2"="{iso}"]->.a;({parts});out tags center;'


def subsector_for(sector: str, tags: dict) -> str:
    name = (tags.get("name") or "").lower()
    amenity = tags.get("amenity")
    if sector == "health":
        if amenity == "hospital":
            return "hospital"
        if amenity == "pharmacy":
            return "pharmacy"
        if tags.get("healthcare") == "laboratory" or re.search(r"diagnost|laborator|\blab\b|scan|imaging", name):
            return "diagnostic_lab"
        if re.search(r"fertility|ivf", name):
            return "fertility_clinic"
        if "hospital" in name:
            return "hospital"
        return "specialist_clinic"
    if sector == "finance":
        if re.search(r"microfinance|\bmfb\b", name):
            return "microfinance_bank"
        if "mortgage" in name:
            return "mortgage_bank"
        if amenity == "bank":
            return "commercial_bank"
        if re.search(r"pay|wallet|fintech", name):
            return "fintech"
        if re.search(r"asset|capital|invest|securities|pension", name):
            return "investment_firm"
        return "fintech"
    if sector == "insurance":
        if re.search(r"\bhmo\b|health maintenance", name):
            return "hmo"
        if "broker" in name:
            return "insurance_broker"
        return "insurer"
    return sector


def _address(tags: dict) -> str | None:
    bits = [tags.get(k) for k in ("addr:housenumber", "addr:street", "addr:suburb", "addr:city")]
    s = ", ".join(b for b in bits if b)
    return s or tags.get("addr:full")


def parse(data: dict, sector: str, city: str) -> list[OsmResult]:
    out = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("brand") or tags.get("operator")
        if not name:
            continue
        website = tags.get("website") or tags.get("contact:website") or tags.get("brand:website") or tags.get("url")
        if website and not website.startswith("http"):
            website = "https://" + website
        out.append(
            OsmResult(
                osm_id=f"osm:{el['type']}/{el['id']}",
                name=tags.get("brand") or name,
                address=_address(tags),
                website=website,
                phone=tags.get("phone") or tags.get("contact:phone"),
                sector=sector,
                subsector=subsector_for(sector, tags),
                city=city,
            )
        )
    return out


def collapse_branches(results: list[OsmResult]) -> list[OsmResult]:
    """One entry per brand (website domain, else normalized name) per state."""
    seen: dict[tuple, OsmResult] = {}
    for r in results:
        key = (r.city, domain_of(r.website) or normalize_name(r.name))
        if key not in seen or (not seen[key].website and r.website):
            seen[key] = r
    return list(seen.values())


def fetch(query: str, client: httpx.Client) -> dict:
    last = None
    for url in ENDPOINTS:
        try:
            r = client.post(url, data={"data": query})
            if r.status_code == 200:
                return r.json()
            last = f"{url} returned {r.status_code}"
        except httpx.HTTPError as e:
            last = f"{url}: {e}"
        time.sleep(5)
    raise RuntimeError(f"Overpass query failed ({last}). Try again in a few minutes.")


def discover(sectors=None, cities=None, website_only: bool = True,
             client: httpx.Client | None = None, pause: float = 5, progress=None) -> list[OsmResult]:
    """cities: state names (or big-city aliases); None or ["all"] covers all of Nigeria.
    Each result's `city` field holds the state name."""
    sectors = sectors or settings.sectors
    states = resolve_states(cities)
    own = client is None
    client = client or httpx.Client(timeout=180, headers={"User-Agent": settings.user_agent})
    results: list[OsmResult] = []
    try:
        for i, state in enumerate(states, 1):
            for sector in sectors:
                if progress:
                    progress(f"[{i}/{len(states)}] {state}: {sector}")
                try:
                    results.extend(parse(fetch(build_query(sector, STATE_AREAS[state]), client), sector, state))
                except RuntimeError as e:  # skip one failed query, keep the rest of the run
                    if progress:
                        progress(f"  skipped: {e}")
                time.sleep(pause)
    finally:
        if own:
            client.close()
    results = collapse_branches(results)
    if website_only:
        results = [r for r in results if r.website]
    return results

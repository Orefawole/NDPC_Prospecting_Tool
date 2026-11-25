"""Discovery through the Google Places API (Text Search, New).

Google's terms allow storing place IDs indefinitely, but other Places content
should be refreshed rather than kept long term. We store the place ID plus the
fields we need, and re-pull on each run.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from ..config import settings

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.websiteUri",
        "places.nationalPhoneNumber",
        "places.userRatingCount",
        "places.primaryType",
        "nextPageToken",
    ]
)

# (sector, subsector, search phrase). Subsectors line up with the NDPC
# Guidance Notice tier examples so the tier estimate has a starting point.
SECTOR_QUERIES: list[tuple[str, str, str]] = [
    ("finance", "commercial_bank", "commercial bank head office"),
    ("finance", "microfinance_bank", "microfinance bank"),
    ("finance", "mortgage_bank", "mortgage bank"),
    ("finance", "fintech", "fintech company"),
    ("finance", "payment_service", "payment service provider"),
    ("finance", "investment_firm", "asset management company"),
    ("health", "hospital", "hospital"),
    ("health", "specialist_clinic", "specialist clinic"),
    ("health", "fertility_clinic", "fertility clinic IVF"),
    ("health", "diagnostic_lab", "diagnostic centre medical laboratory"),
    ("health", "pharmacy", "pharmacy"),
    ("insurance", "insurer", "insurance company"),
    ("insurance", "hmo", "HMO health maintenance organisation"),
    ("insurance", "insurance_broker", "insurance broker"),
]


@dataclass
class PlaceResult:
    place_id: str
    name: str
    address: str | None
    website: str | None
    phone: str | None
    review_count: int | None
    sector: str
    subsector: str
    city: str


def search(query: str, city: str, sector: str, subsector: str, max_pages: int = 3,
           client: httpx.Client | None = None) -> list[PlaceResult]:
    if not settings.google_places_api_key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY is not set. Use: discover --source osm, or import-businesses your.csv")
    client = client or httpx.Client(timeout=30)
    headers = {
        "X-Goog-Api-Key": settings.google_places_api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body: dict = {"textQuery": f"{query} in {city}, Nigeria", "regionCode": "NG", "pageSize": 20}
    out: list[PlaceResult] = []
    for _ in range(max_pages):
        r = client.post(ENDPOINT, json=body, headers=headers)
        r.raise_for_status()
        data = r.json()
        for p in data.get("places", []):
            out.append(
                PlaceResult(
                    place_id=p["id"],
                    name=p.get("displayName", {}).get("text", ""),
                    address=p.get("formattedAddress"),
                    website=p.get("websiteUri"),
                    phone=p.get("nationalPhoneNumber"),
                    review_count=p.get("userRatingCount"),
                    sector=sector,
                    subsector=subsector,
                    city=city,
                )
            )
        token = data.get("nextPageToken")
        if not token:
            break
        body["pageToken"] = token
        time.sleep(2)  # page tokens need a moment to become valid
    return out


def discover(sectors=None, cities=None, max_pages: int = 1) -> list[PlaceResult]:
    sectors = set(sectors or settings.sectors)
    cities = cities or settings.cities
    results: list[PlaceResult] = []
    with httpx.Client(timeout=30) as client:
        for sector, subsector, phrase in SECTOR_QUERIES:
            if sector not in sectors:
                continue
            for city in cities:
                results.extend(search(phrase, city, sector, subsector, max_pages, client))
    return results

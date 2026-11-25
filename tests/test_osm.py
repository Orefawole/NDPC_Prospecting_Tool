import httpx

from prospect_intel.sources import osm

SAMPLE = {
    "elements": [
        {"type": "node", "id": 1, "tags": {"amenity": "bank", "name": "Acme Bank", "brand": "Acme Bank", "website": "https://acmebank.example"}},
        {"type": "node", "id": 2, "tags": {"amenity": "bank", "name": "Acme Bank Ikeja", "brand": "Acme Bank", "website": "acmebank.example"}},
        {"type": "way", "id": 3, "tags": {"amenity": "bank", "name": "Zuma Microfinance Bank", "contact:website": "https://zuma.example"}},
        {"type": "node", "id": 4, "tags": {"amenity": "bank", "name": "No Site Bank"}},
        {"type": "node", "id": 5, "tags": {"amenity": "bank"}},
    ]
}


def test_query_mentions_area_and_filters():
    q = osm.build_query("insurance", "NG-LA")
    assert '"ISO3166-2"="NG-LA"' in q and '"office"="insurance"' in q


def test_subsectors():
    assert osm.subsector_for("health", {"amenity": "pharmacy", "name": "X"}) == "pharmacy"
    assert osm.subsector_for("health", {"amenity": "clinic", "name": "Bright IVF Centre"}) == "fertility_clinic"
    assert osm.subsector_for("finance", {"amenity": "bank", "name": "Zuma MFB"}) == "microfinance_bank"
    assert osm.subsector_for("insurance", {"office": "insurance", "name": "Wellguard HMO"}) == "hmo"


def test_discover_collapses_branches_and_needs_website():
    def handler(req):
        return httpx.Response(200, json=SAMPLE)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    found = osm.discover(["finance"], ["Lagos"], client=client, pause=0)
    names = sorted(r.name for r in found)
    assert names == ["Acme Bank", "Zuma Microfinance Bank"]
    everything = osm.discover(["finance"], ["Lagos"], website_only=False, client=client, pause=0)
    assert "No Site Bank" in {r.name for r in everything}


def test_resolve_states():
    assert len(osm.resolve_states(None)) == 37
    assert len(osm.resolve_states(["all"])) == 37
    assert osm.resolve_states(["Port Harcourt", "lagos state", "FCT"]) == ["Rivers", "Lagos", "Abuja"]

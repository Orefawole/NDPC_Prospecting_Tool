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
    q = osm.build_query("insurance", "Lagos")
    assert '"ISO3166-2"="NG-LA"' in q and '"office"="insurance"' in q
    assert '"name"~"^Lagos( State)?$",i' in q and "map_to_area" in q
    assert "Federal Capital Territory" in osm.build_query("health", "Abuja")


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


def test_fetch_falls_back_and_retries():
    calls = []

    def handler(req):
        calls.append(req.url.host)
        if req.url.host == "a.example" or len(calls) < 3:
            return httpx.Response(502)
        return httpx.Response(200, json=SAMPLE)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    data = osm.fetch("q", client, ["https://a.example/api", "https://b.example/api"], waits=[0, 0])
    assert data == SAMPLE and calls == ["a.example", "b.example", "a.example", "b.example"]


def test_runtime_error_remark_counts_as_failure_and_batches_continue():
    def handler(req):
        if b"NG-LA" in req.content or b"NG%22%5D" in req.content and b"NG-LA" in req.content:
            return httpx.Response(200, json={"elements": [], "remark": "runtime error: Query timed out"})
        return httpx.Response(200, json=SAMPLE)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = list(osm.discover_batches(["finance"], ["Lagos", "Rivers"], client=client, pause=0,
                                    endpoints=["https://a.example/api"], waits=[0]))
    assert out[0][3] is not None and out[0][2] == []
    assert out[1][3] is None and len(out[1][2]) == 2

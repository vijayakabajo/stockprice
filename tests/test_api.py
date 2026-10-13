"""
The page API against the prototype's 13 sample stocks. Expected values are
the ones the prototype pages show.
"""

import pytest
from django.core.cache import cache

from core.cache import DATA_VERSION_KEY, bump_data_version

pytestmark = pytest.mark.usefixtures("prototype_stocks")


def get(client, url, status=200, **headers):
    response = client.get(url, headers=headers)
    assert response.status_code == status, response.content
    return response.json()["data"] if status == 200 else response


def tickers(rows):
    return [row["ticker"] for row in rows]


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------


def test_overview(client):
    data = get(client, "/api/v1/overview/")
    assert data["companies"] == 13
    assert round(data["total_market_cap"] / 1e9, 2) == 88.96
    # Nine real sectors; the ADR without a SIC code is "Not classified".
    assert data["sectors_covered"] == 9
    assert {e["slug"]: e["companies"] for e in data["by_exchange"]} == {"nasdaq": 8, "nyse": 5}
    assert {s["slug"]: s["companies"] for s in data["by_size"]} == {
        "large": 2,
        "mid": 5,
        "small": 3,
        "micro": 1,
        "nano": 2,
    }
    assert data["by_sector"][0]["slug"] == "blank-checks"
    assert data["by_sector"][-1]["slug"] == "not-classified"
    assert tickers(data["largest"]) == ["A", "AA", "AAOI", "AAL", "AAON", "AAMI"]
    assert data["as_of"]


# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------


def test_directory_defaults_to_largest_first_and_excludes_non_pages(client):
    data = get(client, "/api/v1/stocks/")
    assert data["count"] == 13  # no ETF, no delisted company
    assert data["results"][0]["ticker"] == "A"
    assert data["results"][-1]["ticker"] == "AAME"


@pytest.mark.parametrize(
    "query, expected",
    [
        ("exchange=nasdaq", 8),
        ("exchange=nyse", 5),
        ("type=spac", 4),
        ("type=adr", 1),
        ("sector=blank-checks", 4),
        ("sector=not-classified", 1),
        ("size=mid", 5),
        ("q=acquisition", 4),
        ("q=aal", 1),
        ("exchange=nasdaq&type=spac", 3),
    ],
)
def test_directory_filters(client, query, expected):
    assert get(client, f"/api/v1/stocks/?{query}")["count"] == expected


def test_directory_ordering_and_pages(client):
    data = get(client, "/api/v1/stocks/?ordering=ticker&page=2&page_size=5")
    assert tickers(data["results"]) == ["AACO", "AACP", "AADX", "AAL", "AAME"]
    assert data["num_pages"] == 3
    names = [r["display_name"] for r in get(client, "/api/v1/stocks/?ordering=name")["results"]]
    assert names == sorted(names, key=str.lower)


@pytest.mark.parametrize(
    "query, field",
    [
        ("exchange=lse", "exchange"),
        ("sector=nope", "sector"),
        ("type=etf", "type"),
        ("size=huge", "size"),
        ("ordering=price", "ordering"),
        ("page=abc", "page"),
    ],
)
def test_directory_rejects_unknown_values(client, query, field):
    response = get(client, f"/api/v1/stocks/?{query}", status=400)
    assert field in response.json()["errors"]


def test_directory_page_out_of_range(client):
    get(client, "/api/v1/stocks/?page=99", status=404)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def test_profile(client):
    data = get(client, "/api/v1/stocks/A/")
    assert data["display_name"] == "Agilent Technologies"
    assert data["security_type"] == "common"
    assert data["exchange"] == {"slug": "nyse", "name": "NYSE"}
    assert data["sector"] == {
        "slug": "laboratory-analytical-instruments",
        "name": "Laboratory Analytical Instruments",
    }
    assert data["size_bucket"] == "large"
    assert data["hq"] == "Santa Clara, CA"
    assert data["shares_outstanding"] == {"value": 281928854, "basis": "class"}
    assert data["edgar_url"].endswith("CIK=1090872")
    assert data["indexable"] is True
    assert data["as_of"]


def test_profile_variants(client):
    spac = get(client, "/api/v1/stocks/AACP/")
    assert (spac["security_type"], spac["indexable"]) == ("spac", False)
    assert spac["shares_outstanding"]["basis"] == "weighted"
    assert spac["website"] is None  # missing is null, never ""

    adr = get(client, "/api/v1/stocks/AACG/")
    assert adr["security_type"] == "adr"
    assert adr["sector"] == {"slug": "not-classified", "name": "Not classified"}


def test_profile_lookup_rules(client):
    assert get(client, "/api/v1/stocks/aal/")["ticker"] == "AAL"
    get(client, "/api/v1/stocks/SPYX/", status=404)  # ETFs have no page
    get(client, "/api/v1/stocks/NOPE/", status=404)
    gone = get(client, "/api/v1/stocks/GONE/")  # delisted: page kept, not indexed
    assert (gone["active"], gone["indexable"]) == (False, False)


def test_dotted_ticker(client, prototype_stocks):
    from market.models import Stock

    Stock.objects.create(
        ticker="BRK.A", name="Berkshire Hathaway Inc.", asset_type="CS", primary_exchange="XNYS"
    )
    assert get(client, "/api/v1/stocks/brk.a/")["ticker"] == "BRK.A"


def test_peers(client):
    data = get(client, "/api/v1/stocks/AAL/peers/")
    assert data["rank"] == 4 and data["ranked_total"] == 13
    assert tickers(data["context"]) == ["A", "AA", "AAOI", "AAL", "AAON"]
    # AAL is alone in its sector, so peers come from its exchange.
    assert tickers(data["peers"]) == ["AAOI", "AAON", "AACI", "AACO", "AACP"]
    assert len(data["related"]) == 3 and "AAL" not in tickers(data["related"])


def test_peers_for_small_stock_and_spac(client):
    data = get(client, "/api/v1/stocks/AACP/peers/")
    assert data["peers"] == []  # SPACs have no business to compare
    assert tickers(data["context"])[-1] == "AACP"  # appended after the top five
    assert tickers(data["related"]) == ["AAC", "AACI", "AACO"]


# ---------------------------------------------------------------------------
# Hubs
# ---------------------------------------------------------------------------


def test_sectors(client):
    results = get(client, "/api/v1/sectors/")["results"]
    first = results[0]
    assert (first["slug"], first["companies"], first["indexable"]) == ("blank-checks", 4, True)
    assert round(first["total_market_cap"] / 1e9, 2) == 1.39
    singles = [s for s in results if s["companies"] == 1]
    assert singles and not any(s["indexable"] for s in singles)


def test_sector_hub(client):
    data = get(client, "/api/v1/sectors/blank-checks/")
    assert (data["name"], data["sic_code"], data["companies"]) == ("Blank Checks", "6770", 4)
    assert data["total_employees"] is None
    assert round(data["average_market_cap"] / 1e6, 1) == 347.4
    assert tickers(data["largest"]) == ["AAC", "AACI", "AACO", "AACP"]
    assert get(client, "/api/v1/sectors/not-classified/")["companies"] == 1
    get(client, "/api/v1/sectors/nope/", status=404)


def test_exchanges(client):
    results = get(client, "/api/v1/exchanges/")["results"]
    assert [(e["slug"], e["companies"]) for e in results] == [("nasdaq", 8), ("nyse", 5)]
    hub = get(client, "/api/v1/exchanges/nasdaq/")
    assert hub["total_employees"] == 154633
    assert round(hub["total_market_cap"] / 1e9, 2) == 25.46
    get(client, "/api/v1/exchanges/nyse-arca/")  # exists, just has no page stocks
    get(client, "/api/v1/exchanges/lse/", status=404)


# ---------------------------------------------------------------------------
# Search and sitemap
# ---------------------------------------------------------------------------


def test_search_ranks_exact_ticker_first(client):
    assert tickers(get(client, "/api/v1/search/?q=a")["results"])[0] == "A"
    assert tickers(get(client, "/api/v1/search/?q=AAL")["results"]) == ["AAL"]
    assert tickers(get(client, "/api/v1/search/?q=apogee")["results"]) == ["AACP"]
    assert get(client, "/api/v1/search/?q=ETF")["results"] == []
    get(client, "/api/v1/search/?q=", status=400)


def test_sitemap_lists_only_indexable_pages(client):
    data = get(client, "/api/v1/sitemap/")
    listed = {s["ticker"] for s in data["stocks"]}
    assert "AACP" not in listed and "GONE" not in listed and "SPYX" not in listed
    assert {"A", "AACG"} <= listed
    assert [s["slug"] for s in data["sectors"]] == ["blank-checks"]
    assert {e["slug"] for e in data["exchanges"]} == {"nasdaq", "nyse"}


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def test_responses_are_cached_until_the_data_version_changes(client, prototype_stocks):
    from market.models import Stock

    before = get(client, "/api/v1/stocks/A/")
    Stock.objects.filter(ticker="A").update(total_employees=1)
    assert get(client, "/api/v1/stocks/A/") == before  # served from cache

    bump_data_version()
    assert get(client, "/api/v1/stocks/A/")["total_employees"] == 1


def test_etag_and_not_modified(client):
    first = client.get("/api/v1/overview/")
    assert first["Cache-Control"] == "public, max-age=300"
    again = client.get("/api/v1/overview/", headers={"If-None-Match": first["ETag"]})
    assert again.status_code == 304 and again.content == b""


def test_successful_sync_bumps_data_version():
    from sync.models import DataSyncJob
    from sync.services import tracked_job

    version = cache.get(DATA_VERSION_KEY)
    with tracked_job(DataSyncJob.JobType.SECTORS):
        pass
    assert cache.get(DATA_VERSION_KEY) != version


def test_api_needs_no_login_and_is_read_only(client):
    assert client.post("/api/v1/stocks/").status_code == 405

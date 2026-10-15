"""
The server-rendered site against the prototype's 13 sample stocks.

These check what crawlers depend on: complete HTML without JavaScript, one
H1, unique metadata within length limits, valid JSON-LD, canonical and
robots rules that match the sitemap, and crawler files.
"""

import json
import re
from html import unescape
from unittest import mock

import pytest
from django.core.cache import cache

from core.cache import bump_data_version
from web import indexnow, seo

pytestmark = pytest.mark.usefixtures("prototype_stocks")

PAGES = [
    "/",
    "/stocks/",
    "/stocks/a/",
    "/stocks/aacg/",
    "/stocks/aacp/",
    "/sectors/",
    "/sectors/blank-checks/",
    "/exchanges/",
    "/exchanges/nasdaq/",
    "/guides/",
    "/guides/what-is-market-cap/",
    "/guides/what-is-a-spac/",
    "/guides/what-is-an-adr/",
    "/glossary/",
    "/about/",
]


def html(client, url, status=200):
    response = client.get(url)
    assert response.status_code == status, (url, response.status_code)
    return response.content.decode()


def meta(page, name):
    match = re.search(rf'<meta (?:name|property)="{name}" content="([^"]*)"', page)
    return match.group(1) if match else None


def canonical(page):
    match = re.search(r'<link rel="canonical" href="([^"]+)"', page)
    return unescape(match.group(1)) if match else None


def jsonld(page):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    assert len(blocks) <= 1
    return json.loads(blocks[0]) if blocks else None


def graph_types(page):
    return {node["@type"] for node in jsonld(page)["@graph"]}


# ---------------------------------------------------------------------------
# Every page
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", PAGES)
def test_page_basics(client, url):
    page = html(client, url)
    assert '<html lang="en">' in page
    assert page.count("<h1") == 1
    assert '<meta name="viewport" content="width=device-width, initial-scale=1">' in page
    title = re.search(r"<title>(.*?)</title>", page).group(1)
    assert 0 < len(title) <= seo.TITLE_MAX, title
    assert 0 < len(meta(page, "description")) <= seo.DESCRIPTION_MAX
    assert canonical(page) == f"https://example.test{url}"
    assert meta(page, "og:title") and meta(page, "og:image").startswith("https://example.test/static/")
    assert meta(page, "twitter:card") == "summary_large_image"
    assert jsonld(page)["@context"] == "https://schema.org"
    # Every image declares its size, so nothing shifts as it loads.
    for img in re.findall(r"<img [^>]+>", page):
        assert 'width="' in img and 'height="' in img and 'alt="' in img
    # The only scripts are deferred, apart from the inline theme snippet and JSON-LD.
    for script in re.findall(r"<script[^>]*src=[^>]*>", page):
        assert " defer" in script


def test_titles_and_descriptions_are_unique(client):
    pages = [html(client, url) for url in PAGES]
    titles = [re.search(r"<title>(.*?)</title>", p).group(1) for p in pages]
    descriptions = [meta(p, "description") for p in pages]
    assert len(set(titles)) == len(titles)
    assert len(set(descriptions)) == len(descriptions)


# ---------------------------------------------------------------------------
# Stock profile
# ---------------------------------------------------------------------------


def test_profile_content_is_in_the_html(client, prototype_stocks):
    page = html(client, "/stocks/a/")
    agilent = prototype_stocks["A"]
    assert "Agilent Technologies (A) stock profile" in page
    assert agilent.description[:80] in page
    # Answers are visible text, not behind an accordion.
    assert "<details" not in page
    assert "<h3>What is Agilent Technologies&#x27;s market cap?</h3>" in page
    assert "Published" in page and "Last updated" in page
    assert "Research Desk" in page
    assert meta(page, "robots").startswith("index")
    assert {"WebPage", "Corporation", "FAQPage", "BreadcrumbList"} <= graph_types(page)
    assert 'target="_blank" rel="noopener"' in page


def test_profile_structured_data(client):
    nodes = {n["@type"]: n for n in jsonld(html(client, "/stocks/a/"))["@graph"]}
    company = nodes["Corporation"]
    assert company["tickerSymbol"] == "NYSE A"
    assert company["numberOfEmployees"]["value"] == 18200
    assert {"propertyID": "CIK", "value": "1090872", "@type": "PropertyValue"} in company["identifier"]
    page = nodes["WebPage"]
    assert page["datePublished"] and page["dateModified"]
    assert page["author"]["name"] == "Research Desk"
    crumbs = [item["name"] for item in nodes["BreadcrumbList"]["itemListElement"]]
    assert crumbs == ["Home", "Stocks", "Laboratory Analytical Instruments", "A"]
    faq = nodes["FAQPage"]["mainEntity"]
    assert all(q["acceptedAnswer"]["text"] for q in faq)


def test_spac_and_adr_variants(client):
    spac = html(client, "/stocks/aacp/")
    assert meta(spac, "robots") == seo.NOINDEX
    assert "Pre-merger shell." in spac
    assert 'id="peers"' not in spac

    adr = html(client, "/stocks/aacg/")
    assert meta(adr, "robots").startswith("index")
    assert "U.S.-listed ADR." in adr


def test_inactive_stock_keeps_a_noindexed_page(client):
    page = html(client, "/stocks/gone/")
    assert meta(page, "robots") == seo.NOINDEX
    assert "No longer listed." in page


def test_profile_urls_are_lowercase(client):
    response = client.get("/stocks/A/")
    assert response.status_code == 301
    assert response["Location"] == "/stocks/a/"


def test_profile_404s(client):
    html(client, "/stocks/nope/", status=404)
    html(client, "/stocks/spyx/", status=404)  # ETFs have no page


def test_jsonld_cannot_break_out_of_its_script_tag(client, prototype_stocks):
    stock = prototype_stocks["AAL"]
    stock.description = "Flies planes.</script><script>alert(1)</script>"
    stock.save(update_fields=["description"])
    page = html(client, "/stocks/aal/")
    data = jsonld(page)
    assert "</script>" in next(n for n in data["@graph"] if n["@type"] == "Corporation")["description"]
    assert "<script>alert(1)" not in page


# ---------------------------------------------------------------------------
# Directory and hubs
# ---------------------------------------------------------------------------


def test_directory_lists_every_company_with_real_links(client):
    page = html(client, "/stocks/")
    assert meta(page, "robots").startswith("index")
    assert page.count('class="co" href="/stocks/') == 13
    assert "<table" in page and "<caption" in page


def test_filtered_directory_is_noindexed(client):
    page = html(client, "/stocks/?exchange=nasdaq&type=spac")
    assert meta(page, "robots") == seo.NOINDEX
    assert canonical(page) == "https://example.test/stocks/?exchange=nasdaq&type=spac"
    assert page.count('class="co" href="/stocks/') == 3


def test_directory_unknown_filter_is_404(client):
    html(client, "/stocks/?sector=nope", status=404)
    html(client, "/stocks/?page=99", status=404)


def test_pagination_keeps_filters_but_never_stray_parameters(client, settings):
    with mock.patch("market.queries.DEFAULT_PAGE_SIZE", 5):
        page = html(client, "/stocks/?exchange=nasdaq&utm_source=newsletter")
    assert 'href="/stocks/?exchange=nasdaq&amp;page=2" rel="next"' in page
    assert "utm_source" not in page


def test_sector_hub(client):
    page = html(client, "/sectors/blank-checks/")
    assert "Blank Checks stocks" in page
    assert "4 U.S.-listed companies are classified under Blank Checks" in page
    assert {"CollectionPage", "ItemList", "FAQPage", "BreadcrumbList"} <= graph_types(page)


def test_thin_hub_is_noindexed(client):
    page = html(client, "/sectors/life-insurance/")
    assert meta(page, "robots") == seo.NOINDEX


def test_search(client):
    response = client.get("/search/?q=AAL")
    assert response.status_code == 302 and response["Location"] == "/stocks/aal/"
    page = html(client, "/search/?q=acquisition")
    assert meta(page, "robots") == seo.NOINDEX
    assert "/stocks/aac/" in page


# ---------------------------------------------------------------------------
# Crawler files
# ---------------------------------------------------------------------------


def test_robots_txt_names_every_crawler(client):
    text = html(client, "/robots.txt")
    for bot in [
        "Googlebot",
        "Bingbot",
        "GPTBot",
        "OAI-SearchBot",
        "ChatGPT-User",
        "ClaudeBot",
        "Claude-SearchBot",
        "PerplexityBot",
        "Google-Extended",
    ]:
        assert re.search(rf"User-agent: {bot}\nAllow: /\n", text), bot
    assert "Sitemap: https://example.test/sitemap.xml" in text
    assert "Disallow: /api/" in text


def test_sitemap_lists_only_indexable_pages(client):
    index = html(client, "/sitemap.xml")
    assert "<loc>https://example.test/sitemap-stocks.xml</loc>" in index
    assert "<lastmod>" in index

    stocks = html(client, "/sitemap-stocks.xml")
    locs = re.findall(r"<loc>(.*?)</loc>", stocks)
    assert "https://example.test/stocks/a/" in locs
    assert "https://example.test/stocks/aacg/" in locs  # ADRs are indexed
    assert not any(t in loc for loc in locs for t in ("/aacp/", "/aac/", "/gone/", "/spyx/"))
    assert "<lastmod>" in stocks

    sectors = html(client, "/sitemap-sectors.xml")
    assert "/sectors/blank-checks/" in sectors
    assert "/sectors/life-insurance/" not in sectors

    guides = html(client, "/sitemap-guides.xml")
    assert "/guides/what-is-market-cap/" in guides


def test_llms_txt(client):
    response = client.get("/llms.txt")
    assert response["Content-Type"].startswith("text/markdown")
    text = response.content.decode()
    assert text.startswith("# Equity Profiles")
    assert "https://example.test/stocks/" in text


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def test_pages_are_cached_until_the_data_version_changes(client, prototype_stocks):
    assert "Agilent Technologies" in html(client, "/stocks/a/")
    stock = prototype_stocks["A"]
    stock.display_name = "Renamed Co"
    stock.save(update_fields=["display_name"])
    assert "Renamed Co" not in html(client, "/stocks/a/")
    bump_data_version()
    assert "Renamed Co" in html(client, "/stocks/a/")


def test_page_etag_and_not_modified(client):
    response = client.get("/sectors/")
    assert response["Cache-Control"] == "public, max-age=300"
    again = client.get("/sectors/", headers={"If-None-Match": f'W/{response["ETag"]}'})
    assert again.status_code == 304


def test_unlisted_query_parameters_do_not_create_cache_entries(client):
    client.get("/glossary/")
    before = len(cache._cache)
    client.get("/glossary/?utm_source=a")
    client.get("/glossary/?utm_source=b")
    assert len(cache._cache) == before


# ---------------------------------------------------------------------------
# IndexNow
# ---------------------------------------------------------------------------


def test_indexnow_key_file_only_exists_with_a_key(client):
    html(client, "/abc123key.txt", status=404)


def test_indexnow_disabled_submits_nothing(settings):
    settings.INDEXNOW_ENABLED = False
    with mock.patch("web.indexnow.requests.post") as post:
        assert indexnow.submit(["https://example.test/stocks/a/"]) == 0
    post.assert_not_called()


def test_indexnow_submits_changed_profiles_in_batches(settings):
    settings.INDEXNOW_ENABLED = True
    settings.INDEXNOW_KEY = "abc123key"
    urls = indexnow.stock_urls()
    assert "https://example.test/stocks/a/" in urls
    assert "https://example.test/stocks/aacp/" not in urls  # SPACs are not indexed

    with mock.patch("web.indexnow.BATCH_SIZE", 4), mock.patch("web.indexnow.requests.post") as post:
        post.return_value.status_code = 202
        assert indexnow.submit(urls) == len(urls)
    assert post.call_count == -(-len(urls) // 4)
    body = post.call_args.kwargs["json"]
    assert body["host"] == "example.test"
    assert body["key"] == "abc123key"
    assert body["keyLocation"] == "https://example.test/abc123key.txt"


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------


def test_fit_title_prefers_the_longest_candidate_that_fits():
    assert seo.fit_title("Short") == "Short | Equity Profiles"
    long = "A" * 50
    assert seo.fit_title(long, "Medium title") == "Medium title | Equity Profiles"
    assert len(seo.fit_title("word " * 30)) <= seo.TITLE_MAX


def test_fit_description_keeps_whole_sentences():
    text = seo.fit_description("First sentence.", "x" * 200)
    assert text == "First sentence."
    assert len(seo.fit_description("word " * 80)) <= seo.DESCRIPTION_MAX

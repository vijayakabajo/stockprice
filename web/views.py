"""
The public site. Every page is rendered on the server, complete, in the first
response: crawlers that run no JavaScript (GPTBot, ClaudeBot, PerplexityBot)
see exactly what a reader sees. JavaScript only enhances (search suggestions,
theme toggle).

Data comes from market.payloads, the same builders the JSON API uses. Pages
are cached per data version and release (core.cache.cache_html).
"""

from django.conf import settings
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_safe
from rest_framework.exceptions import APIException

from core.cache import cache_html
from market import payloads, queries
from market.lookups import reference_as_of
from web import content, seo
from web.copy import home_faqs, hub_copy, profile_copy
from web.formatting import cap, human_date, size_label

DIRECTORY_FILTERS = ("exchange", "type", "sector", "size", "ordering", "q")
ORDERING_LABELS = {
    "-market_cap": "Market cap, high to low",
    "name": "Name, A to Z",
    "ticker": "Ticker, A to Z",
    "-employees": "Employees, high to low",
}
TYPE_FILTERS = {"common": "Common stock", "adr": "ADR", "spac": "SPAC"}


def _or_404(builder, *args):
    """Payload lookups raise DRF errors for the API; on the site they are 404s."""
    try:
        return builder(*args)
    except APIException:
        raise Http404 from None


def _page_number(request):
    try:
        return max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        raise Http404 from None


def _max_cap(rows):
    return max((r["market_cap"] or 0 for r in rows), default=0)


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------


@require_safe
@cache_html()
def home(request):
    overview = payloads.overview()
    faqs = home_faqs(overview, settings.SITE_NAME)
    meta = seo.PageMeta(
        title=seo.fit_title(
            f"{settings.SITE_NAME}: U.S. Stock Profiles, Answer First", "U.S. Stock Profiles"
        ),
        description=seo.fit_description(
            f"Answer-first profiles of {overview['companies']:,} U.S.-listed companies.",
            "Market cap, sector, exchange, headcount, identifiers and SEC filings, every figure dated and sourced.",
        ),
        path="/",
        modified=reference_as_of(),
    )
    meta.graph = [
        seo.organization(),
        seo.website(),
        seo.web_page(meta, about={"@id": seo.absolute(seo.ORG_ID)}),
        seo.faq_page(meta, faqs),
    ]
    return render(
        request,
        "pages/home.html",
        {
            "page": meta,
            "overview": overview,
            "max_cap": _max_cap(overview["largest"]),
            "faqs": faqs,
            "guides": content.GUIDES,
        },
    )


# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------


@require_safe
@cache_html(params=DIRECTORY_FILTERS + ("page",))
def directory(request):
    filters = {k: request.GET.get(k, "").strip() for k in DIRECTORY_FILTERS}
    if filters["ordering"] == queries.DEFAULT_ORDERING:
        filters["ordering"] = ""
    filters = {k: v for k, v in filters.items() if v}
    page_number = _page_number(request)
    data = _or_404(payloads.directory, {**filters, "page": page_number})

    sectors = payloads.sector_list()["results"]
    exchanges = payloads.exchange_list()["results"]
    label = _filter_label(filters, sectors, exchanges)
    as_of = human_date(data["as_of"])

    heading = f"{label}" if label else "U.S. stock directory"
    page_suffix = f", page {page_number}" if page_number > 1 else ""
    meta = seo.PageMeta(
        title=seo.fit_title(
            f"{label or 'U.S. Stock Directory'}: All Listed Companies by Market Cap{page_suffix}",
            f"{label or 'U.S. Stock Directory'} by Market Cap{page_suffix}",
            f"{label or 'U.S. Stock Directory'}{page_suffix}",
        ),
        description=seo.fit_description(
            f"Browse {data['count']:,} {label.lower() if label else 'U.S.-listed companies'} ranked by market cap.",
            "Filter by exchange, sector, security type and size, with every figure dated",
            f"as of {as_of}.",
        ),
        path=_query_path(
            reverse("web:directory"), {**filters, "page": page_number if page_number > 1 else ""}
        ),
        # Filtered and searched views are for readers; the unfiltered pages
        # already link every company, so only those are indexed.
        robots=seo.NOINDEX if filters else seo.INDEX,
        modified=data["as_of"],
        breadcrumbs=[("Stocks", reverse("web:directory"))],
    )
    meta.graph = [seo.web_page(meta, page_type="CollectionPage")]
    return render(
        request,
        "pages/directory.html",
        {
            "page": meta,
            "heading": heading,
            "data": data,
            "filters": filters,
            "max_cap": _max_cap(data["results"]),
            "sectors": sectors,
            "exchanges": exchanges,
            "sizes": [(b, size_label(b)) for b in ("mega", "large", "mid", "small", "micro", "nano")],
            "types": TYPE_FILTERS.items(),
            "orderings": ORDERING_LABELS.items(),
            "overview": payloads.overview(),
        },
    )


def _filter_label(filters, sectors, exchanges):
    parts = []
    if size := filters.get("size"):
        parts.append(size_label(size))
    if slug := filters.get("sector"):
        parts.append(next((s["name"] for s in sectors if s["slug"] == slug), slug))
    if type_ := filters.get("type"):
        parts.append({"common": "common", "adr": "ADR", "spac": "SPAC"}.get(type_, type_))
    label = " ".join(parts + ["stocks"]) if parts else ""
    if slug := filters.get("exchange"):
        name = next((e["name"] for e in exchanges if e["slug"] == slug), slug)
        label = f"{label or 'Stocks'} on {name}"
    if q := filters.get("q"):
        label = f"{label or 'Stocks'} matching “{q}”"
    return label[:1].upper() + label[1:]


def _query_path(path, params):
    query = QueryDict(mutable=True)
    for key, value in params.items():
        if value:
            query[key] = value
    encoded = query.urlencode()
    return f"{path}?{encoded}" if encoded else path


# ---------------------------------------------------------------------------
# Stock profile
# ---------------------------------------------------------------------------


@require_safe
@cache_html()
def stock(request, ticker):
    # One URL per company: /stocks/brk.b/, never /stocks/BRK.B/.
    if ticker != ticker.lower():
        return redirect("web:stock", ticker=ticker.lower(), permanent=True)
    instance = _or_404(payloads.page_stock, ticker)
    profile = payloads.profile(instance)
    peers = payloads.peers(instance)
    copy = profile_copy(profile, peers)
    name, symbol = copy["name"], profile["ticker"]
    sector = profile["sector"]
    as_of = human_date(profile["as_of"])

    crumbs = [("Stocks", reverse("web:directory"))]
    if sector:
        crumbs.append((sector["name"], reverse("web:sector", kwargs={"slug": sector["slug"]})))
    crumbs.append((symbol, reverse("web:stock", kwargs={"ticker": ticker})))

    meta = seo.PageMeta(
        title=seo.fit_title(
            f"{name} ({symbol}) Stock: Market Cap, Sector & Key Facts",
            f"{name} ({symbol}) Stock Profile & Key Facts",
            f"{name} ({symbol}) Stock Profile",
            f"{symbol} Stock Profile",
        ),
        description=seo.fit_description(
            copy["lead"],
            f"Market cap {cap(profile['market_cap'])} as of {as_of}." if profile["market_cap"] else "",
            "Key facts, peers, identifiers and SEC filings.",
        ),
        path=reverse("web:stock", kwargs={"ticker": ticker}),
        robots=seo.INDEX if profile["indexable"] else seo.NOINDEX,
        og_type="article",
        published=instance.created_at,
        modified=profile["as_of"],
        breadcrumbs=crumbs,
    )
    company = seo.corporation(profile, meta.canonical)
    meta.graph = [
        seo.web_page(
            meta,
            author=content.DEFAULT_AUTHOR,
            about={"@id": company["@id"]},
            main_entity={"@id": company["@id"]},
        ),
        company,
        seo.faq_page(meta, copy["faqs"]),
    ]

    toc = [("overview", f"What is {name}?"), ("business", "What it does"), ("facts", "Key facts")]
    if profile["market_cap"] is not None:
        toc.append(("market-cap", "Market cap"))
    if peers["peers"]:
        toc.append(("peers", "Peers"))
    toc += [
        ("identifiers", "Identifiers"),
        ("financials", "Financials"),
        ("sector", "Sector"),
        ("terms", "Key terms"),
        ("faq", "FAQ"),
        ("sources", "Sources"),
    ]
    return render(
        request,
        "pages/stock.html",
        {
            "page": meta,
            "p": profile,
            "peers": peers,
            "copy": copy,
            "toc": toc,
            "context_max": _max_cap(peers["context"]),
            "author": content.DEFAULT_AUTHOR,
            "terms": [
                content.GLOSSARY_BY_SLUG[s] for s in content.PROFILE_TERMS.get(profile["security_type"], [])
            ],
            "sector_primer": _sector_primer(profile),
        },
    )


def _sector_primer(profile):
    sector = profile["sector"]
    if not sector or sector["slug"] == "not-classified":
        return None
    hub = payloads.sector_hub(sector["slug"])
    return hub["primer"] or (
        f"Companies classified under {sector['name']} share SIC code {hub['sic_code']}, which the SEC "
        f"assigns by a company's main line of business. {hub['companies']:,} U.S.-listed companies carry "
        f"this code, with a combined market cap of {cap(hub['total_market_cap'])}."
    )


# ---------------------------------------------------------------------------
# Sectors and exchanges
# ---------------------------------------------------------------------------


@require_safe
@cache_html()
def sector_index(request):
    data = payloads.sector_list()
    sectors = data["results"]
    classified = [s for s in sectors if s["slug"] != "not-classified"]
    meta = seo.PageMeta(
        title=seo.fit_title("U.S. Stocks by Sector: Every SIC Industry Ranked", "U.S. Stocks by Sector"),
        description=seo.fit_description(
            f"Browse {len(classified):,} industry sectors of U.S.-listed stocks, each with its company count and "
            f"combined market cap, as of {human_date(data['as_of'])}.",
        ),
        path=reverse("web:sectors"),
        modified=data["as_of"],
        breadcrumbs=[("Sectors", reverse("web:sectors"))],
    )
    meta.graph = [seo.web_page(meta, page_type="CollectionPage")]
    return render(
        request,
        "pages/sector_index.html",
        {
            "page": meta,
            "data": data,
            "sectors": sectors,
            "classified": len(classified),
            "max_cap": max((s["total_market_cap"] or 0 for s in sectors), default=0),
        },
    )


@require_safe
@cache_html()
def exchange_index(request):
    data = payloads.exchange_list()
    meta = seo.PageMeta(
        title=seo.fit_title("U.S. Stock Exchanges: Listings and Market Cap", "U.S. Stock Exchanges"),
        description=seo.fit_description(
            f"Every U.S. stock exchange we track, with its number of listed companies and their combined market "
            f"cap, as of {human_date(data['as_of'])}.",
        ),
        path=reverse("web:exchanges"),
        modified=data["as_of"],
        breadcrumbs=[("Exchanges", reverse("web:exchanges"))],
    )
    meta.graph = [seo.web_page(meta, page_type="CollectionPage")]
    return render(request, "pages/exchange_index.html", {"page": meta, "data": data})


@require_safe
@cache_html(params=("page",))
def sector_hub(request, slug):
    return _hub(request, "sector", slug)


@require_safe
@cache_html(params=("page",))
def exchange_hub(request, slug):
    return _hub(request, "exchange", slug)


def _hub(request, kind, slug):
    hub = _or_404(payloads.sector_hub if kind == "sector" else payloads.exchange_hub, slug)
    page_number = _page_number(request)
    companies = _or_404(payloads.directory, {kind: slug, "page": page_number})
    copy = hub_copy(hub, kind)
    name = hub["name"]
    index_name, index_url = (
        ("Sectors", reverse("web:sectors")) if kind == "sector" else ("Exchanges", reverse("web:exchanges"))
    )
    path = reverse(f"web:{kind}", kwargs={"slug": slug})
    page_suffix = f", Page {page_number}" if page_number > 1 else ""

    if kind == "sector":
        titles = (
            f"{name} Stocks: {hub['companies']:,} U.S. Companies by Market Cap{page_suffix}",
            f"{name} Stocks by Market Cap{page_suffix}",
            f"{name} Stocks{page_suffix}",
        )
    else:
        titles = (
            f"Stocks Listed on {name}: {hub['companies']:,} Companies by Market Cap{page_suffix}",
            f"{name} Stocks by Market Cap{page_suffix}",
            f"{name} Stocks{page_suffix}",
        )
    meta = seo.PageMeta(
        title=seo.fit_title(*titles),
        description=seo.fit_description(
            copy["lead"], "Ranked list, combined and average market cap, and headcount."
        ),
        path=_query_path(path, {"page": page_number if page_number > 1 else ""}),
        robots=seo.INDEX if hub["indexable"] else seo.NOINDEX,
        modified=hub["as_of"],
        breadcrumbs=[(index_name, index_url), (name, path)],
    )
    meta.graph = [
        seo.web_page(meta, page_type="CollectionPage"),
        seo.item_list(
            f"Largest {copy['subject']} by market cap",
            hub["largest"],
            lambda t: reverse("web:stock", kwargs={"ticker": t.lower()}),
        ),
        seo.faq_page(meta, copy["faqs"]),
    ]
    primer = hub.get("primer") or (
        f"Companies classified under {name} share SIC code {hub['sic_code']}, which the SEC assigns by a "
        f"company's main line of business."
        if kind == "sector" and hub.get("sic_code")
        else None
    )
    return render(
        request,
        "pages/hub.html",
        {
            "page": meta,
            "kind": kind,
            "hub": hub,
            "copy": copy,
            "primer": primer,
            "companies": companies,
            "filters": {},
            "max_cap": _max_cap(hub["largest"]),
            "index_name": index_name,
            "index_url": index_url,
        },
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@require_safe
@cache_html(params=("q",))
def search(request):
    query = request.GET.get("q", "").strip()
    results = payloads.search(query)["results"] if query else []
    # A ticker typed exactly goes straight to its page.
    if results and results[0]["ticker"].lower() == query.lower():
        return redirect("web:stock", ticker=results[0]["ticker"].lower())
    meta = seo.PageMeta(
        title=seo.fit_title(f"Search results for “{query[:30]}”" if query else "Search U.S. stocks"),
        description="Search U.S.-listed companies by ticker symbol or company name.",
        path=_query_path(reverse("web:search"), {"q": query}),
        robots=seo.NOINDEX,
    )
    return render(request, "pages/search.html", {"page": meta, "query": query, "results": results})


# ---------------------------------------------------------------------------
# Editorial pages
# ---------------------------------------------------------------------------


@require_safe
@cache_html()
def glossary(request):
    meta = seo.PageMeta(
        title=seo.fit_title("Stock Market Glossary: Key Terms, Plainly Defined", "Stock Market Glossary"),
        description=seo.fit_description(
            "Plain definitions of the terms on every company profile: market cap, shares outstanding, SIC code, "
            "CIK, FIGI, round lot, ADR, SPAC and more.",
        ),
        path=reverse("web:glossary"),
        breadcrumbs=[("Glossary", reverse("web:glossary"))],
    )
    meta.graph = [seo.web_page(meta), seo.defined_term_set(meta, content.GLOSSARY)]
    return render(request, "pages/glossary.html", {"page": meta, "terms": content.GLOSSARY})


@require_safe
@cache_html()
def about(request):
    meta = seo.PageMeta(
        title=seo.fit_title(
            f"About {settings.SITE_NAME}: Data, Methods and Editors", f"About {settings.SITE_NAME}"
        ),
        description=seo.fit_description(
            f"How {settings.SITE_NAME} builds its company profiles: where the data comes from, how often it is "
            "refreshed, how companies are classified and who reviews it.",
        ),
        path=reverse("web:about"),
        breadcrumbs=[("About", reverse("web:about"))],
    )
    meta.graph = [
        seo.organization(),
        seo.web_page(meta, page_type="AboutPage", about={"@id": seo.absolute(seo.ORG_ID)}),
    ]
    return render(
        request,
        "pages/about.html",
        {
            "page": meta,
            "authors": content.AUTHORS.values(),
            "as_of": payloads.as_of(),
            "overview": payloads.overview(),
        },
    )


@require_safe
@cache_html()
def guide_index(request):
    meta = seo.PageMeta(
        title=seo.fit_title("Stock Market Guides: Plain Answers to Common Questions", "Stock Market Guides"),
        description=seo.fit_description(
            "Short, sourced guides to the ideas behind every company profile: market capitalization, SPACs, "
            "ADRs and how U.S. stocks are classified.",
        ),
        path=reverse("web:guides"),
        breadcrumbs=[("Guides", reverse("web:guides"))],
    )
    meta.graph = [seo.web_page(meta, page_type="CollectionPage")]
    return render(request, "pages/guide_index.html", {"page": meta, "guides": content.GUIDES})


@require_safe
@cache_html()
def guide(request, slug):
    item = content.GUIDES_BY_SLUG.get(slug)
    if item is None:
        raise Http404
    meta = seo.PageMeta(
        title=seo.fit_title(item.seo_title),
        description=item.description,
        path=reverse("web:guide", kwargs={"slug": slug}),
        og_type="article",
        image=f"{item.image}.png",
        image_alt=item.image_alt,
        published=item.published,
        modified=item.updated,
        breadcrumbs=[
            ("Guides", reverse("web:guides")),
            (item.title, reverse("web:guide", kwargs={"slug": slug})),
        ],
    )
    meta.graph = [seo.web_page(meta, author=item.author), seo.article(meta, item.title, item.author)]
    return render(
        request,
        item.template,
        {
            "page": meta,
            "guide": item,
            "author": item.author,
            "stats": _guide_stats(slug),
            "related_guides": [g for g in content.GUIDES if g.slug != slug],
        },
    )


def _guide_stats(slug):
    """Live figures quoted in a guide, so its numbers are never stale."""
    if slug == "what-is-market-cap":
        overview = payloads.overview()
        return {"overview": overview, "by_size": {s["slug"]: s["companies"] for s in overview["by_size"]}}
    if slug in ("what-is-a-spac", "what-is-an-adr"):
        listing = payloads.directory({"type": "spac" if slug == "what-is-a-spac" else "adr", "page_size": 5})
        return {"listing": listing, "max_cap": _max_cap(listing["results"])}
    return {}


# ---------------------------------------------------------------------------
# Crawler files
# ---------------------------------------------------------------------------

# Named explicitly so a later blanket rule for "*" can never shut them out.
CRAWLERS = [
    "Googlebot",
    "Bingbot",
    "GPTBot",
    "OAI-SearchBot",
    "ChatGPT-User",
    "ClaudeBot",
    "Claude-SearchBot",
    "Claude-User",
    "PerplexityBot",
    "Perplexity-User",
    "Google-Extended",
    "Applebot",
    "Applebot-Extended",
    "DuckDuckBot",
]
# JSON, admin and search results are not pages anyone should land on.
DISALLOW = ["/admin/", "/api/", "/search/"]


@require_safe
@cache_html()
def robots_txt(request):
    return render(
        request,
        "seo/robots.txt",
        {"crawlers": CRAWLERS, "disallow": DISALLOW, "sitemap": seo.absolute(reverse("web:sitemap-index"))},
        content_type="text/plain; charset=utf-8",
    )


@require_safe
@cache_html()
def llms_txt(request):
    overview = payloads.overview()
    return render(
        request,
        "seo/llms.txt",
        {
            "overview": overview,
            "sectors": overview["by_sector"],
            "exchanges": overview["by_exchange"],
            "guides": content.GUIDES,
            "base": settings.SITE_URL,
        },
        content_type="text/markdown; charset=utf-8",
    )


@require_safe
def indexnow_key(request):
    """IndexNow ownership proof: the key, served at /<key>.txt."""
    return HttpResponse(settings.INDEXNOW_KEY, content_type="text/plain; charset=utf-8")

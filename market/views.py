"""
The page API: one endpoint per prototype page or page block.

Every view is public, read-only and cached per data version (core.cache).
Lists and hubs report `as_of` as the last successful reference sync; a stock
profile reports its own last fetch.
"""

from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Case, IntegerField, Q, Value, When
from rest_framework.exceptions import NotFound, ValidationError

from core.cache import CachedAPIView
from market import queries
from market.lookups import Labels, reference_as_of
from market.models import Stock
from market.serializers import StockProfileSerializer, StockRowSerializer
from market.universe import NOT_CLASSIFIED, PAGE_TYPES, hub_is_indexable, indexable_stocks, page_stocks

HUB_TOP_SIZE = 10
OVERVIEW_TOP_SIZE = 6
OVERVIEW_SECTORS = 10
SEARCH_LIMIT = 10
SEARCH_MAX_LENGTH = 50


def _as_of():
    as_of = reference_as_of()
    return as_of.isoformat() if as_of else None


def _rows(stocks, labels):
    return StockRowSerializer(stocks, many=True, context={"labels": labels}).data


def _page_stock(ticker):
    """The stock behind /stocks/{ticker}/, or 404 if it has no page."""
    # Inactive stocks keep their page (marked inactive, not indexed). Types
    # without pages (ETFs, warrants...) do not exist as far as the site knows.
    stock = Stock.objects.filter(ticker=ticker.upper(), security_type__in=PAGE_TYPES).first()
    if stock is None:
        raise NotFound(f"No stock page for '{ticker}'.")
    return stock


class OverviewView(CachedAPIView):
    """GET /api/v1/overview/ — the home page."""

    def build(self, request):
        labels = Labels()
        stocks = page_stocks()
        sectors = queries.sector_index(labels)
        return {
            **queries.stats(stocks),
            "sectors_covered": sum(1 for s in sectors if s["slug"] != NOT_CLASSIFIED["slug"]),
            "by_sector": sectors[:OVERVIEW_SECTORS],
            "by_exchange": queries.exchange_index(labels),
            "by_size": queries.size_index(),
            "largest": _rows(queries.largest(stocks, OVERVIEW_TOP_SIZE), labels),
            "as_of": _as_of(),
        }


class StockListView(CachedAPIView):
    """GET /api/v1/stocks/ — the directory, and the company tables on hubs."""

    def build(self, request):
        labels = Labels()
        stocks = queries.filter_directory(request.query_params, labels)
        page = queries.paginate(stocks, request.query_params)
        return {
            "count": page["count"],
            "page": page["page"],
            "page_size": page["page_size"],
            "num_pages": page["num_pages"],
            "results": _rows(page["objects"], labels),
            "as_of": _as_of(),
        }


class StockDetailView(CachedAPIView):
    """GET /api/v1/stocks/{ticker}/ — the profile page."""

    def build(self, request, ticker):
        stock = _page_stock(ticker)
        return StockProfileSerializer(stock, context={"labels": Labels()}).data


class StockPeersView(CachedAPIView):
    """GET /api/v1/stocks/{ticker}/peers/ — market cap context, peers, related."""

    def build(self, request, ticker):
        stock = _page_stock(ticker)
        labels = Labels()
        result = queries.peers(stock)
        return {
            "ticker": stock.ticker,
            "rank": result["rank"],
            "ranked_total": result["ranked_total"],
            "context": _rows(result["context"], labels),
            "peers": _rows(result["peers"], labels),
            "related": _rows(result["related"], labels),
            "as_of": _as_of(),
        }


class SectorListView(CachedAPIView):
    """GET /api/v1/sectors/"""

    def build(self, request):
        return {"results": queries.sector_index(Labels()), "as_of": _as_of()}


class SectorDetailView(CachedAPIView):
    """GET /api/v1/sectors/{slug}/ — a sector hub. Companies via /stocks/?sector=."""

    def build(self, request, slug):
        labels = Labels()
        if slug == NOT_CLASSIFIED["slug"]:
            stocks, name, primer = page_stocks().filter(sic_code=""), NOT_CLASSIFIED["name"], ""
            sic_code = None
        else:
            sector = labels.sector_by_slug.get(slug)
            if sector is None:
                raise NotFound(f"No sector '{slug}'.")
            stocks, name, primer = page_stocks().filter(sic_code=sector.sic_code), sector.name, sector.primer
            sic_code = sector.sic_code
        return _hub(
            stocks, labels, slug=slug, name=name, extra={"sic_code": sic_code, "primer": primer or None}
        )


class ExchangeListView(CachedAPIView):
    """GET /api/v1/exchanges/"""

    def build(self, request):
        return {"results": queries.exchange_index(Labels()), "as_of": _as_of()}


class ExchangeDetailView(CachedAPIView):
    """GET /api/v1/exchanges/{slug}/ — an exchange hub. Companies via /stocks/?exchange=."""

    def build(self, request, slug):
        labels = Labels()
        exchange = labels.exchange_by_slug.get(slug)
        if exchange is None:
            raise NotFound(f"No exchange '{slug}'.")
        stocks = page_stocks().filter(primary_exchange=exchange.mic)
        return _hub(stocks, labels, slug=slug, name=exchange.display_name, extra={"mic": exchange.mic})


def _hub(stocks, labels, slug, name, extra):
    summary = queries.stats(stocks)
    return {
        "slug": slug,
        "name": name,
        **extra,
        **summary,
        "largest": _rows(queries.largest(stocks, HUB_TOP_SIZE), labels),
        "indexable": hub_is_indexable(summary["companies"], slug),
        "as_of": _as_of(),
    }


class SearchView(CachedAPIView):
    """
    GET /api/v1/search/?q= — the search box typeahead.

    Exact ticker first, then ticker prefix, then names starting with the
    text, then fuzzy name matches (pg_trgm) ranked by similarity; ties go to
    the larger company.
    """

    def build(self, request):
        text = request.query_params.get("q", "").strip()
        if not text:
            raise ValidationError({"q": ["Enter a ticker or company name."]})
        text = text[:SEARCH_MAX_LENGTH]

        matches = (
            page_stocks()
            .annotate(similarity=TrigramSimilarity("name", text))
            .filter(
                Q(ticker__istartswith=text) | Q(display_name__icontains=text) | Q(name__trigram_similar=text)
            )
            .annotate(
                tier=Case(
                    When(ticker__iexact=text, then=Value(0)),
                    When(ticker__istartswith=text, then=Value(1)),
                    When(display_name__istartswith=text, then=Value(2)),
                    default=Value(3),
                    output_field=IntegerField(),
                )
            )
            .order_by("tier", "-similarity", *queries.BY_SIZE)[:SEARCH_LIMIT]
        )
        labels = Labels()
        return {
            "query": text,
            "results": [
                {
                    "ticker": s.ticker,
                    "display_name": s.display_name or s.name,
                    "security_type": s.security_type,
                    "exchange": labels.exchange(s.primary_exchange),
                }
                for s in matches
            ],
        }


class SitemapView(CachedAPIView):
    """GET /api/v1/sitemap/ — every indexable page, with its last-modified date."""

    def build(self, request):
        labels = Labels()
        as_of = reference_as_of()
        lastmod = as_of.date().isoformat() if as_of else None

        stocks = [
            {"ticker": ticker, "lastmod": (synced.date().isoformat() if synced else lastmod)}
            for ticker, synced in indexable_stocks()
            .order_by("ticker")
            .values_list("ticker", "details_synced_at")
        ]
        sectors = [
            {"slug": s["slug"], "lastmod": lastmod} for s in queries.sector_index(labels) if s["indexable"]
        ]
        exchanges = [
            {"slug": e["slug"], "lastmod": lastmod} for e in queries.exchange_index(labels) if e["indexable"]
        ]
        return {"stocks": stocks, "sectors": sectors, "exchanges": exchanges}

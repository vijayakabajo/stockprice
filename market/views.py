"""
The page API: one endpoint per prototype page or page block.

Every view is public, read-only and cached per data version (core.cache).
Lists and hubs report `as_of` as the last successful reference sync; a stock
profile reports its own last fetch. The payloads themselves are built in
market.payloads, shared with the server-rendered site.
"""

from core.cache import CachedAPIView
from market import payloads


class OverviewView(CachedAPIView):
    """GET /api/v1/overview/ — the home page."""

    def build(self, request):
        return payloads.overview()


class StockListView(CachedAPIView):
    """GET /api/v1/stocks/ — the directory, and the company tables on hubs."""

    def build(self, request):
        return payloads.directory(request.query_params)


class StockDetailView(CachedAPIView):
    """GET /api/v1/stocks/{ticker}/ — the profile page."""

    def build(self, request, ticker):
        return payloads.profile(payloads.page_stock(ticker))


class StockPeersView(CachedAPIView):
    """GET /api/v1/stocks/{ticker}/peers/ — market cap context, peers, related."""

    def build(self, request, ticker):
        return payloads.peers(payloads.page_stock(ticker))


class SectorListView(CachedAPIView):
    """GET /api/v1/sectors/"""

    def build(self, request):
        return payloads.sector_list()


class SectorDetailView(CachedAPIView):
    """GET /api/v1/sectors/{slug}/ — a sector hub. Companies via /stocks/?sector=."""

    def build(self, request, slug):
        return payloads.sector_hub(slug)


class ExchangeListView(CachedAPIView):
    """GET /api/v1/exchanges/"""

    def build(self, request):
        return payloads.exchange_list()


class ExchangeDetailView(CachedAPIView):
    """GET /api/v1/exchanges/{slug}/ — an exchange hub. Companies via /stocks/?exchange=."""

    def build(self, request, slug):
        return payloads.exchange_hub(slug)


class SearchView(CachedAPIView):
    """GET /api/v1/search/?q= — the search box typeahead."""

    def build(self, request):
        return payloads.search(request.query_params.get("q", ""))


class SitemapView(CachedAPIView):
    """GET /api/v1/sitemap/ — every indexable page, with its last-modified date."""

    def build(self, request):
        return payloads.sitemap()

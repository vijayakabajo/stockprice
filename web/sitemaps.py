"""
sitemap.xml, built with django.contrib.sitemaps.

Only indexable pages are listed: the same rules (market.universe) decide
what the sitemap lists and which pages carry `noindex`, so the two never
disagree. lastmod is the date the page's data last changed: a company's own
profile refresh, the last reference sync for hubs, the edit date for guides.

Absolute URLs come from settings.SITE_URL. The sitemap index is our own
small view because Django's builds them from the request's Host header.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap as sitemap_section_view
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_safe

from core.cache import cache_html
from market import payloads
from market.lookups import reference_as_of
from market.universe import indexable_stocks
from web import content, seo


def _reference_date():
    as_of = reference_as_of()
    return as_of.date() if as_of else None


class SiteSitemap(Sitemap):
    def get_protocol(self, protocol=None):
        return urlsplit(settings.SITE_URL).scheme

    def get_domain(self, site=None):
        return urlsplit(settings.SITE_URL).netloc


class PagesSitemap(SiteSitemap):
    """Home and the index pages: they change with every reference sync."""

    changefreq = "daily"

    def items(self):
        return [
            "web:home",
            "web:directory",
            "web:sectors",
            "web:exchanges",
            "web:guides",
            "web:glossary",
            "web:about",
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return _reference_date()


class GuidesSitemap(SiteSitemap):
    changefreq = "monthly"

    def items(self):
        return content.GUIDES

    def location(self, item):
        return reverse("web:guide", kwargs={"slug": item.slug})

    def lastmod(self, item):
        return item.updated


class StocksSitemap(SiteSitemap):
    changefreq = "daily"
    limit = 10000

    def items(self):
        return indexable_stocks().order_by("ticker").values("ticker", "details_synced_at", "last_synced_at")

    def location(self, item):
        return reverse("web:stock", kwargs={"ticker": item["ticker"].lower()})

    def lastmod(self, item):
        synced = item["details_synced_at"] or item["last_synced_at"]
        return synced.date() if synced else None


class SectorsSitemap(SiteSitemap):
    changefreq = "daily"

    def items(self):
        return [s for s in payloads.sector_list()["results"] if s["indexable"]]

    def location(self, item):
        return reverse("web:sector", kwargs={"slug": item["slug"]})

    def lastmod(self, item):
        return _reference_date()


class ExchangesSitemap(SectorsSitemap):
    def items(self):
        return [e for e in payloads.exchange_list()["results"] if e["indexable"]]

    def location(self, item):
        return reverse("web:exchange", kwargs={"slug": item["slug"]})


SITEMAPS = {
    "pages": PagesSitemap,
    "guides": GuidesSitemap,
    "sectors": SectorsSitemap,
    "exchanges": ExchangesSitemap,
    "stocks": StocksSitemap,
}


@require_safe
@cache_html()
def sitemap_index(request):
    entries = []
    for section, sitemap_class in SITEMAPS.items():
        site = sitemap_class()
        url = seo.absolute(reverse("web:sitemap-section", kwargs={"section": section}))
        lastmod = site.get_latest_lastmod()
        for page in range(1, site.paginator.num_pages + 1):
            entries.append({"location": url if page == 1 else f"{url}?p={page}", "lastmod": lastmod})
    return render(request, "seo/sitemap_index.xml", {"entries": entries}, content_type="application/xml")


@require_safe
@cache_html(params=("p",))
def sitemap_section(request, section):
    if section not in SITEMAPS:
        raise Http404
    return sitemap_section_view(request, SITEMAPS, section=section)

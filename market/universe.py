"""
Which stocks get pages, and which pages search engines should index.

Every endpoint takes these rules from here, so the directory, the hubs, the
profile and the sitemap can never disagree about what exists.
"""

from market.models import SecurityType, Stock

# Security types that get a page. ETFs, warrants, units, preferreds, rights
# and funds are not companies and are left out entirely (404).
PAGE_TYPES = (SecurityType.COMMON, SecurityType.ADR, SecurityType.SPAC)

# Of those, the ones whose pages are indexed. SPACs are pre-merger shells with
# thin pages, so they render but stay out of search indexes.
INDEXABLE_TYPES = (SecurityType.COMMON, SecurityType.ADR)

# A sector or exchange hub with fewer companies than this is a thin page.
HUB_MIN_COMPANIES = 3

NOT_CLASSIFIED = {"slug": "not-classified", "name": "Not classified"}


def page_stocks():
    """Active stocks that get a page: the directory universe."""
    return Stock.objects.filter(active=True, security_type__in=PAGE_TYPES)


def indexable_stocks():
    return page_stocks().filter(security_type__in=INDEXABLE_TYPES).exclude(description="")


def stock_is_indexable(stock) -> bool:
    return stock.active and stock.security_type in INDEXABLE_TYPES and bool(stock.description)


def hub_is_indexable(companies: int, slug: str) -> bool:
    return companies >= HUB_MIN_COMPANIES and slug != NOT_CLASSIFIED["slug"]

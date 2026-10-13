"""
Query-string parsing, pagination and aggregate queries for the page API.

Everything here works on market.universe.page_stocks(): the directory, hub
stats, peers and the overview all count the same set of companies.
"""

from django.core.paginator import EmptyPage, Paginator
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import Lower
from rest_framework.exceptions import NotFound, ValidationError

from market.models import SecurityType, SizeBucket
from market.universe import NOT_CLASSIFIED, PAGE_TYPES, hub_is_indexable, page_stocks

ORDERINGS = {
    "-market_cap": [F("market_cap").desc(nulls_last=True), "ticker"],
    "name": [Lower("display_name"), "ticker"],
    "ticker": ["ticker"],
    "-employees": [F("total_employees").desc(nulls_last=True), "ticker"],
}
DEFAULT_ORDERING = "-market_cap"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100

# Largest-first, nulls last: the order every "top companies" list uses.
BY_SIZE = [F("market_cap").desc(nulls_last=True), "ticker"]


# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------


def filter_directory(params, labels):
    """
    Applies the directory query string to page_stocks(). An unknown value is
    a 400 listing the valid ones: an empty page would hide a typo.
    """
    qs = page_stocks()
    errors = {}

    if slug := params.get("exchange"):
        exchange = labels.exchange_by_slug.get(slug)
        if exchange is None:
            errors["exchange"] = [f"Unknown exchange '{slug}'."]
        else:
            qs = qs.filter(primary_exchange=exchange.mic)

    if slug := params.get("sector"):
        if slug == NOT_CLASSIFIED["slug"]:
            qs = qs.filter(sic_code="")
        elif (sector := labels.sector_by_slug.get(slug)) is None:
            errors["sector"] = [f"Unknown sector '{slug}'."]
        else:
            qs = qs.filter(sic_code=sector.sic_code)

    if value := params.get("type"):
        if value not in PAGE_TYPES:
            errors["type"] = [f"Must be one of: {', '.join(PAGE_TYPES)}."]
        else:
            qs = qs.filter(security_type=value)

    if value := params.get("size"):
        if value not in SizeBucket.values:
            errors["size"] = [f"Must be one of: {', '.join(SizeBucket.values)}."]
        else:
            qs = qs.filter(size_bucket=value)

    if text := params.get("q", "").strip():
        qs = qs.filter(
            Q(ticker__istartswith=text) | Q(display_name__icontains=text) | Q(name__icontains=text)
        )

    ordering = params.get("ordering", DEFAULT_ORDERING)
    if ordering not in ORDERINGS:
        errors["ordering"] = [f"Must be one of: {', '.join(ORDERINGS)}."]

    if errors:
        raise ValidationError(errors)
    return qs.order_by(*ORDERINGS[ordering])


def paginate(queryset, params):
    """
    Page-number pagination. Returns page numbers rather than next/previous
    links: links would embed the host of whichever request filled the cache.
    """
    try:
        page_number = int(params.get("page", 1))
        page_size = min(int(params.get("page_size", DEFAULT_PAGE_SIZE)), MAX_PAGE_SIZE)
    except ValueError:
        raise ValidationError({"page": ["page and page_size must be integers."]}) from None
    if page_number < 1 or page_size < 1:
        raise ValidationError({"page": ["page and page_size must be positive."]})

    paginator = Paginator(queryset, page_size)
    try:
        page = paginator.page(page_number)
    except EmptyPage:
        raise NotFound(f"Page {page_number} is out of range.") from None
    return {
        "count": paginator.count,
        "page": page_number,
        "page_size": page_size,
        "num_pages": paginator.num_pages,
        "objects": list(page.object_list),
    }


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------


def _number(value):
    return float(value) if value is not None else None


def stats(qs):
    """Company count, combined/average market cap and total employees."""
    raw = qs.aggregate(
        companies=Count("id"),
        total_market_cap=Sum("market_cap"),
        average_market_cap=Avg("market_cap"),
        total_employees=Sum("total_employees"),
    )
    return {
        "companies": raw["companies"],
        "total_market_cap": _number(raw["total_market_cap"]),
        "average_market_cap": _number(raw["average_market_cap"]),
        "total_employees": raw["total_employees"],
    }


def grouped(field):
    """{value of `field`: {companies, total_market_cap}} over page_stocks()."""
    rows = page_stocks().values(field).annotate(companies=Count("id"), total_market_cap=Sum("market_cap"))
    return {
        row[field]: {"companies": row["companies"], "total_market_cap": _number(row["total_market_cap"])}
        for row in rows
    }


def sector_index(labels):
    """Every sector with companies, largest first, with Not classified last."""
    entries = []
    for sic_code, counts in grouped("sic_code").items():
        label = labels.sector(sic_code)
        entries.append({**label, **counts, "indexable": hub_is_indexable(counts["companies"], label["slug"])})
    return sorted(entries, key=lambda e: (e["slug"] == NOT_CLASSIFIED["slug"], -e["companies"], e["name"]))


def exchange_index(labels):
    """Every exchange with listed companies, largest first."""
    entries = []
    for mic, counts in grouped("primary_exchange").items():
        label = labels.exchange(mic)
        if label is None:
            continue
        entries.append({**label, **counts, "indexable": hub_is_indexable(counts["companies"], label["slug"])})
    return sorted(entries, key=lambda e: (-e["companies"], e["name"]))


def size_index():
    counts = grouped("size_bucket")
    return [
        {"slug": bucket.value, "name": bucket.label, "companies": counts[bucket.value]["companies"]}
        for bucket in SizeBucket
        if bucket.value in counts
    ]


def largest(qs, limit):
    return list(qs.order_by(*BY_SIZE)[:limit])


# ---------------------------------------------------------------------------
# Peers
# ---------------------------------------------------------------------------

CONTEXT_SIZE = 5
PEERS_SIZE = 5
MIN_SECTOR_PEERS = 2
RELATED_SIZE = 3


def peers(stock):
    """
    The comparison blocks on a profile, using the prototype's rules:

    context  the largest companies plus this one, with its rank by market cap
    peers    largest in the same sector, or the same exchange when the sector
             has fewer than two others; none for SPACs, which have no business
    related  three companies, same sector first, topped up from the exchange
    """
    others = page_stocks().exclude(pk=stock.pk)
    same_sector = others.filter(sic_code=stock.sic_code) if stock.sic_code else others.none()
    same_exchange = others.filter(primary_exchange=stock.primary_exchange)

    ranked = page_stocks().filter(market_cap__isnull=False)
    rank = None
    if stock.market_cap is not None:
        rank = ranked.filter(market_cap__gt=stock.market_cap).count() + 1
    top = largest(ranked, CONTEXT_SIZE)
    context = top if stock in top else sorted(top + [stock], key=_size_key)

    peer_list = []
    if stock.security_type != SecurityType.SPAC:
        peer_list = largest(same_sector, PEERS_SIZE)
        if len(peer_list) < MIN_SECTOR_PEERS:
            peer_list = largest(same_exchange, PEERS_SIZE)

    related = largest(same_sector, RELATED_SIZE)
    if len(related) < RELATED_SIZE:
        seen = {s.pk for s in related}
        extra = largest(same_exchange.exclude(pk__in=seen), RELATED_SIZE - len(related))
        related += extra

    return {
        "rank": rank,
        "ranked_total": ranked.count(),
        "context": context,
        "peers": peer_list,
        "related": related,
    }


def _size_key(stock):
    return (stock.market_cap is None, -(stock.market_cap or 0), stock.ticker)

"""
IndexNow: tell Bing, Yandex, Seznam, Naver and the other participating
engines which URLs changed, instead of waiting for a recrawl. One ping to
api.indexnow.org is shared with every participating engine. (Google does not
use IndexNow; it reads sitemap lastmod.)

Pinged after each successful company-profile sync (sync.tasks), and by hand
with `manage.py indexnow_ping`. Only active when settings.INDEXNOW_ENABLED,
which by default means production with INDEXNOW_KEY set.
"""

import logging
from urllib.parse import urlsplit

import requests
from django.conf import settings
from django.urls import reverse

from market import payloads
from market.universe import indexable_stocks
from web import content, seo

logger = logging.getLogger(__name__)

BATCH_SIZE = 10_000  # the protocol's per-request limit
TIMEOUT = 30


def stock_urls(since=None):
    stocks = indexable_stocks()
    if since is not None:
        stocks = stocks.filter(details_synced_at__gte=since)
    return [
        seo.absolute(reverse("web:stock", kwargs={"ticker": t.lower()}))
        for t in stocks.values_list("ticker", flat=True)
    ]


def hub_urls():
    """Pages whose figures move with every sync: home, indexes and hubs."""
    names = ["web:home", "web:directory", "web:sectors", "web:exchanges"]
    urls = [seo.absolute(reverse(name)) for name in names]
    urls += [
        seo.absolute(reverse("web:sector", kwargs={"slug": s["slug"]}))
        for s in payloads.sector_list()["results"]
        if s["indexable"]
    ]
    urls += [
        seo.absolute(reverse("web:exchange", kwargs={"slug": e["slug"]}))
        for e in payloads.exchange_list()["results"]
        if e["indexable"]
    ]
    return urls


def guide_urls():
    return [seo.absolute(reverse("web:guide", kwargs={"slug": g.slug})) for g in content.GUIDES]


def submit(urls):
    """POSTs `urls` in batches. Returns how many were submitted (0 when disabled)."""
    urls = list(dict.fromkeys(urls))
    if not urls:
        return 0
    if not settings.INDEXNOW_ENABLED:
        logger.info(f"IndexNow disabled; would have submitted {len(urls)} URL(s).")
        return 0

    host = urlsplit(settings.SITE_URL).netloc
    for start in range(0, len(urls), BATCH_SIZE):
        batch = urls[start : start + BATCH_SIZE]
        response = requests.post(
            settings.INDEXNOW_ENDPOINT,
            json={
                "host": host,
                "key": settings.INDEXNOW_KEY,
                "keyLocation": f"{settings.SITE_URL}/{settings.INDEXNOW_KEY}.txt",
                "urlList": batch,
            },
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=TIMEOUT,
        )
        # 200 OK and 202 Accepted (key validation pending) are both success.
        response.raise_for_status()
        logger.info(f"IndexNow accepted {len(batch)} URL(s) (HTTP {response.status_code}).")
    return len(urls)

import logging

from celery import shared_task
from django.utils.dateparse import parse_datetime

from web import indexnow

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True, soft_time_limit=600, time_limit=660)
def indexnow_ping_task(since):
    """
    Pings IndexNow with every profile refreshed since `since` (ISO datetime),
    plus the hubs, whose totals moved with them. A failed ping is logged, not
    retried: the sitemap's lastmod covers the same change.
    """
    urls = indexnow.stock_urls(parse_datetime(since))
    if not urls:
        return
    try:
        indexnow.submit(urls + indexnow.hub_urls())
    except Exception:
        logger.exception("IndexNow ping failed")

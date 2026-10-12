"""
Celery entry points for the sync jobs. Thin wrappers: the work, the locking
and the DataSyncJob bookkeeping all live in sync.services, so a management
command and a scheduled run behave identically.

acks_late is off for these tasks. With the Redis broker, an unacknowledged
task is redelivered once the visibility timeout (1h by default) passes, so a
long sync acked late would be started a second time while still running. A
sync lost to a worker crash is simply picked up by the next scheduled run.
"""

import logging
from datetime import date

from celery import shared_task

from sync import services

logger = logging.getLogger(__name__)

SYNC_TASK_OPTIONS = {"acks_late": False, "ignore_result": True}


def _run(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except services.SyncAlreadyRunning as e:
        # Not a failure: the run already in progress covers this one.
        logger.warning(str(e))


@shared_task(soft_time_limit=3600, time_limit=3900, **SYNC_TASK_OPTIONS)
def sync_stocks_task():
    _run(services.sync_stocks)


@shared_task(soft_time_limit=3 * 3600, time_limit=3 * 3600 + 300, **SYNC_TASK_OPTIONS)
def sync_stock_details_task(limit=None):
    """Profiles, then sectors: new SIC codes only arrive with the profiles."""
    try:
        _run(services.sync_stock_details, limit=limit)
    finally:
        _run(services.refresh_sectors)


@shared_task(soft_time_limit=600, time_limit=900, **SYNC_TASK_OPTIONS)
def refresh_sectors_task():
    _run(services.refresh_sectors)


@shared_task(soft_time_limit=600, time_limit=900, **SYNC_TASK_OPTIONS)
def sync_exchanges_task():
    _run(services.sync_exchanges)


@shared_task(**SYNC_TASK_OPTIONS)
def sync_reference_data_task():
    """Ticker master, then company profiles. Profiles run even if the master fails."""
    try:
        _run(services.sync_stocks)
    finally:
        sync_stock_details_task.delay()


@shared_task(soft_time_limit=1800, time_limit=2100, **SYNC_TASK_OPTIONS)
def sync_daily_prices_task(day=None):
    """
    Syncs one session (ISO date string), or by default every recent session
    that has no successful sync yet, so a missed night heals itself.
    """
    days = [date.fromisoformat(day)] if day else services.pending_daily_price_dates()
    if not days:
        logger.info("Daily prices are up to date.")
    for d in days:
        _run(services.sync_daily_prices, d)

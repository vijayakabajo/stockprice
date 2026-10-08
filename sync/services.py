import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db import connection
from django.db.models import F, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from psycopg2.extras import execute_values

from data_provider.massive import MassiveClient
from market.models import Stock
from sync.models import DataSyncJob

logger = logging.getLogger(__name__)

MARKET_TZ = ZoneInfo("America/New_York")

# Extended-hours trading ends at 20:00 ET; the day's bar is final after that.
SESSION_FINAL_HOUR_ET = 20

# Fields owned by the ticker list (master) and by ticker details (profile).
MASTER_FIELDS = [
    "name", "market", "locale", "primary_exchange", "asset_type", "active",
    "currency_name", "cik", "composite_figi", "share_class_figi",
    "list_date", "delisted_utc", "last_synced_at",
]
DETAIL_FIELDS = [
    "description", "ticker_root", "ticker_suffix", "sic_code", "sic_description",
    "homepage_url", "phone_number", "logo_url", "icon_url",
    "address1", "city", "state", "postal_code",
    "market_cap", "share_class_shares_outstanding", "weighted_shares_outstanding",
    "round_lot", "total_employees", "details_synced_at",
]

# A master sync that returns far fewer tickers than we hold is a provider
# hiccup, not a mass delisting. Below this ratio, skip deactivation.
MIN_SEEN_RATIO_FOR_DEACTIVATION = 0.9


class SyncAlreadyRunning(Exception):
    """Another run of the same job type holds the lock."""


@contextmanager
def tracked_job(job_type, data_date=None, lock_timeout=3600):
    """
    Wraps one sync run: takes a Redis lock per job type, records a
    DataSyncJob, and always leaves it in SUCCESS or FAILED — including on
    KeyboardInterrupt, worker shutdown or a Celery time limit.

    Exceptions are re-raised so the caller (Celery, a management command)
    sees the failure too.
    """
    lock_key = f"sync-lock:{job_type}"
    token = uuid.uuid4().hex
    if not cache.add(lock_key, token, timeout=lock_timeout):
        raise SyncAlreadyRunning(f"{job_type} sync is already running")

    try:
        # We hold the lock, so any STARTED row of this type is from a run
        # that died without cleaning up.
        DataSyncJob.objects.filter(job_type=job_type, status=DataSyncJob.Status.STARTED).update(
            status=DataSyncJob.Status.FAILED,
            error="Abandoned: process exited before the job finished",
            end_time=Coalesce(F("end_time"), Value(timezone.now())),
        )

        job = DataSyncJob.objects.create(
            job_type=job_type,
            data_date=data_date,
            start_time=timezone.now(),
            status=DataSyncJob.Status.STARTED,
        )
        try:
            yield job
            job.status = DataSyncJob.Status.SUCCESS
        except BaseException as e:
            job.status = DataSyncJob.Status.FAILED
            job.error = f"{type(e).__name__}: {e}"
            logger.exception(f"{job_type} sync failed")
            raise
        finally:
            job.end_time = timezone.now()
            job.save()
    finally:
        if cache.get(lock_key) == token:
            cache.delete(lock_key)


def _clip(model, field_name, value):
    """Truncate strings to the column width so one odd value cannot fail a whole batch."""
    if value is None:
        return ""
    value = str(value)
    max_length = model._meta.get_field(field_name).max_length
    return value[:max_length] if max_length else value


def _parse(parser, value):
    if not value:
        return None
    try:
        return parser(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Stock master
# ---------------------------------------------------------------------------


def _stock_from_ticker(data, now):
    def s(field, key=None, default=""):
        return _clip(Stock, field, data.get(key or field) or default)

    return Stock(
        ticker=_clip(Stock, "ticker", data["ticker"]),
        name=s("name"),
        market=s("market", default="stocks"),
        locale=s("locale", default="us"),
        primary_exchange=s("primary_exchange"),
        asset_type=s("asset_type", "type"),
        active=data.get("active", True),
        currency_name=s("currency_name", default="usd"),
        cik=s("cik"),
        composite_figi=s("composite_figi"),
        share_class_figi=s("share_class_figi"),
        list_date=_parse(parse_date, data.get("list_date")),
        delisted_utc=_parse(parse_datetime, data.get("delisted_utc")),
        last_synced_at=now,
    )


def sync_stocks(batch_size=1000):
    """
    Fetches the active ticker list from Massive and bulk-upserts it into Stock.
    Active stocks missing from a complete run are marked inactive — Massive's
    active list is the source of truth, and delisted rows are kept, not deleted.
    """
    with tracked_job(DataSyncJob.JobType.STOCK_MASTER) as job:
        client = MassiveClient()
        now = timezone.now()
        batch = []
        seen = 0

        def flush():
            Stock.objects.bulk_create(
                batch,
                update_conflicts=True,
                unique_fields=["ticker"],
                update_fields=MASTER_FIELDS,
            )
            batch.clear()
            job.records_processed = seen
            job.save(update_fields=["records_processed"])

        for ticker_data in client.get_tickers():
            if not ticker_data.get("ticker"):
                continue
            batch.append(_stock_from_ticker(ticker_data, now))
            seen += 1
            if len(batch) >= batch_size:
                flush()
                logger.info(f"Upserted {seen} stocks...")
        if batch:
            flush()

        previously_active = Stock.objects.filter(active=True, last_synced_at__lt=now)
        active_total = Stock.objects.filter(active=True).count()
        if active_total and seen / active_total >= MIN_SEEN_RATIO_FOR_DEACTIVATION:
            deactivated = previously_active.update(active=False)
        else:
            deactivated = 0
            logger.warning(
                f"Only {seen} tickers returned vs {active_total} active; skipping deactivation."
            )

        job.records_processed = seen
        logger.info(f"Stock sync complete. {seen} upserted, {deactivated} marked inactive.")


# ---------------------------------------------------------------------------
# Stock details
# ---------------------------------------------------------------------------


def _apply_details(stock, details, now):
    for field in ["description", "ticker_root", "ticker_suffix", "sic_code",
                  "sic_description", "homepage_url", "phone_number"]:
        setattr(stock, field, _clip(Stock, field, details.get(field)))

    # Nested objects can be absent or explicitly null.
    branding = details.get("branding") or {}
    stock.logo_url = _clip(Stock, "logo_url", branding.get("logo_url"))
    stock.icon_url = _clip(Stock, "icon_url", branding.get("icon_url"))

    address = details.get("address") or {}
    for field in ["address1", "city", "state", "postal_code"]:
        setattr(stock, field, _clip(Stock, field, address.get(field)))

    market_cap = details.get("market_cap")
    stock.market_cap = Decimal(str(market_cap)).quantize(Decimal("0.01")) if market_cap is not None else None
    for field in ["share_class_shares_outstanding", "weighted_shares_outstanding",
                  "round_lot", "total_employees"]:
        value = details.get(field)
        setattr(stock, field, int(value) if value is not None else None)

    stock.details_synced_at = now


def sync_stock_details(limit=None, delay=0, workers=8, max_consecutive_errors=25):
    """
    Refreshes company profiles from the ticker-details endpoint.

    Active stocks are processed never-fetched first, then oldest-fetched, so
    a capped run still makes progress and repeated runs cycle through the
    whole universe. `delay` (seconds between calls) is for rate-limited plans
    and forces a single worker.
    """
    with tracked_job(DataSyncJob.JobType.STOCK_DETAILS, lock_timeout=4 * 3600) as job:
        client = MassiveClient(pool_size=max(workers, 1))
        stocks = Stock.objects.filter(active=True).order_by(
            F("details_synced_at").asc(nulls_first=True), "ticker"
        )
        if limit:
            stocks = stocks[:limit]
        stocks = list(stocks)

        if delay > 0:
            workers = 1

        def fetch(stock):
            try:
                details = client.get_ticker_details(stock.ticker)
            except Exception as e:
                return stock, None, e
            finally:
                if delay > 0:
                    time.sleep(delay)
            return stock, details, None

        processed = failed = consecutive_errors = 0
        with ThreadPoolExecutor(max_workers=max(workers, 1)) as pool:
            for stock, details, error in pool.map(fetch, stocks):
                if error is not None:
                    failed += 1
                    consecutive_errors += 1
                    logger.warning(f"Details fetch failed for {stock.ticker}: {error}")
                    if consecutive_errors >= max_consecutive_errors:
                        pool.shutdown(cancel_futures=True)
                        raise RuntimeError(
                            f"Aborting after {consecutive_errors} consecutive failures; last: {error}"
                        )
                    continue

                consecutive_errors = 0
                _apply_details(stock, details, timezone.now())
                stock.save(update_fields=DETAIL_FIELDS)
                processed += 1

                if processed % 500 == 0:
                    job.records_processed = processed
                    job.save(update_fields=["records_processed"])
                    logger.info(f"Processed {processed}/{len(stocks)} stock details...")

        job.records_processed = processed
        if failed:
            job.error = f"{failed} ticker(s) failed to fetch; they will be retried next run"
        logger.info(f"Stock details sync complete. {processed} updated, {failed} failed.")


# ---------------------------------------------------------------------------
# Daily prices
# ---------------------------------------------------------------------------

UPSERT_DAILY_PRICE_SQL = """
INSERT INTO market_daily_price
    (stock_id, date, open, high, low, close, volume, vwap, transactions, adjusted)
VALUES %s
ON CONFLICT (stock_id, date) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    vwap = EXCLUDED.vwap,
    transactions = EXCLUDED.transactions,
    adjusted = EXCLUDED.adjusted
"""


def _bar_row(stock_id, day, bar, adjusted):
    """Maps a grouped-daily bar to a row, or None if it fails validation."""
    try:
        o, h, l, c = (Decimal(str(bar[k])) for k in ("o", "h", "l", "c"))
        volume = Decimal(str(bar.get("v") or 0))
    except (KeyError, TypeError, ArithmeticError, ValueError):
        return None
    # Mirrors market_daily_price_ohlc_sane: one bad bar must not fail the batch.
    if not (h >= l and h >= o and h >= c and l <= o and l <= c and volume >= 0):
        return None
    vwap = bar.get("vw")
    return (
        stock_id, day, o, h, l, c, volume,
        Decimal(str(vwap)) if vwap is not None else None,
        bar.get("n"),
        adjusted,
    )


def sync_daily_prices(day: date, adjusted=True, batch_size=2000):
    """
    Upserts one session's OHLCV bars for every known stock, from a single
    grouped-daily call. Bars for tickers not in Stock are skipped (the master
    sync runs first and adds new listings). A weekend or holiday is a
    successful run with zero rows.
    """
    with tracked_job(DataSyncJob.JobType.DAILY_PRICES, data_date=day) as job:
        bars = MassiveClient().get_grouped_daily(day, adjusted=adjusted)
        stock_ids = dict(Stock.objects.values_list("ticker", "id"))

        rows, unknown, invalid = [], 0, 0
        for bar in bars:
            stock_id = stock_ids.get(bar.get("T"))
            if stock_id is None:
                unknown += 1
                continue
            row = _bar_row(stock_id, day, bar, adjusted)
            if row is None:
                invalid += 1
                continue
            rows.append(row)

        with connection.cursor() as cursor:
            execute_values(cursor.cursor, UPSERT_DAILY_PRICE_SQL, rows, page_size=batch_size)

        job.records_processed = len(rows)
        if unknown or invalid:
            job.error = f"Skipped {unknown} bar(s) for unknown tickers and {invalid} invalid bar(s)"
        logger.info(
            f"Daily prices for {day}: {len(rows)} upserted, {unknown} unknown tickers, {invalid} invalid."
        )


def last_final_session_date(now: datetime = None) -> date:
    """The most recent weekday whose daily bar is final (after 20:00 ET)."""
    now_et = (now or timezone.now()).astimezone(MARKET_TZ)
    day = now_et.date() if now_et.hour >= SESSION_FINAL_HOUR_ET else now_et.date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def pending_daily_price_dates(lookback_days=7):
    """
    Weekdays in the lookback window with no successful, non-empty price sync.
    Lets a missed night (worker down, provider outage) heal itself on the
    next run. Holidays stay "pending" and cost one cheap empty call each.
    """
    end = last_final_session_date()
    candidates = [
        end - timedelta(days=i)
        for i in range(lookback_days)
        if (end - timedelta(days=i)).weekday() < 5
    ]
    done = set(
        DataSyncJob.objects.filter(
            job_type=DataSyncJob.JobType.DAILY_PRICES,
            status=DataSyncJob.Status.SUCCESS,
            records_processed__gt=0,
            data_date__in=candidates,
        ).values_list("data_date", flat=True)
    )
    return sorted(d for d in candidates if d not in done)

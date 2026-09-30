from django.utils import timezone
from data_provider.massive import MassiveClient
from market.models import Stock
from sync.models import DataSyncJob
import logging
import time
from dateutil.parser import parse

logger = logging.getLogger(__name__)

def sync_stocks():
    """
    Fetches the stock master list from Massive API and upserts into the Stock table.
    """
    job = DataSyncJob.objects.create(
        job_type=DataSyncJob.JobType.STOCK_MASTER,
        start_time=timezone.now(),
        status=DataSyncJob.Status.STARTED,
    )

    client = MassiveClient()
    processed = 0
    created = 0
    updated = 0
    
    # We will do batch updates since it's >1000s of stocks.
    # To keep it simple in this MVP iteration, we will use update_or_create.
    # For a real scale, bulk_create + on_conflict_do_update should be used.

    try:
        for ticker_data in client.get_tickers():
            # Basic mapping
            ticker = ticker_data.get("ticker")
            if not ticker:
                continue

            # Parse list_date
            list_date = ticker_data.get("list_date")
            if list_date:
                try:
                    list_date = parse(list_date).date()
                except:
                    list_date = None

            # Parse delisted_utc
            delisted_utc = ticker_data.get("delisted_utc")
            if delisted_utc:
                try:
                    delisted_utc = parse(delisted_utc)
                except:
                    delisted_utc = None

            defaults = {
                "name": ticker_data.get("name", ""),
                "market": ticker_data.get("market", "stocks"),
                "locale": ticker_data.get("locale", "us"),
                "primary_exchange": ticker_data.get("primary_exchange", ""),
                "asset_type": ticker_data.get("type", ""),
                "active": ticker_data.get("active", True),
                "currency_name": ticker_data.get("currency_name", "usd"),
                "cik": ticker_data.get("cik", ""),
                "composite_figi": ticker_data.get("composite_figi", ""),
                "share_class_figi": ticker_data.get("share_class_figi", ""),
                "last_synced_at": timezone.now(),
                "list_date": list_date,
                "delisted_utc": delisted_utc,
            }

            _, is_created = Stock.objects.update_or_create(
                ticker=ticker,
                defaults=defaults
            )

            processed += 1
            if is_created:
                created += 1
            else:
                updated += 1
                
            if processed % 500 == 0:
                logger.info(f"Processed {processed} stocks...")

        job.status = DataSyncJob.Status.SUCCESS
        job.records_processed = processed
        logger.info(f"Stock sync complete. {processed} total, {created} created, {updated} updated.")
    
    except Exception as e:
        logger.exception("Stock sync failed")
        job.status = DataSyncJob.Status.FAILED
        job.error = str(e)
    
    finally:
        job.end_time = timezone.now()
        job.save()

def sync_stock_details(limit=1000, delay=13):
    """
    Fetches detailed profiles for stocks that are missing them (e.g. description is empty)
    and updates the Stock records. 
    delay=13 ensures we stay under the 5 requests/minute free tier limit (60s / 5 = 12s).
    """
    job = DataSyncJob.objects.create(
        job_type=DataSyncJob.JobType.STOCK_DETAILS,
        start_time=timezone.now(),
        status=DataSyncJob.Status.STARTED,
    )

    client = MassiveClient()
    processed = 0
    updated = 0

    try:
        # Find active stocks without a description (or other key profile data)
        # Limiting the query to avoid hitting rate limits too hard in a single run.
        stocks_to_update = Stock.objects.filter(description="", active=True)[:limit]
        
        for stock in stocks_to_update:
            details = client.get_ticker_details(stock.ticker)
            if not details:
                processed += 1
                continue

            stock.description = details.get("description", "")
            stock.ticker_root = details.get("ticker_root", "")
            stock.ticker_suffix = details.get("ticker_suffix", "")
            stock.sic_code = details.get("sic_code", "")
            stock.sic_description = details.get("sic_description", "")
            stock.homepage_url = details.get("homepage_url", "")
            stock.phone_number = details.get("phone_number", "")
            
            # Nested fields (if provided by Massive)
            branding = details.get("branding", {})
            stock.logo_url = branding.get("logo_url", "")
            stock.icon_url = branding.get("icon_url", "")
            
            address = details.get("address", {})
            stock.address1 = address.get("address1", "")
            stock.city = address.get("city", "")
            stock.state = address.get("state", "")
            stock.postal_code = address.get("postal_code", "")
            
            stock.market_cap = details.get("market_cap")
            stock.share_class_shares_outstanding = details.get("share_class_shares_outstanding")
            stock.weighted_shares_outstanding = details.get("weighted_shares_outstanding")
            stock.round_lot = details.get("round_lot")
            stock.total_employees = details.get("total_employees")

            stock.save()
            processed += 1
            updated += 1
            
            if processed % 100 == 0:
                logger.info(f"Processed {processed} stock details...")
                
            # Proactively sleep to avoid hitting the 429 Too Many Requests limit
            if delay > 0 and processed < limit:
                time.sleep(delay)

        job.status = DataSyncJob.Status.SUCCESS
        job.records_processed = processed
        logger.info(f"Stock details sync complete. {processed} total, {updated} updated.")
    
    except Exception as e:
        logger.exception("Stock details sync failed")
        job.status = DataSyncJob.Status.FAILED
        job.error = str(e)
    
    finally:
        job.end_time = timezone.now()
        job.save()

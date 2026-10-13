"""
Test database and fixtures.

Every model is managed = False, so Django's test runner creates no tables for
them. django_db_setup is extended to build the test database from sql/ the
same way every other environment is built.
"""

import io
import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("apply_sql", stdout=io.StringIO())


@pytest.fixture(autouse=True)
def local_cache(settings):
    """Tests never touch the developer's Redis."""
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def prototype_stocks(db):
    """
    The prototype's 13 sample stocks, plus an ETF and a delisted company that
    must not appear in listings, with exchanges, sectors and a successful
    reference sync so `as_of` is set.
    """
    from market.classification import display_name
    from market.models import Exchange, Stock
    from sync.models import DataSyncJob
    from sync.services import refresh_sectors

    now = timezone.now()
    rows = json.loads((FIXTURES / "prototype_stocks.json").read_text(encoding="utf-8"))
    stocks = []
    for row in rows:
        market_cap = row.pop("market_cap")
        stocks.append(
            Stock(
                **row,
                display_name=display_name(row["name"]),
                market_cap=Decimal(str(market_cap)).quantize(Decimal("0.01")),
                last_synced_at=now,
                details_synced_at=now,
            )
        )
    stocks.append(Stock(ticker="SPYX", name="Sample ETF", asset_type="ETF", primary_exchange="ARCX"))
    stocks.append(
        Stock(
            ticker="GONE",
            name="Gone Corp",
            display_name="Gone",
            asset_type="CS",
            primary_exchange="XNYS",
            active=False,
            description="A delisted company.",
        )
    )
    Stock.objects.bulk_create(stocks)

    Exchange.objects.bulk_create(
        [
            Exchange(mic="XNAS", name="Nasdaq", display_name="Nasdaq", slug="nasdaq"),
            Exchange(mic="XNYS", name="New York Stock Exchange", display_name="NYSE", slug="nyse"),
            Exchange(mic="ARCX", name="NYSE Arca", display_name="NYSE Arca", slug="nyse-arca"),
        ]
    )
    refresh_sectors()
    DataSyncJob.objects.create(
        job_type=DataSyncJob.JobType.STOCK_DETAILS,
        start_time=now,
        end_time=now,
        status=DataSyncJob.Status.SUCCESS,
    )
    return {s.ticker: s for s in Stock.objects.all()}

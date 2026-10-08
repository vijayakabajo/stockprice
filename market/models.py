"""
Market data models.

Every model here is unmanaged — the tables are defined in sql/, not by Django
migrations. Two rules follow:

  * `db_table` is always explicit. With managed = False an implicit table name
    is a guess about what someone typed in a .sql file.
  * Every Meta inherits `UnmanagedBaseModel.Meta`. A child class that declares
    a bare `class Meta:` silently gets `managed = True` back, and Django starts
    generating DDL for a table it does not own.
"""

from django.db import models

from core.models import UnmanagedBaseModel


class Timespan(models.TextChoices):
    """Intraday bar resolutions we store, and their Massive equivalents."""

    ONE_MINUTE = "1m", "1 minute"
    FIVE_MINUTE = "5m", "5 minutes"
    FIFTEEN_MINUTE = "15m", "15 minutes"
    ONE_HOUR = "1h", "1 hour"

    @property
    def massive_params(self) -> tuple[int, str]:
        """(multiplier, timespan) for the Massive aggregates URL."""
        return {
            "1m": (1, "minute"),
            "5m": (5, "minute"),
            "15m": (15, "minute"),
            "1h": (1, "hour"),
        }[self.value]


class Stock(UnmanagedBaseModel):
    """
    A U.S. listed security. Mirrors Massive's ticker reference data.

    Delisted rows stay, with active = False — historical prices still point at
    them, and a search for a company that no longer trades should still find it.
    """

    # Identity ---------------------------------------------------------------
    ticker = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")
    ticker_root = models.CharField(max_length=20, blank=True, default="")
    ticker_suffix = models.CharField(max_length=20, blank=True, default="")

    # Classification ---------------------------------------------------------
    market = models.CharField(max_length=20, default="stocks")
    locale = models.CharField(max_length=10, default="us")
    # Massive calls this `type`; renamed here so it does not shadow the builtin.
    asset_type = models.CharField(max_length=20, blank=True, default="")
    primary_exchange = models.CharField(max_length=20, blank=True, default="")
    currency_name = models.CharField(max_length=20, default="usd")
    active = models.BooleanField(default=True)

    # External identifiers ---------------------------------------------------
    cik = models.CharField(max_length=20, blank=True, default="")
    composite_figi = models.CharField(max_length=20, blank=True, default="")
    share_class_figi = models.CharField(max_length=20, blank=True, default="")

    # Industry ---------------------------------------------------------------
    sic_code = models.CharField(max_length=10, blank=True, default="")
    sic_description = models.CharField(max_length=255, blank=True, default="")

    # Profile ----------------------------------------------------------------
    description = models.TextField(blank=True, default="")
    homepage_url = models.CharField(max_length=500, blank=True, default="")
    phone_number = models.CharField(max_length=50, blank=True, default="")
    logo_url = models.CharField(max_length=500, blank=True, default="")
    icon_url = models.CharField(max_length=500, blank=True, default="")
    address1 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=50, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")

    # Size -------------------------------------------------------------------
    market_cap = models.DecimalField(max_digits=24, decimal_places=2, null=True, blank=True)
    share_class_shares_outstanding = models.BigIntegerField(null=True, blank=True)
    weighted_shares_outstanding = models.BigIntegerField(null=True, blank=True)
    round_lot = models.IntegerField(null=True, blank=True)
    total_employees = models.IntegerField(null=True, blank=True)

    # Dates ------------------------------------------------------------------
    list_date = models.DateField(null=True, blank=True)
    delisted_utc = models.DateTimeField(null=True, blank=True)

    # Bookkeeping ------------------------------------------------------------
    # Last refresh from the provider, as opposed to updated_at which moves on
    # any write. Drives "which tickers are stale" without a separate job table.
    last_synced_at = models.DateTimeField(null=True, blank=True)
    # Last profile fetch from the ticker-details endpoint, set even when the
    # provider returns nothing, so the details sync can refresh oldest-first.
    details_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Maintained by the market_stock_set_updated_at trigger as well, so rows
    # written by COPY during a backfill are correct too.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(UnmanagedBaseModel.Meta):
        db_table = "market_stock"
        ordering = ["ticker"]
        verbose_name = "stock"
        verbose_name_plural = "stocks"

    def __str__(self):
        return f"{self.ticker} — {self.name}" if self.name else self.ticker


class DailyPrice(UnmanagedBaseModel):
    """
    One split-adjusted OHLCV bar per stock per trading day.

    Primary key is (stock, date). Django 5.2+ supports composite primary keys,
    which is what the table already uses — a surrogate id on a table heading
    for tens of millions of rows buys nothing. The tradeoff: models with a
    composite PK cannot be a ForeignKey target and are not registrable in the
    admin. Neither matters for a price series.
    """

    pk = models.CompositePrimaryKey("stock_id", "date")

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="daily_prices")
    date = models.DateField()

    open = models.DecimalField(max_digits=18, decimal_places=6)
    high = models.DecimalField(max_digits=18, decimal_places=6)
    low = models.DecimalField(max_digits=18, decimal_places=6)
    close = models.DecimalField(max_digits=18, decimal_places=6)
    volume = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    vwap = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    transactions = models.BigIntegerField(null=True, blank=True)

    # Massive returns split-adjusted bars by default and we store that series.
    # Recorded so an unadjusted backfill can never be silently mixed in.
    adjusted = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(UnmanagedBaseModel.Meta):
        db_table = "market_daily_price"
        ordering = ["-date"]
        verbose_name = "daily price"
        verbose_name_plural = "daily prices"

    def __str__(self):
        return f"{self.stock_id} {self.date} close={self.close}"


class IntradayBar(UnmanagedBaseModel):
    """
    Sub-daily OHLCV bars, one row per (stock, resolution, window start).

    `ts` is the start of the aggregate window in UTC. Massive sends Unix
    milliseconds; the sync layer converts. Bars cover pre-market, regular and
    after-hours sessions, and a window with no qualifying trades produces no
    row at all — gaps are data, not errors.
    """

    pk = models.CompositePrimaryKey("stock_id", "timespan", "ts")

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="intraday_bars")
    timespan = models.CharField(max_length=5, choices=Timespan.choices)
    ts = models.DateTimeField()

    open = models.DecimalField(max_digits=18, decimal_places=6)
    high = models.DecimalField(max_digits=18, decimal_places=6)
    low = models.DecimalField(max_digits=18, decimal_places=6)
    close = models.DecimalField(max_digits=18, decimal_places=6)
    volume = models.DecimalField(max_digits=20, decimal_places=4, default=0)
    vwap = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    transactions = models.BigIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(UnmanagedBaseModel.Meta):
        db_table = "market_intraday_bar"
        ordering = ["-ts"]
        verbose_name = "intraday bar"
        verbose_name_plural = "intraday bars"

    def __str__(self):
        return f"{self.stock_id} {self.timespan} {self.ts:%Y-%m-%d %H:%M} close={self.close}"

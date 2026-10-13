"""
Exchange and sector labels for a request.

market_stock holds the MIC and SIC code with no foreign key to these tables.
Both are small (tens of exchanges, a few hundred sectors), so each request
loads them once and resolves labels in memory instead of joining per row.
"""

from django.db.models import Max

from market.models import Exchange, Sector
from market.universe import NOT_CLASSIFIED
from sync.models import DataSyncJob


class Labels:
    def __init__(self):
        self.exchanges = {e.mic: e for e in Exchange.objects.all()}
        self.sectors = {s.sic_code: s for s in Sector.objects.all()}
        self.exchange_by_slug = {e.slug: e for e in self.exchanges.values()}
        self.sector_by_slug = {s.slug: s for s in self.sectors.values()}

    def exchange(self, mic):
        exchange = self.exchanges.get(mic)
        if exchange is None:
            return None
        return {"slug": exchange.slug, "name": exchange.display_name}

    def sector(self, sic_code):
        sector = self.sectors.get(sic_code)
        if sector is None:
            return dict(NOT_CLASSIFIED)
        return {"slug": sector.slug, "name": sector.name}


def reference_as_of():
    """
    When the reference data was last refreshed: the latest successful ticker
    or profile sync. None if neither has ever succeeded.
    """
    return DataSyncJob.objects.filter(
        job_type__in=[DataSyncJob.JobType.STOCK_MASTER, DataSyncJob.JobType.STOCK_DETAILS],
        status=DataSyncJob.Status.SUCCESS,
    ).aggregate(latest=Max("end_time"))["latest"]

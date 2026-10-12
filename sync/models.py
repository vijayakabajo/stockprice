from django.db import models
from core.models import UnmanagedBaseModel


class DataSyncJob(UnmanagedBaseModel):
    """
    Log of data synchronization operations.
    Used to track successful runs, failures, and prevent silent stale-data problems.
    """

    class JobType(models.TextChoices):
        STOCK_MASTER = "stock_master", "Stock Master (Tickers)"
        STOCK_DETAILS = "stock_details", "Stock Details (Profiles)"
        DAILY_PRICES = "daily_prices", "Daily Prices"
        EXCHANGES = "exchanges", "Exchanges"
        SECTORS = "sectors", "Sectors"
        # Others can be added later

    class Status(models.TextChoices):
        STARTED = "started", "Started"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    job_type = models.CharField(max_length=50, choices=JobType.choices)
    provider = models.CharField(max_length=50, default="massive")
    data_date = models.DateField(null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.STARTED)
    records_processed = models.IntegerField(default=0)
    error = models.TextField(blank=True, null=True)

    class Meta(UnmanagedBaseModel.Meta):
        db_table = "sync_data_sync_job"
        ordering = ["-start_time"]
        verbose_name = "data sync job"
        verbose_name_plural = "data sync jobs"

    def __str__(self):
        return f"{self.job_type} on {self.data_date or self.start_time.date()} - {self.status}"

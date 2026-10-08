from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from sync.services import SyncAlreadyRunning, last_final_session_date, sync_daily_prices


class Command(BaseCommand):
    help = "Pulls whole-market daily OHLCV bars from Massive API and upserts them into DailyPrice."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=date.fromisoformat,
            default=None,
            help="Session to sync, YYYY-MM-DD (default: the last completed session)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Backfill this many calendar days ending at --date (weekends are skipped)",
        )

    def handle(self, *args, **options):
        end = options["date"] or last_final_session_date()
        days = [end - timedelta(days=i) for i in range(options["days"])]
        days = sorted(d for d in days if d.weekday() < 5)

        for day in days:
            self.stdout.write(self.style.NOTICE(f"Syncing daily prices for {day}..."))
            try:
                sync_daily_prices(day)
            except SyncAlreadyRunning as e:
                raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS("Finished daily price sync! Check logs for details."))

from django.core.management.base import BaseCommand, CommandError

from sync.services import SyncAlreadyRunning, sync_stock_details


class Command(BaseCommand):
    help = "Refreshes stock profile details from Massive API, never-fetched first, then oldest."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of stocks to process in this run (default: all active)",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.0,
            help="Seconds to wait between requests, for rate-limited plans (forces one worker)",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=8,
            help="Concurrent API requests (default: 8)",
        )

    def handle(self, *args, **options):
        limit, delay, workers = options["limit"], options["delay"], options["workers"]
        self.stdout.write(
            self.style.NOTICE(
                f"Starting stock details sync (limit={limit}, delay={delay}s, workers={workers})..."
            )
        )
        try:
            sync_stock_details(limit=limit, delay=delay, workers=workers)
        except SyncAlreadyRunning as e:
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS("Finished stock details sync! Check logs for details."))

from django.core.management.base import BaseCommand
from sync.services import sync_stock_details

class Command(BaseCommand):
    help = "Fetches missing stock profile details from Massive API and updates the local database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=1000,
            help='Maximum number of stocks to process in this run'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=13.0,
            help='Seconds to wait between requests (default: 13s for 5/min rate limit)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        delay = options['delay']
        self.stdout.write(self.style.NOTICE(f"Starting stock details sync (limit={limit}, delay={delay}s)..."))
        sync_stock_details(limit=limit, delay=delay)
        self.stdout.write(self.style.SUCCESS("Finished stock details sync! Check logs for details."))

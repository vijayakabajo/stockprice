from django.core.management.base import BaseCommand
from sync.services import sync_stocks

class Command(BaseCommand):
    help = "Pulls stock tickers from Massive API and updates the local database."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting stock master sync..."))
        sync_stocks()
        self.stdout.write(self.style.SUCCESS("Finished stock master sync! Check logs for details."))

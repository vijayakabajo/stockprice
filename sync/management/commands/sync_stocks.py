from django.core.management.base import BaseCommand, CommandError

from sync.services import SyncAlreadyRunning, sync_stocks


class Command(BaseCommand):
    help = "Pulls stock tickers from Massive API and updates the local database."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting stock master sync..."))
        try:
            sync_stocks()
        except SyncAlreadyRunning as e:
            raise CommandError(str(e))
        self.stdout.write(self.style.SUCCESS("Finished stock master sync! Check logs for details."))

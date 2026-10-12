from django.core.management.base import BaseCommand, CommandError

from sync.services import SyncAlreadyRunning, sync_exchanges


class Command(BaseCommand):
    help = "Pulls the U.S. stock exchange list from Massive API (one call)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting exchange sync..."))
        try:
            sync_exchanges()
        except SyncAlreadyRunning as e:
            raise CommandError(str(e)) from e
        self.stdout.write(self.style.SUCCESS("Finished exchange sync! Check logs for details."))

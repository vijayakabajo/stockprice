from django.core.management.base import BaseCommand, CommandError

from sync.services import SyncAlreadyRunning, refresh_sectors


class Command(BaseCommand):
    help = "Adds a sector row for every SIC code in use. No API calls."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Refreshing sectors..."))
        try:
            refresh_sectors()
        except SyncAlreadyRunning as e:
            raise CommandError(str(e)) from e
        self.stdout.write(self.style.SUCCESS("Finished sector refresh! Check logs for details."))

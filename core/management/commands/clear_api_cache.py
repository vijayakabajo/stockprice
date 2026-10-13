from django.core.management.base import BaseCommand

from core.cache import bump_data_version


class Command(BaseCommand):
    help = (
        "Retires every cached API response by bumping the data version. Syncs do "
        "this on their own; run it after deploying code that changes a response."
    )

    def handle(self, *args, **options):
        bump_data_version()
        self.stdout.write(self.style.SUCCESS("API response cache cleared."))

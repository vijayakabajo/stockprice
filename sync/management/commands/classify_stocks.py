from django.core.management.base import BaseCommand

from sync.services import classify_stocks


class Command(BaseCommand):
    help = "Recomputes every stock's display_name from its stored name. No API calls."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Recomputing display names..."))
        changed = classify_stocks()
        self.stdout.write(self.style.SUCCESS(f"Finished! {changed} display name(s) changed."))

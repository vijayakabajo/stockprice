from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from web import indexnow


class Command(BaseCommand):
    help = (
        "Submits changed URLs to IndexNow. By default: profiles refreshed in the last 24 hours plus the hubs. "
        "Use after publishing a guide (--guides) or to resubmit everything (--all)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24, help="Profiles refreshed in the last N hours.")
        parser.add_argument("--all", action="store_true", help="Every indexable page.")
        parser.add_argument("--guides", action="store_true", help="Guide pages only.")
        parser.add_argument(
            "--url", action="append", default=[], help="A specific absolute URL (repeatable)."
        )
        parser.add_argument("--dry-run", action="store_true", help="Print the URLs instead of submitting.")

    def handle(self, *args, **options):
        if options["url"]:
            urls = options["url"]
        elif options["guides"]:
            urls = indexnow.guide_urls()
        elif options["all"]:
            urls = indexnow.hub_urls() + indexnow.guide_urls() + indexnow.stock_urls()
        else:
            since = timezone.now() - timedelta(hours=options["hours"])
            urls = indexnow.stock_urls(since) + indexnow.hub_urls()

        if options["dry_run"]:
            for url in urls:
                self.stdout.write(url)
            self.stdout.write(f"{len(urls)} URL(s).")
            return
        if not settings.INDEXNOW_ENABLED:
            raise CommandError(
                "IndexNow is disabled: set INDEXNOW_KEY (and INDEXNOW_ENABLED=True outside production)."
            )
        submitted = indexnow.submit(urls)
        self.stdout.write(self.style.SUCCESS(f"Submitted {submitted} URL(s) to IndexNow."))

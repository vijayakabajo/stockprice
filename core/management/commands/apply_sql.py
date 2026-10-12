"""
Applies the .sql files in sql/ that have not been applied yet.

Every model in this project is managed = False, so Django's migration system
never emits DDL. This command is what actually builds the schema. See
sql/README.md for the rules the files follow.
"""

import hashlib
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections

TRACKING_TABLE = "schema_migrations"

CREATE_TRACKING_TABLE = f"""
CREATE TABLE IF NOT EXISTS {TRACKING_TABLE} (
    filename    VARCHAR(255) PRIMARY KEY,
    checksum    VARCHAR(64)  NOT NULL,
    applied_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
)
"""

# Files that cannot run inside a transaction (CREATE INDEX CONCURRENTLY,
# ALTER TYPE ... ADD VALUE, and friends).
NO_TRANSACTION_SUFFIX = ".noxact.sql"


def sql_dir() -> Path:
    return Path(settings.BASE_DIR) / "sql"


def checksum(text: str) -> str:
    # Normalise line endings so a Windows checkout and a Linux CI runner agree.
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


class Command(BaseCommand):
    help = "Apply pending .sql files from the sql/ directory."

    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default=DEFAULT_DB_ALIAS,
            help="Database alias to apply against. Defaults to 'default'.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be applied without changing anything.",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            dest="list_only",
            help="Show applied and pending files, then exit.",
        )
        parser.add_argument(
            "--fake",
            nargs="+",
            metavar="FILE",
            help=(
                "Record these pending files as applied without running them. For a "
                "database whose tables were created before it was tracked."
            ),
        )

    def handle(self, *args, **options):
        directory = sql_dir()
        if not directory.is_dir():
            raise CommandError(f"No sql/ directory at {directory}")

        files = sorted(p for p in directory.glob("*.sql") if p.is_file())
        if not files:
            self.stdout.write("No .sql files found.")
            return

        connection = connections[options["database"]]
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TRACKING_TABLE)
            cursor.execute(f"SELECT filename, checksum FROM {TRACKING_TABLE}")
            applied = dict(cursor.fetchall())

        pending = []
        for path in files:
            digest = checksum(path.read_text(encoding="utf-8"))
            recorded = applied.get(path.name)
            if recorded is None:
                pending.append((path, digest))
            elif recorded != digest:
                # Rule 1 in sql/README.md. An applied file is immutable —
                # every other environment already ran the old contents.
                raise CommandError(
                    f"{path.name} changed after it was applied.\n"
                    f"  recorded: {recorded}\n"
                    f"  on disk:  {digest}\n"
                    "Restore the file and add a new one with your change instead."
                )

        if options["list_only"]:
            for path in files:
                mark = "applied" if path.name in applied else "PENDING"
                self.stdout.write(f"  [{mark:>7}] {path.name}")
            return

        if options["fake"]:
            self._fake(connection, pending, options["fake"], options["dry_run"])
            return

        if not pending:
            self.stdout.write(self.style.SUCCESS("Schema is up to date."))
            return

        for path, digest in pending:
            if options["dry_run"]:
                self.stdout.write(f"  would apply {path.name}")
                continue
            self._apply(connection, path, digest)

        if options["dry_run"]:
            self.stdout.write(f"\n{len(pending)} file(s) pending. Nothing was changed.")
        else:
            self.stdout.write(self.style.SUCCESS(f"\nApplied {len(pending)} file(s)."))

    def _fake(self, connection, pending, names, dry_run):
        # Only pending files can be faked: faking an applied file would hide a
        # checksum change, and an unknown name is almost certainly a typo.
        pending_by_name = {path.name: digest for path, digest in pending}
        unknown = [name for name in names if name not in pending_by_name]
        if unknown:
            raise CommandError(f"Not pending (or not in sql/): {', '.join(unknown)}")

        record = f"INSERT INTO {TRACKING_TABLE} (filename, checksum) VALUES (%s, %s)"
        for name in names:
            if dry_run:
                self.stdout.write(f"  would fake {name}")
                continue
            with connection.cursor() as cursor:
                cursor.execute(record, [name, pending_by_name[name]])
            self.stdout.write(f"  faked {name}")

    def _apply(self, connection, path: Path, digest: str):
        body = path.read_text(encoding="utf-8")
        record = f"INSERT INTO {TRACKING_TABLE} (filename, checksum) VALUES (%s, %s)"

        if path.name.endswith(NO_TRANSACTION_SUFFIX):
            # Caller is responsible for the file being safe to re-run, since a
            # failure partway through leaves it unrecorded and it will be
            # retried from the top next time.
            with connection.cursor() as cursor:
                cursor.execute(body)
                cursor.execute(record, [path.name, digest])
        else:
            with connection.cursor() as cursor:
                cursor.execute("BEGIN")
                try:
                    cursor.execute(body)
                    cursor.execute(record, [path.name, digest])
                    cursor.execute("COMMIT")
                except Exception:
                    cursor.execute("ROLLBACK")
                    raise

        self.stdout.write(f"  applied {path.name}")

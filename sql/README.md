# sql/ — the schema of record

Every model in this project is `managed = False`. Django does **not** create,
alter, or drop tables. This directory is the only place the schema is defined.

If a change is not in a file here, it does not exist.

---

## Rules

1. **One change, one new file.** Never edit a file that has already been
   applied anywhere — not on your machine, not on staging. A file that has run
   is immutable. Corrections go in a new file.
2. **Sequential, zero-padded prefixes.** `0007_add_stock_sector.sql`. The
   number decides the order; the rest of the name says what it does.
3. **Idempotent where possible.** `CREATE TABLE IF NOT EXISTS`,
   `CREATE INDEX IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`. Re-running a file
   should not be an error.
4. **Every file is one transaction.** `apply_sql` wraps each file in
   `BEGIN`/`COMMIT` — a file either fully applies or does not apply at all.
   The exception is `CREATE INDEX CONCURRENTLY`, which cannot run inside a
   transaction; put those in a file whose name ends `.noxact.sql`.
5. **Mirror the change in `models.py` in the same commit.** The table and the
   model drift the moment you allow them to.

## Naming

```
0000_extensions.sql              extensions, shared functions, triggers
0001_create_market_stock.sql     one table per file where practical
0002_create_market_daily_price.sql
0003_create_market_intraday_bar.sql
0007_add_stock_sector.sql        later alterations
0012_backfill_vwap.noxact.sql    anything that can't be transactional
```

Table names are `<app>_<model>` in snake_case — `market_stock`,
`market_daily_price`. This matches what Django would have generated, so
`db_table` stays predictable. Every model still sets `db_table` explicitly,
because with `managed = False` an implicit name is a guess.

## Applying

```bash
python manage.py apply_sql
```

Runs every file that has not been applied yet, in order, recording each one in
a `schema_migrations` table alongside a SHA-256 of its contents.

```bash
python manage.py apply_sql --list          # what is applied, what is pending
python manage.py apply_sql --dry-run       # show what would run, change nothing
python manage.py apply_sql --database=...  # target a non-default connection
```

If a file's checksum no longer matches what was recorded, `apply_sql` stops and
tells you which file changed. That is rule 1 catching you. Restore the file and
write a new one instead.

## Tests

`tests/conftest.py` runs this directory against the test database before any
test — unmanaged models otherwise mean a test database with no tables at all.
A `.sql` file that fails on an empty database fails the whole test run.

## Conventions inside the SQL

- **Timestamps are `TIMESTAMPTZ`.** Never `TIMESTAMP`. The application handles
  U.S. market sessions from a server that may be in any timezone; a naive
  timestamp is a bug waiting for the next DST transition.
- **Money and prices are `NUMERIC`, never `float`.** `NUMERIC(18, 6)` for
  prices — enough for sub-penny quotes and for a six-figure share price.
- **`created_at` / `updated_at` on every table.** `updated_at` is maintained by
  the `set_updated_at()` trigger from `0000_extensions.sql`, not by Django, so
  it stays correct for rows written by bulk COPY and by hand.
- **Foreign keys are declared.** Unmanaged does not mean unconstrained. The
  database is the last line of defence against a sync task writing prices for
  a ticker that was never imported.

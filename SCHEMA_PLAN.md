# Schema Plan — models and tables

How a table gets built in this project, and what gets built next.

Companion to [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) (architecture) and
[sql/README.md](sql/README.md) (the rules the `.sql` files follow).

---

## The workflow

Every model is `managed = False`. Django maps onto a schema it does not own.
So each change moves through five steps, in this order, in one commit:

```
1. Write the SQL        sql/000N_<verb>_<table>.sql
2. Apply it             python manage.py apply_sql
3. Write the model      <app>/models.py, Meta(UnmanagedBaseModel.Meta) + db_table
4. Record the state     python manage.py makemigrations <app>     # state only, no DDL
5. Sanity-check it      manage.py shell, or a request against the API
```

**SQL first, model second.** The table is the fact; the model is a description
of it. Writing the model first invites a description of a table nobody created.

### Step 4 is not optional

`makemigrations` on an unmanaged model produces a migration that emits **no
DDL** — verified:

```
$ python manage.py sqlmigrate market 0001
BEGIN;
-- Create model DailyPrice
-- (no-op)
...
COMMIT;
```

It is worth generating anyway: it records which models exist and their Meta,
so `makemigrations --check --dry-run` flags a model added, removed, or switched
back to `managed = True`.

**It does not catch field drift.** Django's autodetector ignores field changes
on unmanaged models — verified when `display_name`, `security_type` and
`size_bucket` were added to `Stock` and `makemigrations market` reported only
the two new models. A field added, removed or retyped on one side only goes
unnoticed until a query fails. Until something compares models against
`information_schema`, that check is a code-review job.

### Two traps specific to `managed = False`

**Meta inheritance.** `UnmanagedBaseModel` sets `managed = False` on its
`Meta`. A child that declares a bare `class Meta:` does **not** inherit it —
Django defaults `managed` back to `True` and starts generating DDL for a table
you own by hand. Always:

```python
class Meta(UnmanagedBaseModel.Meta):   # not `class Meta:`
    db_table = "market_stock"
```

**A test database would be empty.** Django creates no tables for unmanaged
models, so every ORM test would fail on a missing relation. `tests/conftest.py`
extends pytest-django's `django_db_setup` to run `apply_sql` against the test
database, so it is built exactly like every other environment.

---

## What exists now

```
sql/
├── README.md
├── 0000_extensions.sql               pg_trgm, set_updated_at() trigger function
├── 0001_create_market_stock.sql      market_stock
├── 0002_create_market_daily_price.sql  market_daily_price
├── 0003_create_market_intraday_bar.sql market_intraday_bar
├── 0004_sync_data_sync_job.sql       sync_data_sync_job
├── 0005_add_stock_details_synced_at.sql
├── 0006_create_market_exchange.sql   market_exchange
├── 0007_create_market_sector.sql     market_sector
└── 0008_add_stock_classification.sql display_name; generated security_type, size_bucket

market/
├── models.py          Stock, Exchange, Sector, DailyPrice, IntradayBar, choices
├── classification.py  display-name and sector-name rules
├── admin.py           Stock read-only; Exchange/Sector editorial fields editable
└── migrations/        state only, no DDL
```

**Generated columns.** `security_type` and `size_bucket` are computed by
Postgres and mapped as `GeneratedField`, so Django never writes them. The
model repeats the SQL expression only because `GeneratedField` requires one;
the SQL is what runs. Change both together, in a new `.sql` file that drops
and re-adds the column.

Applied and smoke-tested against the dev database: rows insert, the composite
primary keys resolve, reverse FK traversal works, the OHLC check constraints
hold.

### Decisions worth knowing

| Decision | Why |
|---|---|
| Surrogate `id` on `market_stock`, unique `ticker` | Prices reference a stable id, so a ticker rename does not orphan history. |
| Composite PK `(stock_id, date)` on prices | The PK *is* the access path for every chart query. A surrogate id would add 8 bytes and a second index for nothing on a table heading for tens of millions of rows. Django 5.2+ `CompositePrimaryKey` maps it. |
| `NUMERIC`, never float, for prices | Binary floats cannot represent `0.1`. Money does not tolerate that. |
| `TIMESTAMPTZ` everywhere | See gap 1 in the overview: the app's timezone and the market's are not the same, and DST moves one of them twice a year. |
| `updated_at` by trigger, not only Django | A bulk `COPY` during backfill never runs `save()`. The trigger is correct for every writer. |
| OHLC `CHECK` constraints | A bar whose high is not the highest is a field-mapping bug in the sync task. Catch it on write, not six months later on a chart. |
| Delisted rows kept (`active = false`) | Historical prices still reference them, and a search for a company that stopped trading should still find it. |
| `asset_type`, not `type` | Massive calls it `type`; renamed so it does not shadow the builtin. |
| `Stock` admin is read-only | A sync task overwrites anything typed there on its next run. Better to not offer the edit. |

### Known limits of what is built

- **`CompositePrimaryKey` models cannot be a ForeignKey target** and cannot be
  registered in the Django admin. Neither is wanted for a price series, but it
  is a real constraint if a future model wants to point at a specific bar.
- **`UNIQUE (ticker)`** assumes a symbol is never reassigned. Exchanges do
  reassign delisted symbols after a few years. If that bites, the constraint
  becomes a partial unique index on `(ticker) WHERE active` with
  `composite_figi` as the stable identity. Noted in the SQL, not solved.
- **`market_intraday_bar` is not partitioned.** It is the table that grows
  fastest (~480k rows/day at 500 tickers on 1-minute bars). Partitioning an
  empty table is speculation; converting later is contained while the
  retention window is short. Retention policy has to land with the sync task,
  not after.

---

## What gets built next

Each row is one `sql/` file plus one model, in the order they unblock each other.

### Phase 2 — first data through the pipe

| # | Table | Model | Notes |
|---|---|---|---|
| 0004 | `sync_data_sync_job` | `sync.DataSyncJob` | job type, provider, data date, start/end, status, records processed, error. Ships **with** the first sync task, not after — it is what makes stale data loud instead of silent. |

Needs a new `sync` app, and `data_provider/` alongside it (no models — the
Massive client, retries, rate limiting, and response→model mapping).

**Done when** `GET /api/v1/stocks/AAPL/` returns real data imported from
`/v3/reference/tickers`.

### Phase 3–4 — history

No new tables. `market_daily_price` and `market_intraday_bar` already exist;
this phase fills them via Flat Files for the backfill and the grouped daily
endpoint for the nightly sync. Expect one `sql/` file here for indexes that
only reveal themselves under real data volume.

### Phase 6 — fundamentals

| # | Table | Model | Source |
|---|---|---|---|
| 00NN | `fundamentals_financial_statement` | `FinancialStatement` | `/stocks/financials/v1/{income-statements,balance-sheets,cash-flow-statements}` |
| 00NN | `fundamentals_financial_ratio` | `FinancialRatio` | `/stocks/financials/v1/ratios` |
| 00NN | `market_dividend` | `Dividend` | `/v3/reference/dividends` |
| 00NN | `market_stock_split` | `StockSplit` | `/v3/reference/splits` |
| 00NN | `market_ticker_event` | `TickerEvent` | `/vX/reference/tickers/{id}/events` |

Statements are keyed by `(stock, fiscal_period, fiscal_year, timeframe)` and
**appended, never overwritten** — restatements are data, and a ratio computed
against a silently replaced figure is unexplainable later.

Ratios that are cheap to derive (P/E, P/B, D/E) are computed on read from
stored figures rather than stored, so they cannot go stale against the price.
Ratios the provider gives directly are stored as provided.

### Phase 7 — search and market features

Likely no new tables. `market_stock_name_trgm_idx` already backs name search.
Movers come from the snapshot endpoint through Redis, not from a table.

### Later

`market_announcement` / filings, and the user-facing tables (watchlists,
alerts). Both wait for the data layer to be boring first.

---

## Immediate follow-ups

1. ~~**`accounts_user` is not under this convention yet.**~~ **Resolved:** the
   `accounts` app was removed, since the site has no user accounts. Django's
   own tables (auth for the admin login, sessions, admin log) are the one
   deliberate exception to SQL ownership and come from `manage.py migrate`.
2. ~~**Timezone.**~~ **Resolved:** UTC throughout.
3. **CI gate.** Add `makemigrations --check --dry-run` and `apply_sql` to
   `.github/workflows/ci.yml` so drift and unapplied SQL fail the build.

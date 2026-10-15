# ShockPrices

A U.S. stock market data backend. Django + DRF over market data from
[Massive](https://massive.com), with the database schema owned as SQL rather
than by Django migrations.

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — architecture, Massive API reference, roadmap
- [SCHEMA_PLAN.md](SCHEMA_PLAN.md) — how models and tables get built, and what's next
- [sql/README.md](sql/README.md) — the rules the `.sql` files follow
- [stockprices_planning.md](stockprices_planning.md) — feature roadmap
- [API.md](API.md) — API reference with curl examples; Postman collection in [postman/](postman/)

## Stack

- Django 6 + Django REST Framework
- PostgreSQL
- Redis — cache backend and Celery broker/result backend
- Celery — background sync tasks (worker + beat)
- No user accounts: the API is public and read-only. Django's auth app only
  backs the admin login.
- `pytest` + `pytest-django` for tests
- `ruff` + `black` for lint/format

## The one thing to know first

**Every model is `managed = False`.** Django does not create, alter, or drop
tables. `manage.py migrate` will not build this schema — `manage.py apply_sql`
will. If a table is not defined in `sql/`, it does not exist.

## Project structure

```
app/            Django project config (settings, urls, wsgi/asgi, celery bootstrap)
  config/       Settings split by concern: cors.py, database.py, redis.py,
                rest_framework.py, celery.py, logger.py — each returns a config
                dict/list consumed by settings.py.
core/           Cross-cutting concerns: UnmanagedBaseModel, the api_response()
                envelope, the DRF exception handler, pagination, health check,
                and the apply_sql management command.
market/         Stock, Exchange, Sector, DailyPrice, IntradayBar, the page API
                (/api/v1/...) and the page payloads it shares with the site.
web/            The public, server-rendered site: views, templates, SEO,
                sitemaps, IndexNow. Built assets in web/static/web/.
assets/         CSS and JS sources for the site; `npm run build` compiles them.
scripts/        Asset and image build scripts, and verify_site.py.
sync/           Sync jobs: services, Celery tasks, management commands, DataSyncJob.
data_provider/  The Massive client — the only code that knows the provider.
tests/          pytest suite; builds the test database from sql/.
sql/            The schema of record. One file per change, applied in order.
requirements/   base.txt / dev.txt / prod.txt
secrets/        Per-environment secret files loaded on top of .env. Only
                *.example files are committed.
```

## Quickstart

Requires a running PostgreSQL and Redis.

```bash
python -m venv .venv
source .venv/bin/activate            # .venv\Scripts\activate on Windows
pip install -r requirements/dev.txt
cp .env.example .env                 # fill in DB_*/REDIS_*/MASSIVE_API_KEY
python manage.py migrate             # Django's own tables (admin, auth, sessions)
python manage.py apply_sql           # our schema — this is the one that matters
python manage.py createsuperuser     # admin login, for editing sector/exchange labels
python manage.py runserver
```

Celery worker and beat, in separate terminals. Beat only enqueues; the worker
does the syncing. On Windows add `--pool=solo` to the worker (prefork is
unsupported there, and task time limits are not enforced):

```bash
celery -A app worker --loglevel=info
celery -A app beat --loglevel=info
```

Scheduled syncs (UTC, defined in `app/config/celery.py`):

| Task | When | What |
|---|---|---|
| `sync_reference_data_task` | daily 01:15 | ticker master, then company profiles, then sectors |
| `sync_daily_prices_task` | Tue–Sat 01:45 | the day's OHLCV for every stock, plus any recent session that failed |
| `sync_exchanges_task` | 1st of the month 01:00 | exchange list (one API call) |

The same jobs run by hand: `sync_stocks`, `sync_stock_details [--limit N]`,
`sync_daily_prices [--date YYYY-MM-DD] [--days N]`, `sync_exchanges`, and
`refresh_sectors` (no API calls). `classify_stocks` recomputes every display
name after the naming rules in `market/classification.py` change. Every run is
logged to `sync_data_sync_job`, and a Redis lock stops two runs of one job
overlapping.

On the free Massive tier (5 calls/minute) the client waits out each 429, so
even a one-call job can take a few minutes.

`http://localhost:8000/` returns landing JSON, `/api/health/` checks the
database and cache, `/admin/` is the Django admin.

## Schema changes

```bash
make sql-list        # what's applied, what's pending
make apply-sql       # apply pending sql/ files
make check-drift     # any output means a model disagrees with its .sql file
```

A database whose tables were built before `apply_sql` tracked them shows every
file as pending. Record the ones already in place, then apply the rest:

```bash
python manage.py apply_sql --fake 0000_extensions.sql 0001_create_market_stock.sql ...
```

The full workflow — SQL first, then the model, then `makemigrations` to record
state — is in [SCHEMA_PLAN.md](SCHEMA_PLAN.md). An applied `.sql` file is
immutable; `apply_sql` verifies checksums and refuses if one changed.

## Environment & secrets

Config comes from environment variables, loaded in this order (later wins):

1. `.env` — base config for all environments (not committed)
2. `secrets/.env.<ENV_TYPE>.secrets` — selected by `ENV_TYPE`
   (`local` / `preproduction` / `production`)

Copy `.env.example` to `.env`, and the relevant
`secrets/.env.<env>.secrets.example` to `secrets/.env.<env>.secrets`. Both real
files are gitignored — never commit them.

## API conventions

Every endpoint returns the same envelope via `core.response.api_response()`:

```json
{"success": true, "message": "...", "data": {...}}
{"success": false, "message": "...", "data": null, "errors": {...}}
```

`core.exceptions.custom_exception_handler` reshapes every DRF exception into the
same envelope globally, so views don't have to remember to.

The API is public and read-only (GET only, no login). Endpoints, all under
`/api/v1/`:

| Endpoint | Serves |
|---|---|
| `overview/` | Home: headline stats, counts by sector/exchange/size, largest companies |
| `stocks/?exchange=&type=&sector=&size=&q=&ordering=&page=&page_size=` | Directory and hub company tables |
| `stocks/{ticker}/` | Stock profile (case-insensitive; dotted tickers like `BRK.A` work) |
| `stocks/{ticker}/peers/` | Market cap rank and context, peers, related companies |
| `sectors/`, `sectors/{slug}/` | Sector index and hub (`not-classified` included) |
| `exchanges/`, `exchanges/{slug}/` | Exchange index and hub |
| `search/?q=` | Typeahead: exact ticker, ticker prefix, then fuzzy name |
| `sitemap/` | Every indexable stock, sector and exchange with `lastmod` |

Rules every endpoint follows:

- Only active common stock, ADRs and SPACs have pages (`market/universe.py`);
  anything else is a 404. Every row carries `indexable`: SPACs, inactive
  stocks, stocks without a description and hubs with fewer than 3 companies
  are `false`.
- Lists and hubs carry `as_of`, the last successful ticker or profile sync; a
  profile carries its own last fetch.
- Missing values are `null`, never `""`. Market cap, shares and employees are
  JSON numbers. Unknown filter values are a 400 listing the valid ones.
- Responses are cached in Redis per **data version**, which every successful
  sync bumps (`core/cache.py`), and carry `ETag` and
  `Cache-Control: public, max-age=300`. A matching `If-None-Match` gets a 304.
  After deploying code that changes a response, run
  `python manage.py clear_api_cache`.

Full reference with curl examples: [API.md](API.md). For manual testing,
import `postman/StockPrices.postman_collection.json` and
`postman/StockPrices.local.postman_environment.json` into Postman.

## Adding a new app

1. `python manage.py startapp <name>`
2. Add it to `LOCAL_APPS` in `app/settings.py`
3. Write the table in `sql/` and apply it **before** writing the model
4. Inherit `core.models.UnmanagedBaseModel`, and write
   `class Meta(UnmanagedBaseModel.Meta):` — a bare `class Meta:` silently
   re-enables `managed = True`
5. Set `db_table` explicitly
6. `python manage.py makemigrations <name>` to record state (emits no DDL)
7. Use `core.response.api_response()` in views, wire `urls.py` into `app/urls.py`

## Lint & format

```bash
make lint     # ruff check + black --check
make format   # ruff --fix + black
```

Optionally install the pre-commit hooks so these run on `git commit`:

```bash
pre-commit install
```

## Tests

```bash
pytest
```

Needs a reachable PostgreSQL (pytest-django creates `test_<DB_NAME>`); Redis is
not needed, tests use an in-memory cache. Unmanaged models mean Django creates
no tables for the test database, so `tests/conftest.py` runs `apply_sql`
against it first. API tests run against the prototype's 13 sample stocks
(`tests/fixtures/prototype_stocks.json`), so expected values are the ones the
prototype pages show.

## CI

`.github/workflows/ci.yml` runs `ruff` and `black --check` on every push and PR
to `main`.

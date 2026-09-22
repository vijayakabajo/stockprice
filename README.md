# ShockPrices

A U.S. stock market data backend. Django + DRF over market data from
[Massive](https://massive.com), with the database schema owned as SQL rather
than by Django migrations.

- [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) — architecture, Massive API reference, roadmap
- [SCHEMA_PLAN.md](SCHEMA_PLAN.md) — how models and tables get built, and what's next
- [sql/README.md](sql/README.md) — the rules the `.sql` files follow
- [stockprices_planning.md](stockprices_planning.md) — feature roadmap

## Stack

- Django 6 + Django REST Framework
- PostgreSQL
- Redis — cache backend and Celery broker/result backend
- Celery — background sync tasks (worker + beat)
- JWT auth (`djangorestframework_simplejwt`)
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
accounts/       Custom User model (email login) + register/login/refresh/me.
market/         Stock, DailyPrice, IntradayBar — the market data models.
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
python manage.py migrate             # third-party tables (auth, sessions, admin)
python manage.py apply_sql           # our schema — this is the one that matters
python manage.py runserver
```

Celery worker and beat, in separate terminals, once there are tasks to run:

```bash
celery -A app worker --loglevel=info
celery -A app beat --loglevel=info
```

`http://localhost:8000/` returns landing JSON, `/api/health/` checks the
database and cache, `/admin/` is the Django admin.

## Schema changes

```bash
make sql-list        # what's applied, what's pending
make apply-sql       # apply pending sql/ files
make check-drift     # any output means a model disagrees with its .sql file
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

Auth: get tokens from `POST /api/v1/auth/login/` or `/register/`, then send
`Authorization: Bearer <access>`. Refresh at `POST /api/v1/auth/refresh/`.

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

There are none right now — deliberately out of scope. Bringing them back means
reinstating pytest in `requirements/dev.txt`, a `[tool.pytest.ini_options]`
block in `pyproject.toml`, and a `conftest.py` that runs `apply_sql` against the
test database. That last part is not optional: unmanaged models mean Django
creates no tables for the test database, so without it every ORM test fails on
a missing relation.

## CI

`.github/workflows/ci.yml` runs `ruff` and `black --check` on every push and PR
to `main`.

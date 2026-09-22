# shareprice

A Django + Django REST Framework boilerplate: JWT auth on a custom user model, a
standard API response envelope, health checks, Celery, Redis caching, and Docker —
meant to be cloned as the starting point for new backend projects.

## Stack

- Django 6 + Django REST Framework
- MySQL (via `mysqlclient`)
- Redis — cache backend and Celery broker/result-backend
- Celery — background tasks (worker + beat)
- JWT auth (`djangorestframework_simplejwt`)
- pytest + pytest-django for tests, `ruff` + `black` for lint/format

## Project structure

```
app/                  Django project config (settings, urls, wsgi/asgi, celery bootstrap)
  config/             Settings split by concern: cors.py, database.py, redis.py,
                       rest_framework.py, celery.py, logger.py — each returns a
                       config dict/list consumed by settings.py. Add new concerns
                       (e.g. sentry.py, storages.py) the same way.
accounts/              Reference app: custom User model (email login), register/
                       login/refresh/me endpoints. Copy this app's shape
                       (models/managers/serializers/views/urls/admin/tests) for
                       every new app you add.
core/                  Cross-cutting concerns shared by every app: the
                       api_response() envelope, the custom DRF exception handler,
                       pagination, health check, and the GCS helper.
content/               Static assets (fonts, default images).
requirements/          base.txt / dev.txt / prod.txt.
secrets/               Per-environment secret files, loaded on top of .env
                       (see "Environment & secrets" below). Only *.example files
                       are committed.
```

## Quickstart (Docker)

```bash
cp .env.example .env
docker compose up --build
```

This starts the app, MySQL and Redis. Run migrations in another terminal once it's up:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Visit `http://localhost:8000/` for the landing JSON, `http://localhost:8000/api/health/`
for the health check, `http://localhost:8000/admin/` for the Django admin.

## Quickstart (local, no Docker)

Requires a running MySQL and Redis locally.

```bash
python -m venv .venv
source .venv/bin/activate            # .venv\Scripts\activate on Windows
pip install -r requirements/dev.txt
cp .env.example .env                 # fill in DB_*/REDIS_* to match your local setup
python manage.py migrate
python manage.py runserver
```

Run the Celery worker/beat (separate terminals) if you need background tasks:

```bash
celery -A app worker --loglevel=info
celery -A app beat --loglevel=info
```

Or use the `Makefile` shortcuts: `make run`, `make migrate`, `make test`, `make lint`, `make format`.

## Environment & secrets

Config is read from environment variables, loaded in this order (later overrides earlier):

1. `.env` — base config for all environments (not committed)
2. `secrets/.env.<ENV_TYPE>.secrets` — environment-specific secrets, selected by
   the `ENV_TYPE` var (`local` / `preproduction` / `production`)

Copy `.env.example` to `.env` and the relevant `secrets/.env.<env>.secrets.example`
to `secrets/.env.<env>.secrets` to get started. Both real files are gitignored —
never commit them.

## API conventions

Every endpoint returns the same envelope, success or failure, via `core.response.api_response()`:

```json
{"success": true, "message": "...", "data": {...}}
{"success": false, "message": "...", "data": null, "errors": {...}}
```

This is wired up globally: `core.exceptions.custom_exception_handler` reshapes every
DRF exception (validation errors, 401/403/404, throttling) into the same envelope, so
you don't have to remember to call it from every view.

Auth: obtain tokens from `POST /api/v1/auth/login/` or `/register/`, then send
`Authorization: Bearer <access>` on subsequent requests. Refresh with
`POST /api/v1/auth/refresh/`.

## Adding a new app

1. `python manage.py startapp <name>` (or copy `accounts/` as a starting shape)
2. Add it to `LOCAL_APPS` in `app/settings.py`
3. Use `core.response.api_response()` in views instead of raw `Response()`
4. Wire its `urls.py` into `app/urls.py`
5. Add `tests/` mirroring `accounts/tests/`

## Testing

```bash
pytest                 # runs with coverage (see pyproject.toml [tool.pytest.ini_options])
```

Tests need a reachable MySQL (pytest-django creates/tears down a test database via
your `DATABASES` config) — either run against Docker's `db` service or a local MySQL.

## Lint & format

```bash
make lint     # ruff check + black --check
make format   # ruff --fix + black
```

Optionally install the pre-commit hooks so these run automatically on `git commit`:

```bash
pre-commit install
```

## Using this repo as a template for a new project

1. Rename the repo / clone into the new project directory
2. Update `PROJECT_NAME` in `.env` (and `.env.example`)
3. `rm -rf .git && git init` for a clean history
4. Replace `content/` assets and the `accounts` app's fields with whatever the new
   project actually needs — keep the `core` conventions (response envelope,
   exception handler, health check) as-is
5. Update `CSRF_TRUSTED_ORIGINS` / `ALLOWED_HOSTS` in `.env` once you know the
   real domains

## CI

`.github/workflows/ci.yml` runs `ruff`/`black --check` and the full `pytest` suite
(against real MySQL/Redis service containers) on every push and PR to `main`.

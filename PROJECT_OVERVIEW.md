# ShockPrices — Project Overview

A backend-first U.S. stock market data platform. Django + DRF serves a REST API
(and later WebSockets) built on market data sourced from **Massive**
(<https://massive.com>). The database schema is owned outside Django —
every model is `managed = False`.

This document describes **what exists today**, **what the system is meant to
become**, and the **decisions and open questions** that follow from the
current setup. For the feature/phase roadmap see
[stockprices_planning.md](stockprices_planning.md).

---

## 1. Scope

**In scope (backend):**

- Reference data for U.S. listed companies (ticker, name, exchange, sector, logo, status)
- Historical daily OHLCV, permanently stored
- Intraday bars (1m / 5m / 15m / 1h) for charting
- Current quotes / snapshots, served from Redis rather than PostgreSQL
- Fundamentals: income statement, balance sheet, cash flow, ratios
- Corporate actions: dividends, splits, ticker events, IPOs
- Filings and news
- Market movers, market status, exchange reference data
- Search by ticker and company name

**Out of scope for now:** frontend, user watchlists/alerts, options, crypto,
forex, futures. Auth exists in the boilerplate but no user-facing feature
depends on it yet.

---

## 2. Current State of the Codebase

Single commit so far: *"Rebuild as a clean Django REST boilerplate"*. No
market-data code exists yet — what is in place is the platform underneath it.

```
shockprices/
├── app/                      # Django project
│   ├── settings.py           # env-driven, splits config into app/config/*
│   ├── config/
│   │   ├── database.py       # PostgreSQL, CONN_MAX_AGE=60, health checks
│   │   ├── redis.py          # cache config per ENV_TYPE
│   │   ├── celery.py         # broker/backend, per-env Redis DB, empty beat_schedule
│   │   ├── cors.py           # ALLOWED_HOSTS, CORS, MIDDLEWARE
│   │   ├── logger.py
│   │   └── rest_framework.py
│   ├── urls.py               # "", /admin/, /api/, /api/v1/auth/
│   └── wsgi.py  asgi.py  celery.py
├── accounts/                 # custom User (email login), JWT endpoints
├── core/                     # shared: UnmanagedBaseModel, exceptions,
│                             # pagination, response helpers, apply_sql
├── requirements/             # base.txt / dev.txt / prod.txt
├── secrets/                  # .env.<env>.secrets, git-ignored
├── Makefile
└── .github/workflows/ci.yml
```

### Installed stack

| Concern | Choice | Version |
|---|---|---|
| Framework | Django | 6.0.3 |
| API | djangorestframework | 3.17.0 |
| Auth | djangorestframework-simplejwt | 5.5.1 (access 60m, refresh 7d, rotating) |
| Database | PostgreSQL via psycopg2-binary | 2.9.9 |
| Cache | django-redis / redis | 5.4.0 / 6.4.0 |
| Tasks | celery | 5.6.2 |
| HTTP client | requests | 2.32.5 |
| Lint/format | ruff, black, pre-commit | — |

### Environment loading

`app/settings.py` reads `.env` for `ENV_TYPE`, then overlays
`secrets/.env.<ENV_TYPE>.secrets`. Valid `ENV_TYPE` values are `local`,
`preproduction`, `production`. A missing secrets file is tolerated locally.
Celery uses Redis DB 0 (local), 4 (preprod), 3 (prod) and prefixes queue
names with `PROJECT_NAME`.

---

## 3. The `managed = False` Decision

`core/models.py` provides the base that every model in this project inherits:

```python
class UnmanagedBaseModel(models.Model):
    class Meta:
        abstract = True
        managed = False
```

`accounts.User` already sets `managed = False` directly.

**What this means:** Django does not create, alter, or drop tables. The
schema is authored as SQL and applied outside Django. Django only maps onto
it. The benefit for this project is real — market-data tables want hand-tuned
composite primary keys, partitioning by date, and index strategies that
Django's migration autodetector will not produce well.

**What this obligates us to do:**

1. **Own the DDL as versioned SQL.** Add a `sql/` directory with ordered,
   idempotent migration files, and a documented way to apply them. Without
   this, the schema exists only on the machine of whoever created it.
2. **Keep models and SQL in sync deliberately.** Run
   `python manage.py makemigrations --check --dry-run` in CI: for unmanaged
   models it should report nothing, so any output means someone changed a
   model without changing the SQL.
3. **Remember the test-database problem.** There are no tests right now, but
   when they come back: `managed = False` means the test database gets no
   tables. A `conftest.py` that runs `apply_sql` against it is the fix, and it
   is not optional.
4. **Note the leftover migration.** `accounts/migrations/0001_initial.py` was
   written while `User` was still managed. It should be reconciled with the
   SQL-owned `accounts_user` table rather than left to diverge.

---

## 4. Data Provider: Massive

API key comes from the Massive dashboard (<https://massive.com/dashboard>).
It is currently in `.env` as `massive_api_key` — **rename to
`MASSIVE_API_KEY`** to match every other variable in the file, and add it to
`.env.example` (commented, no value).

### REST

- Base URL: `https://api.massive.com`
- Auth, either form:
  - `?apiKey=YOUR_API_KEY`
  - `Authorization: Bearer YOUR_API_KEY` ← prefer this; keys do not belong in URLs, query strings get logged
- Response envelope is consistent: `{ "status", "results": [...], "count", "next_url", "request_id" }`
- Pagination is cursor-based via `next_url`

Endpoints relevant to our scope:

| Need | Endpoint |
|---|---|
| Ticker list | `GET /v3/reference/tickers` |
| Ticker detail | `GET /v3/reference/tickers/{ticker}` |
| Ticker types | `GET /v3/reference/tickers/types` |
| Related companies | `GET /v1/related-companies/{ticker}` |
| Custom bars (daily + intraday) | `GET /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}` |
| Whole-market daily bars | `GET /v2/aggs/grouped/locale/us/market/stocks/{date}` |
| Previous day bar | `GET /v2/aggs/ticker/{stocksTicker}/prev` |
| Daily open/close | `GET /v1/open-close/{stocksTicker}/{date}` |
| Single ticker snapshot | `GET /v2/snapshot/locale/us/markets/stocks/tickers/{stocksTicker}` |
| Full market snapshot | `GET /v2/snapshot/locale/us/markets/stocks/tickers` |
| Top movers | `GET /v2/snapshot/locale/us/markets/stocks/{direction}` |
| Last trade / quote | `GET /v2/last/trade/{stocksTicker}`, `GET /v2/last/nbbo/{stocksTicker}` |
| Income statements | `GET /stocks/financials/v1/income-statements` |
| Balance sheets | `GET /stocks/financials/v1/balance-sheets` |
| Cash flow statements | `GET /stocks/financials/v1/cash-flow-statements` |
| Ratios | `GET /stocks/financials/v1/ratios` |
| Dividends | `GET /v3/reference/dividends` |
| Splits | `GET /v3/reference/splits` |
| IPOs | `GET /vX/reference/ipos` |
| Ticker events | `GET /vX/reference/tickers/{id}/events` |
| Filings index | `GET /stocks/filings/vX/index` |
| News | `GET /v2/reference/news` |
| Market status | `GET /v1/marketstatus/now`, `GET /v1/marketstatus/upcoming` |
| Exchanges | `GET /v3/reference/exchanges` |
| Trade condition codes | `GET /v3/reference/conditions` |
| Indicators (SMA/EMA/RSI/MACD) | `GET /v1/indicators/{sma,ema,rsi,macd}/{stockTicker}` |

Massive also offers **Flat Files** (S3 bulk download) — the right tool for the
initial multi-year historical backfill. Paging the aggregates endpoint 10,000
tickers deep is the slow way to do a one-time load.

### WebSocket

- Real-time: `wss://socket.massive.com/stocks`
- 15-min delayed: `wss://delayed.massive.com/stocks`
- Handshake: connect → `{"action":"auth","params":"<KEY>"}` → `{"action":"subscribe","params":"AM.AAPL,AM.MSFT"}`
- Channels: `AM` (per-minute aggregates), `A` (per-second), `T` (trades), `Q` (NBBO quotes), `LULD`, `NOI`, `business/stocks/FMV`
- **One concurrent connection per asset class** by default. This is an
  architectural constraint, not a detail: a single dedicated worker process
  must own the connection, fan out into Redis, and be the only subscriber.
  Django request handlers must never open one.

### Constraints to settle before building on this

- **Plan gating.** The docs mark endpoint access and recency (real-time vs
  delayed) per plan tier. Which tier the account is on decides whether
  "current price" means real-time or 15-minute delayed — and that changes
  what the UI can honestly claim. Confirm from the dashboard.
- **Display licensing.** Redistributing real-time U.S. market data publicly
  is a licensing matter separate from API access. Needs resolving before
  launch, not at launch.
- **Official Python client** exists (`massive-com` on GitHub) and handles
  auth, retries, and response parsing. Worth evaluating against a thin
  hand-rolled client — but either way it stays behind our own provider
  interface (see §5).

---

## 5. Target Architecture

```
                         Massive
                            │
              ┌─────────────┴─────────────┐
           REST API                  WebSocket
              │                           │
              ▼                           ▼
     data_provider/ client          realtime worker
              │                           │
              ▼                           ▼
     Celery sync tasks ──────────►      Redis
              │                           │
              ▼                           │
         PostgreSQL ◄────────┐            │
              │              │            │
              └──────► Django REST API ◄──┘
                             │
                             ▼
                      Frontend (later)
```

**PostgreSQL** holds the permanent record: companies, daily prices, intraday
bars, financials, corporate actions, filings, sync job history.

**Redis** holds the volatile layer: current quotes, live prices, WebSocket
subscription state, response caches, and the Celery broker/result backend.
Real-time ticks are never written to PostgreSQL row-by-row.

**Celery** runs the scheduled work: ticker master sync, post-close daily price
sync, fundamentals sync, corporate-action sync, validation, cleanup.
`beat_schedule` in `app/config/celery.py` is currently empty and is where
these get registered.

### Planned apps

```
market/          Stock, DailyPrice, IntradayBar + serializers/views/urls/services
data_provider/   Massive client, response→model mapping, rate limiting, retries
sync/            DataSyncJob model, Celery tasks, orchestration
fundamentals/    FinancialStatement, FinancialRatio + sync
realtime/        WebSocket consumer, Redis publish/subscribe
```

`data_provider/` is the only package that knows Massive exists. Everything
else talks to an interface. That boundary is what makes a provider swap a
contained change instead of a rewrite — worth holding even while there is
exactly one provider.

### First models

`Stock`, `DailyPrice`, `IntradayBar`, `DataSyncJob`. All inherit
`UnmanagedBaseModel`, all backed by hand-written SQL. Resist adding the other
fifteen until data is flowing end to end.

`DataSyncJob` records job type, provider, data date, start/end time, status,
records processed, and error. It is what makes stale data loud instead of
silent, so it ships with the first sync task, not after.

### Initial endpoints

```http
GET /api/stocks/
GET /api/stocks/{ticker}/
GET /api/stocks/{ticker}/prices/
GET /api/stocks/{ticker}/intraday/
GET /api/stocks/{ticker}/financials/
GET /api/stocks/{ticker}/corporate-actions/
GET /api/stocks/{ticker}/dividends/
GET /api/search/?q=apple
GET /api/market/movers/
```

Existing routes: `GET /api/health/` and the JWT endpoints under
`/api/v1/auth/`.

---

## 6. Build Order

The definition of done for step 2 is a correct response from
`GET /api/stocks/AAPL/` backed by our own database. Everything else follows it.

1. **Foundation** — SQL migration workflow, test-DB strategy for unmanaged
   models, `MASSIVE_API_KEY` wiring, `data_provider/` client with retries and
   rate limiting, verified Postgres + Redis + Celery.
2. **Stock master** — `Stock` model and table, import U.S. tickers from
   `/v3/reference/tickers`, expose `GET /api/stocks/{ticker}/`.
3. **Historical daily** — `DailyPrice`, backfill via Flat Files, nightly
   post-close sync via grouped daily bars, `DataSyncJob` tracking.
4. **Intraday** — `IntradayBar` for 1m/5m/15m/1h, chart endpoint.
5. **Real-time** — WebSocket worker → Redis → Django Channels → client.
   Requires adding `channels` + an ASGI server (see §7).
6. **Fundamentals** — statements, ratios, dividends, splits, corporate actions.
7. **Market features** — search, movers, market overview, indices.
8. **User features** — watchlists, favorites, alerts, preferences.

---

## 7. Known Gaps

Small now, expensive later.

| # | Issue | Fix |
|---|---|---|
| 1 | ~~`TIME_ZONE` / Celery timezone in Asia/Kolkata.~~ | **Done.** Django and Celery both run in UTC; the sync code derives U.S. session dates in America/New_York. |
| 2 | `.env.example` documents MySQL on port 3306; `app/config/database.py` uses PostgreSQL on 5432. | Update `.env.example`. |
| 3 | `PROJECT_NAME` defaults to `shareprice`; `DB_NAME` to `shareprice_db`. Project is ShockPrices. | Rename, or accept it deliberately — it leaks into Celery queue names. |
| 4 | `massive_api_key` is lowercase and absent from `.env.example`. | `MASSIVE_API_KEY`, documented in `.env.example`. |
| 5 | No `channels` / `daphne` / `uvicorn` in requirements, though `app/asgi.py` exists. | Add at Phase 5, not before. |
| 6 | ~~No SQL schema directory.~~ | **Done.** `sql/` + `python manage.py apply_sql`, with checksum enforcement. See [sql/README.md](sql/README.md). |
| 7 | Unmanaged models leave a test database empty. Tests are out of scope for now, so this is deferred, not solved. | A `conftest.py` running `apply_sql`, reinstated alongside the tests. |
| 8 | `accounts/migrations/0001_initial.py` predates `User.Meta.managed = False`, so it still emits real DDL — confirmed via `sqlmigrate`. `accounts_user` is Django-owned while every other table is SQL-owned, and `makemigrations --check` is dirty. | Reconcile with the SQL-owned table. See follow-up 1 in [SCHEMA_PLAN.md](SCHEMA_PLAN.md). |
| 9 | ~~`beat_schedule` is empty.~~ | **Done.** Daily reference-data and post-close daily-price syncs; see README. |
| 10 | Market-data plan tier and display licensing unconfirmed. | Check the dashboard; confirm real-time vs 15-minute delayed. |

---

## 8. Summary

> ShockPrices is a Django/DRF backend that aggregates U.S. equity reference,
> historical, intraday, fundamental, and corporate-action data from Massive
> into a PostgreSQL store it owns, serves it as a REST API, and streams live
> quotes through Redis — with the database schema managed as SQL rather than
> by Django migrations.

Two rules worth keeping: the pipeline is proven before the frontend starts,
and `data_provider/` is the only code that knows the provider's name.

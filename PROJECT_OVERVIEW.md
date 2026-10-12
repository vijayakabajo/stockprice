# ShockPrices — Project Overview

A backend for a U.S. equity **profile site**: one indexable, answer-first page
per listed company, plus directory, sector and exchange hub pages. Django +
DRF over market data from **Massive** (<https://massive.com>), with the
database schema owned as SQL rather than by Django migrations.

This document covers **what we are building**, **where the project stands**,
and **how we work**. Related docs:

- [stockprices_planning.md](stockprices_planning.md) — phases, database additions, API endpoints
- [SCHEMA_PLAN.md](SCHEMA_PLAN.md) — how a table gets built
- [MASSIVE_APIS.md](MASSIVE_APIS.md) — the provider's endpoints and what we use them for
- [README.md](README.md) — setup and day-to-day commands

---

## 1. What We Are Building

A static HTML prototype lives in `Stockprice_pages_prototype/` (outside this
repo). It is a design prototype, not production code, but it fixes the shape
of the product. Working brand: **Equity Profiles** (placeholder), built by
6sMarketers.

The prototype is rendered entirely from a dump of our own `market_stock`
table — 13 sample tickers. Every number it shows that is not a placeholder
already exists in our database. Prices, charts, financials and news are drawn
as labelled placeholders.

### Pages

| Prototype file | Page | Shows |
|---|---|---|
| `index.html` | Home | Search; headline stats (company count, combined market cap, sectors covered, data as-of date); browse by sector, exchange and size; largest companies |
| `stocks.html` | Stock directory | The whole U.S. universe, filterable by exchange, type, sector and size, sortable by market cap, name, ticker, employees |
| `sectors.html` | Sector index | Every sector with company count and total market cap |
| `sector.html` | Sector hub | Sector stats (companies, combined cap, total employees, average cap), companies ranked by market cap |
| `exchanges.html` | Exchange index | Every exchange with listing count and total market cap |
| `exchange.html` | Exchange hub | Same as the sector hub, grouped by exchange |
| `stock.html` | Stock profile | Full company profile — see below |
| `stock-spac.html` | Profile, SPAC variant | "Pre-merger shell" notice, no peers, kept out of search indexes |
| `stock-adr.html` | Profile, ADR variant | "U.S. listed ADR" notice |
| `Stock Profile Page.html` | Profile, long-form layout | Same data plus byline, table of contents, key takeaways, sector primer, glossary, FAQ, sources, structured data |

### What a stock profile shows

| Block | Content | Status |
|---|---|---|
| Header | logo/monogram, name, ticker, exchange, sector, type tag (Common / ADR / SPAC), Active | have the data |
| Snapshot and key metrics | market cap (dated), shares outstanding, employees, cap per employee, size bucket, HQ, round lot | have the data |
| About | company description | have the data |
| Market cap in context, peers, related companies | comparisons within sector or exchange | have the data |
| Key facts, IDs, filings | exchange, security type, SIC, CIK, FIGIs, address, website, SEC EDGAR link | have the data |
| FAQ, takeaways | generated from the fields above | have the data |
| Quote and price chart | price, change, day range, 52-week range | placeholder |
| Financials | revenue, net income, EPS, P/E, dividend yield | placeholder |
| Latest news | headlines | placeholder |

### What the prototype tells us

- **Reference data is the product, prices are a feature.** The MVP is a
  correct, dated, sourced page for every U.S. listed company — not a trading
  terminal. The prototype only ever promises a *delayed* price.
- **It is programmatic SEO.** Every sector and exchange is its own indexable
  hub page. Sitemaps, stable URLs, last-modified dates and "keep out of the
  index" rules are part of the backend's job.
- **Every figure is dated.** "Indicative, as of 22 Sep 2026" appears on
  nearly every block.
- **Classification belongs to the backend.** The prototype works out display
  names, sectors, type tags and size buckets in the browser. Those are
  filter and grouping keys, so they get computed once, in the database.

---

## 2. Scope

**In scope:**

- Company reference data — the backbone of every page
- Directory, sector and exchange listings for the full U.S. universe
- Aggregates, rankings, peers and search
- SEO support: sitemap data, indexability rules, as-of dates
- Editorial content: sector primers, glossary terms
- Delayed quotes and daily price history
- Fundamentals summary and news
- Later, only if the product asks: market movers, intraday charts, live prices

**Out of scope:** the frontend itself, user accounts and watchlists (nothing
in the prototype needs them), options, crypto, forex, futures.

---

## 3. Where the Project Stands

The data pipeline for reference data and daily prices is built and
scheduled. What is missing is the layer that serves it the way the pages
need it.

```
stockprices/
├── app/                      # Django project; settings split into app/config/*
├── accounts/                 # custom User (email login), JWT
├── core/                     # UnmanagedBaseModel, response envelope,
│                             # exception handler, pagination, health, apply_sql
├── data_provider/            # Massive client, retries + backoff
├── market/                   # Stock, DailyPrice, IntradayBar
├── sync/                     # DataSyncJob, sync services, Celery tasks, commands
├── sql/                      # 0000–0005: the schema of record
├── requirements/  secrets/  Makefile  .github/workflows/ci.yml
```

| Area | State |
|---|---|
| Ticker master | Synced daily into `market_stock`. Delisted rows kept as inactive. |
| Company profiles | Description, address, SIC, market cap, shares, employees filled daily, stalest first. |
| Daily prices | Whole market loaded nightly per session; failed recent sessions retried. |
| Job tracking | Every run logged as a `DataSyncJob`; a Redis lock prevents overlapping runs. |
| Schedule | Reference data 01:15 UTC daily; daily prices 01:45 UTC Tue–Sat. |
| Serving layer | A basic stock list and detail. No filtering, classification, aggregates or as-of dates yet. |
| Schema workflow | `sql/` + `apply_sql`, checksums enforced. |

### Still to build for the prototype

1. Classification: display name, security type, size bucket, sector, exchange name.
2. Sector and exchange reference data, with URL slugs.
3. Directory, hub, profile, search and sitemap data for the pages.
4. As-of dates on everything served.
5. A cache that a successful sync invalidates.
6. Quote, chart, financials, news — the placeholders.

### Stack

| Concern | Choice |
|---|---|
| Framework | Django 6.0.3 + Django REST Framework 3.17.0 |
| Database | PostgreSQL |
| Cache / broker | Redis |
| Background jobs | Celery 5.6.2 (worker + beat) |
| Auth | simplejwt (not used by the site yet) |
| Lint / format | ruff, black, pre-commit |

---

## 4. How We Work

### The schema is SQL, not Django migrations

Every model is `managed = False`, inheriting `core.models.UnmanagedBaseModel`.
Django maps onto tables it does not own. A change goes, in one commit:

```
write sql/000N_*.sql  →  apply_sql  →  write the model  →  makemigrations (state only)
```

SQL first, model second. Applied `.sql` files are immutable. Always write
`class Meta(UnmanagedBaseModel.Meta):` — a bare `class Meta:` silently turns
`managed` back on. Full workflow in [SCHEMA_PLAN.md](SCHEMA_PLAN.md).

What this obligates us to:

- `makemigrations --check --dry-run` must stay empty — it is the drift alarm.
- When tests return, a `conftest.py` must apply `sql/` to the test database,
  because Django will create no tables for it.

### One door to the provider

`data_provider/` is the only code that knows Massive exists. Sync services
call it; nothing else does. Swapping or adding a provider stays a contained
change.

### Data arrives by scheduled sync, never on request

Pages are served from our own database and Redis. A page view never calls
the provider. Every sync:

- runs as a Celery task, also runnable by hand as a management command;
- is logged as a `DataSyncJob` (type, data date, start/end, status, rows,
  error), so stale data is loud instead of silent;
- holds a Redis lock so two runs of one job never overlap;
- upserts — reruns are safe.

### Time

Django and Celery run in UTC. U.S. trading sessions are derived explicitly in
America/New_York. Timestamps are stored as `TIMESTAMPTZ`.

### Every figure is dated

Whatever we serve carries the date it is true as of: the last successful
reference sync for lists and hubs, a company's own last refresh for its
profile, the snapshot time for a quote. A number without a date does not
ship.

### Classification happens once, in the database

Display name, security type, size bucket, sector and exchange name are
computed in the database (generated columns or written by the sync), not
re-derived by each consumer. The rules:

| Field | Rule |
|---|---|
| Display name | Company name with share-class and legal suffixes removed ("Class A Ordinary Shares", "Inc", "Corp", "Holdings"…); falls back to the raw name |
| Security type | SPAC if SIC 6770 or "blank check" in its description; ADR if the asset type is an ADR; Common if common stock; otherwise the raw type |
| Size bucket | Mega ≥ $200B, Large ≥ $10B, Mid ≥ $2B, Small ≥ $300M, Micro ≥ $50M, Nano below |
| Sector | From the SIC code; "Blank Checks" for SPACs, "Not classified" when missing |
| Exchange name | From the exchange code (XNAS → Nasdaq, XNYS → NYSE, …) |
| Indexable | Active, not a SPAC, has a description |

### The backend owns facts, the frontend owns copy

The backend serves facts and classifications. Sentences built from them —
FAQs, takeaways, structured data — are templated by the frontend. Editorial
content that cannot be derived (sector primers, glossary) is stored in the
database and edited through the Django admin.

### Real-time data stays out of PostgreSQL

Quotes live in Redis. PostgreSQL holds the permanent record only.

### Caching follows the data, not the clock

Each successful reference sync bumps a data version in Redis. Cached
responses are keyed by it, so a sync refreshes every page at once and
nothing else does.

### Keep data, don't delete it

Delisted companies stay, marked inactive. Financial statements are appended
per reporting period, never overwritten. History is data.

### Small steps, pipeline first

A table or feature is added when a page needs it, not before. Each phase ends
with something the frontend can render.

---

## 5. Architecture

```
                 Massive
                    │
                    ▼
          data_provider/ client
                    │
                    ▼
            Celery sync tasks ──────────► Redis
                    │                quotes, response cache,
                    ▼                data version, locks
               PostgreSQL                  ▲
                    │                      │
                    └────► Django REST ────┘
                                │
                                ▼
           server-rendered frontend → CDN → search engines
```

- **PostgreSQL** — companies, classification, sectors, exchanges, prices,
  fundamentals, news, editorial content, sync history.
- **Redis** — delayed quotes, response cache, sync locks, Celery broker.
- **Celery** — every scheduled sync.
- **Frontend** — must be server-rendered or statically generated, since
  search engines and AI answer engines are the primary audience. Lives
  outside this repo.

### Apps

```
market/          Stock, Sector, Exchange, DailyPrice, IntradayBar
data_provider/   provider client
sync/            DataSyncJob, tasks, orchestration
content/         sector primers, glossary              (new)
fundamentals/    statements, dividends, summaries     (later)
news/            articles                             (later)
```

---

## 6. Known Gaps

| # | Issue | Fix |
|---|---|---|
| 1 | `PROJECT_NAME` / `DB_NAME` code defaults still say `shareprice`; `.env.example` says `shockprices`. | Align the defaults — the name leaks into Celery queue names. |
| 2 | Unmanaged models leave a test database empty. | `conftest.py` applying `sql/`, when tests return. |
| 3 | `accounts/migrations/0001_initial.py` predates `managed = False`. | Reconcile with an SQL-owned `accounts_user`. See [SCHEMA_PLAN.md](SCHEMA_PLAN.md). |
| 4 | CI runs lint only. | Add the drift check and `apply_sql` against a service Postgres. |
| 5 | Provider plan tier and public display licensing unconfirmed. | Confirm before any price is shown publicly. |
| 6 | Provider logo URLs need our private key. | Serve them through our backend, or keep monograms. |

---

## 7. Open Questions

Decisions for the product owner; the plan assumes the default.

| Question | Default assumed |
|---|---|
| **What is a "sector"?** The prototype uses the 4-digit SIC description (~400 values, many with one company). Thin hub pages hurt SEO. | Keep them, but hubs with fewer than 3 active companies stay out of the index. Revisit a sector → industry grouping once the full universe is loaded. |
| **Which securities get pages?** | Active common stock and ADRs indexed; SPACs get pages but stay out of the index; ETFs, warrants, rights, units and preferreds excluded. |
| **Delisted companies?** | Keep the page, show "Inactive", out of the index. |
| **Frontend stack?** | Server-rendered / statically generated, outside this repo. |
| **Who writes FAQ and takeaway copy?** | The frontend, from backend fields. |
| **Delayed or real-time price?** | 15-minute delayed. |

---

## 8. Summary

> ShockPrices turns U.S. equity reference, price and fundamentals data into
> a dated, classified, SEO-ready dataset that powers an answer-first company
> profile site — with data arriving by tracked scheduled syncs and the
> schema managed as SQL.

Rules worth keeping: every figure ships with its date; classification
happens once, in the database; only `data_provider/` knows the provider's
name.

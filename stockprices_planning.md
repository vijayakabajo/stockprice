# StockPrices --- Project Plan

Roadmap for the backend behind the **Equity Profiles** site (placeholder
brand). What we are building, how we work and the open questions live in
[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md); the table-building workflow in
[SCHEMA_PLAN.md](SCHEMA_PLAN.md); provider endpoints in
[MASSIVE_APIS.md](MASSIVE_APIS.md).

------------------------------------------------------------------------

## 1. Goal

> **An answer-first profile page for every U.S. listed company — correct,
> dated, sourced and indexable — plus directory, sector and exchange hubs,
> served by a backend that owns its data.**

The frontend prototype (`Stockprice_pages_prototype/`) sets the target. It
renders entirely from our `market_stock` table today; prices, charts,
financials and news are placeholders. The plan fills those in, in order of
what the pages need.

### What changed from the previous plan

| Before | Now |
|---|---|
| Trading-style stock page: live price first, company info second | Profile page: company facts first, delayed quote as one block |
| Real-time WebSocket was Phase 5 | Real-time is last; a delayed snapshot covers the prototype |
| Market movers, indices on the home page | Not in the prototype; deferred |
| "Do not build the frontend first" | A frontend prototype exists; the API is shaped by its pages |
| Search, sectors, exchanges were Phase 7 | Directory, hubs and search are the next phase — they are the site |
| No SEO concerns | Sitemaps, slugs, `indexable`, `lastmod`, as-of dates are core |

------------------------------------------------------------------------

## 2. Pages and What They Need

| Page | Needs from the backend |
|---|---|
| Home | Search, headline stats, counts by sector/exchange/size, largest companies, as-of date |
| Stock directory | Server-paginated list; filter by exchange, type, sector, size; sort by market cap, name, ticker, employees |
| Sector index / hub | Sectors with counts and total cap; hub stats (companies, combined cap, total employees, average cap), ranked companies, primer text |
| Exchange index / hub | Same as sectors, grouped by exchange |
| Stock profile | Reference fields, derived classification, key metrics, market cap context, peers, related companies, IDs, EDGAR link, as-of dates |
| Stock profile — SPAC / ADR variants | `security_type` flag drives the notice; SPACs hide peers and are `noindex` |
| Profile placeholders | Quote, price chart, financials, latest news |

------------------------------------------------------------------------

## 3. Core Data

### A. Company reference data — *have it*

Ticker, name, ticker root, exchange (MIC), asset type, currency, CIK,
composite and share-class FIGI, SIC code and description, description,
website, address, phone, logo/icon URL, market cap, share-class and weighted
shares outstanding, employees, round lot, list date, active/delisted.

Source: `/v3/reference/tickers` and `/v3/reference/tickers/{ticker}`, synced
daily into `market_stock`.

### B. Classification — *to build*

Display name, security type (common / ADR / SPAC / other), size bucket,
sector (with slug), exchange display name (with slug). Computed once in the
database; see PROJECT_OVERVIEW §4 for the rules.

### C. Editorial content — *to build*

Sector primers (2–3 plain sentences per sector), glossary terms, and later
per-page bylines/review dates. Stored in the database, edited through the
Django admin.

### D. Daily prices — *have the pipeline*

Date, OHLC, volume, VWAP, transactions — in `market_daily_price`, synced
nightly. Feeds the price chart, the 52-week range and the nightly market cap
refresh.

### E. Delayed quote — *to build*

Last price, change, change %, day open/high/low, previous close, volume,
timestamp. Polled from the snapshot endpoint into Redis. Never written to
PostgreSQL row by row.

### F. Fundamentals summary — *to build*

What the financials block shows: revenue TTM, net income TTM, EPS, P/E,
dividend yield — each with its period and as-of date. Backed by stored
statements (appended per reporting period, never overwritten) and dividends.

### G. News and filings — *to build*

Headline, publisher, URL, published time, tickers. Filings start as the
EDGAR link from CIK and grow into a filings index later.

### H. Intraday and real-time — *later*

`market_intraday_bar` exists but stays empty until a page needs intraday
charts. WebSocket streaming only if the product asks for live ticking prices.

------------------------------------------------------------------------

## 4. Architecture

``` text
                          Massive
                             │
                          REST API
                             │
                             ▼
                   data_provider/ client
                             │
                             ▼
                    Celery sync tasks ─────────► Redis
                             │             quotes, response cache,
                             ▼             data version, locks
                        PostgreSQL               ▲
                             │                   │
                             └──► Django REST API┘
                                        │
                                        ▼
                        SSR / SSG frontend → CDN → search engines
```

-   **PostgreSQL** --- companies, classification, sectors, exchanges,
    prices, fundamentals, news, editorial content, sync history.
-   **Redis** --- delayed quotes, versioned response cache, sync locks,
    Celery broker/results.
-   **Celery** --- reference sync, daily price sync, market cap refresh,
    quote polling, fundamentals and news syncs, data-version bump.

------------------------------------------------------------------------

## 5. Application Structure

``` text
stockprices/
├── app/              settings, urls, celery bootstrap
├── core/             base model, response envelope, pagination, apply_sql
├── data_provider/    Massive client — the only code that knows Massive
├── market/           Stock, Sector, Exchange, DailyPrice, IntradayBar
│                     serializers, views, filters, aggregate queries
├── sync/             DataSyncJob, sync services, tasks, commands
├── content/          glossary and other editorial content          (later)
├── fundamentals/     statements, dividends, summary metrics          (later)
└── news/             articles                                       (later)
```

------------------------------------------------------------------------

## 6. Database Additions

One `sql/` file plus one model each, per the SCHEMA_PLAN workflow.

| # | Change | Phase |
|---|---|---|
| 0006 | `market_exchange` — MIC (PK), slug, display name, acronym, operating MIC | 2 |
| 0007 | `market_sector` — SIC code (PK), slug, display name, raw SIC description | 2 |
| 0008 | `market_stock` + `display_name` column, generated `security_type` and `size_bucket`, indexes on `sic_code`, `security_type`, `size_bucket`, `(active, market_cap DESC)` | 2 |
| 00NN | `content_glossary_term` (sector primers live on `market_sector`) | later |
| 0010 | `market_stock.market_cap_as_of` — date the market cap refers to | 3 |
| 00NN | `fundamentals_financial_statement`, `market_dividend`, `market_stock_split` | 4 |
| 00NN | `news_article` + `news_article_ticker` | 5 |

------------------------------------------------------------------------

## 7. API

All endpoints are public, read-only, under `/api/v1/`, and return the
existing `api_response()` envelope. There is no user auth.

### Conventions

-   **Every response carries `as_of`.** Lists and hubs report the last
    successful reference-data sync; a profile reports its own
    `details_synced_at`; quotes report the snapshot timestamp.
-   **Slugs, not labels, in URLs and filters:** `sector=blank-checks`,
    `exchange=nasdaq`, `type=spac`, `size=mid`.
-   **Server-side pagination,** page-number with `count`, so the
    directory can show "Showing 50 of 6,412".
-   **`indexable` is a field,** decided by the backend: false for
    inactive listings, SPACs, and hubs below the minimum company count.
-   **Caching:** `Cache-Control` and `ETag` on every response, Redis-backed
    per data version.

### Endpoints

| Endpoint | Serves | Notes |
|---|---|---|
| `GET /api/v1/overview/` | Home | headline stats, counts by sector/exchange/size, largest companies |
| `GET /api/v1/stocks/` | Directory, hub tables | filters `exchange`, `type`, `sector`, `size`, `q`, `active`; ordering `-market_cap`, `name`, `ticker`, `-total_employees`; paginated |
| `GET /api/v1/stocks/{ticker}/` | Profile | reference fields, derived fields, flags, `edgar_url`, `as_of` |
| `GET /api/v1/stocks/{ticker}/peers/` | Profile | `context` (top 5 + self, with rank), `peers` (same sector, fallback exchange), `related` (3) |
| `GET /api/v1/sectors/` | Sector index | slug, name, company count, total cap |
| `GET /api/v1/sectors/{slug}/` | Sector hub | stats, primer, `indexable`; companies via `/stocks/?sector=` |
| `GET /api/v1/exchanges/` | Exchange index | slug, name, listing count, total cap |
| `GET /api/v1/exchanges/{slug}/` | Exchange hub | stats; companies via `/stocks/?exchange=` |
| `GET /api/v1/search/?q=` | Search box | ticker prefix first, then name trigram; small typeahead payload |
| `GET /api/v1/sitemap/` | Sitemap build | every indexable stock, sector and exchange with `lastmod` |

Later:

| Endpoint | Serves | Notes |
|---|---|---|
| `GET /api/v1/stocks/{ticker}/quote/` | Quote block | delayed snapshot from Redis, day range, 52-week range, market status |
| `GET /api/v1/stocks/{ticker}/prices/?range=1y` | Price chart | from `market_daily_price` |
| `GET /api/v1/stocks/{ticker}/financials/` | Financials block | revenue TTM, net income TTM, EPS, P/E, dividend yield, each dated |
| `GET /api/v1/stocks/{ticker}/news/` | Latest news | |
| `GET /api/v1/glossary/` | Profile glossary | editorial terms; the frontend holds them until then |

Also: `GET /api/health/`. The boilerplate JWT endpoints and `accounts` app
were removed in Phase 2; the site has no user accounts.

------------------------------------------------------------------------

## 8. Development Phases

### Phase 1 --- Data Foundation ✅

Django, PostgreSQL, Redis, Celery, Massive client, `sql/` + `apply_sql`,
`DataSyncJob` tracking, UTC scheduling.

### Phase 1b --- Reference and Price Pipeline ✅

``` text
/v3/reference/tickers ──► market_stock          (sync_stocks)
/v3/reference/tickers/{t} ──► profile fields    (sync_stock_details)
grouped daily bars ──► market_daily_price       (sync_daily_prices)
```

Scheduled daily.

### Phase 2 --- Profile Site API ✅

The prototype rendered from the API, for the full U.S. universe.

1.  Move market routes under `/api/v1/`.
2.  `market_exchange` synced from `/v3/reference/exchanges`, with display
    names and slugs.
3.  `market_sector` populated from the distinct SIC codes in
    `market_stock`, with slugs; editable display names.
4.  `display_name`, `security_type`, `size_bucket` on `market_stock`;
    backfill `display_name` for existing rows.
5.  Profile serializer: all reference fields, derived fields, `as_of`,
    `indexable`, `edgar_url`.
6.  Directory endpoint with filters, ordering and page-number pagination.
7.  Aggregates: overview, sector and exchange index and hub stats.
8.  Peers / market cap context / related companies.
9.  Search: ticker prefix, then `pg_trgm` name match.
10. Sitemap endpoint with `lastmod`.
11. Sector primers, admin-editable on `market_sector`. (Glossary deferred:
    the frontend holds its terms for now.)
12. Response cache keyed by a data version that each successful reference
    sync bumps; `Cache-Control` and `ETag` headers.
13. Settle universe rules: which asset types get pages, what is
    `noindex`.

Done when every prototype page --- home, directory, sectors, sector hub,
exchanges, exchange hub, and all three profile variants --- can be built
from API responses alone, with no client-side classification logic.

### Phase 3 --- Quote and Chart

``` text
Snapshot endpoint ──► Celery poll ──► Redis ──► /quote/
market_daily_price ──► /prices/?range= ──► chart
market_daily_price ──► 52-week high / low
close × shares outstanding ──► market_cap, market_cap_as_of
/v1/marketstatus/now ──► "market open / closed" label
```

-   Confirm plan tier and display licensing first.
-   Daily price backfill (Flat Files) so charts and 52-week ranges have
    a year of history.
-   Splits sync, so the stored series stays split-adjusted.
-   Market cap recomputed nightly from the close, so it moves with price
    and its as-of date is honest.

Done when the quote block and price chart on the profile show real,
dated, delayed data.

### Phase 4 --- Financials

-   Income statements, balance sheets, cash flow from
    `/stocks/financials/v1/...`, stored per reporting period.
-   Dividends from `/v3/reference/dividends`.
-   Summary endpoint: revenue TTM, net income TTM, EPS, P/E (computed
    on read from the latest close), dividend yield --- each with period
    and as-of.

Done when the financials block shows figures for every company that
reports them, and an honest "not reported" for SPACs and gaps.

### Phase 5 --- News and Related

-   News sync from `/v2/reference/news`, linked to tickers.
-   Related companies from `/v1/related-companies/{t}` to improve on the
    sector/exchange heuristic.
-   Logos: server-side proxy and cache, if the brand wants them over
    monograms.
-   Filings index, if the page grows a filings list.

### Phase 6 --- Market Features *(only if the product asks)*

Top gainers / losers / most active, market overview, indices.

### Phase 7 --- Intraday and Real-Time *(only if the product asks)*

`market_intraday_bar` sync for 1m/5m/15m/1h; WebSocket worker →
Redis → Django Channels for live ticking prices. Requires `channels` and
an ASGI server.

### Phase 8 --- User Features *(not in the prototype)*

Watchlists, favourites, alerts, preferences. Would need user accounts
again; the unused boilerplate `accounts` app was removed in Phase 2.

------------------------------------------------------------------------

## 9. Cross-Cutting Work

Not a phase --- done alongside Phase 2 and kept up.

-   **CI:** `makemigrations --check --dry-run` and `apply_sql` against a
    service Postgres, alongside lint.
-   **Tests:** ✅ pytest, with the test database built from `sql/`. Keep
    one test per endpoint and per naming rule.
-   **Staleness alarms:** a stale reference or price sync (no successful
    `DataSyncJob` within its window) should be visible --- in the
    health check and in `as_of` on every response.
-   **Config clean-up:** `PROJECT_NAME` / `DB_NAME` defaults.

------------------------------------------------------------------------

## 10. MVP Definition

``` text
Search "Agilent"
   ↓
/stocks/A
   ├── Display name, ticker, exchange, sector, type tag
   ├── Market cap (dated), employees, size, HQ
   ├── About, key metrics, key facts, IDs, EDGAR link
   ├── Market cap in context, peers, related companies
   └── Quote and financials shown as "coming soon"
```

plus the directory, sector and exchange hubs, a sitemap, and correct
`noindex` on SPACs and inactive listings --- for every active U.S.
listed company, refreshed daily.

The MVP is **Phase 2**. Phases 3 and 4 replace the two placeholders that
matter most; everything after is optional.

------------------------------------------------------------------------

## 11. Open Questions

Tracked with their working defaults in PROJECT_OVERVIEW §7:

-   SIC industry vs grouped sector for hub pages
-   Which asset types get pages, and which are `noindex`
-   Frontend stack (assumed SSR/SSG, outside this repo)
-   Delayed vs real-time quote, and display licensing
-   Logos vs monograms

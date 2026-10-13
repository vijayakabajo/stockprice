# StockPrices API

The read-only API behind the Equity Profiles site. One endpoint per page, or
per block of a page, with every company already classified and dated.

- **Base URL (local):** `http://localhost:8000/api/v1`
- **Auth:** none. Every endpoint is public.
- **Methods:** `GET` only (plus `HEAD` / `OPTIONS`). Anything else is `405`.
- **Format:** JSON.
- **Postman:** import [`postman/StockPrices.postman_collection.json`](postman/StockPrices.postman_collection.json)
  and [`postman/StockPrices.local.postman_environment.json`](postman/StockPrices.local.postman_environment.json),
  then pick the **StockPrices — local** environment.

Example values below are real responses from the dev database, with long
lists shortened to one or two items.

---

## Contents

| Endpoint | Page it serves |
|---|---|
| [`GET /overview/`](#get-overview) | Home |
| [`GET /stocks/`](#get-stocks) | Stock directory; company tables on hubs |
| [`GET /stocks/{ticker}/`](#get-stocksticker) | Stock profile |
| [`GET /stocks/{ticker}/peers/`](#get-stockstickerpeers) | Profile: market cap context, peers, related |
| [`GET /sectors/`](#get-sectors) | Sector index |
| [`GET /sectors/{slug}/`](#get-sectorsslug) | Sector hub |
| [`GET /exchanges/`](#get-exchanges) | Exchange index |
| [`GET /exchanges/{slug}/`](#get-exchangesslug) | Exchange hub |
| [`GET /search/?q=`](#get-search) | Search box |
| [`GET /sitemap/`](#get-sitemap) | sitemap.xml build |

Outside `/api/v1/`: `GET /api/health/` checks the database and Redis.

---

## Conventions

### Response envelope

Every response, success or error, has the same shape:

```json
{ "success": true,  "message": "", "data": { ... } }
{ "success": false, "message": "No stock page for 'SPY'.", "data": null, "errors": null }
```

### Which stocks exist

Only **active common stock, ADRs and SPACs** have pages. ETFs, warrants,
units, preferreds, rights and funds return `404`. Delisted companies keep
their page, with `"active": false`.

### `indexable`

Every stock, sector and exchange carries `indexable`. When it is `false`, the
frontend should tell search engines not to index the page (`noindex`).

| Page | `indexable` is `false` when |
|---|---|
| Stock | it is a SPAC, it is delisted, or it has no description yet |
| Sector / exchange hub | it has fewer than 3 companies, or it is "Not classified" |

### `as_of`

When the data was last refreshed, as an ISO 8601 UTC timestamp. Lists and
hubs report the last successful ticker or profile sync. A stock profile
reports when that company's own profile was last fetched. `null` if never.

### Values

- **Missing is `null`**, never `0` or `""`. Show "n/a" or hide the field.
- **Market cap, shares and employees are JSON numbers**, in plain units
  (dollars, people). Format them in the frontend: `4912984755200.0` → "$4.91T".
- **Labels come as `{slug, name}`**: `slug` for URLs and filters, `name` for
  display. Never a raw provider code.

### Enumerations

| Field | Values |
|---|---|
| `security_type` | `common`, `adr`, `spac` |
| `size_bucket` | `mega` (≥ $200B), `large` (≥ $10B), `mid` (≥ $2B), `small` (≥ $300M), `micro` (≥ $50M), `nano`, `unknown` (no market cap) |
| exchange slugs | `nasdaq`, `nyse`, `nyse-american`, `nyse-arca`, `cboe-bzx` (from `/exchanges/`) |
| sector slugs | from `/sectors/`, e.g. `blank-checks`, `semiconductors-related-devices`; plus `not-classified` |

### The stock row

Lists (directory, hub `largest`, peers, overview `largest`) all use the same
row:

| Field | Type | Notes |
|---|---|---|
| `ticker` | string | `AAPL`, `BRK.A` |
| `display_name` | string | Cleaned name for display: "Apple" |
| `name` | string | Legal name from the provider: "Apple Inc." |
| `security_type` | string | see enumerations |
| `exchange` | `{slug, name}` \| null | |
| `sector` | `{slug, name}` | `not-classified` when the industry code is unknown |
| `hq` | string \| null | "Cupertino, CA" |
| `total_employees` | number \| null | |
| `market_cap` | number \| null | dollars; indicative, dated by `as_of` |
| `size_bucket` | string | see enumerations |
| `indexable` | boolean | |

### Errors

| Status | When | Example `message` / `errors` |
|---|---|---|
| `400` | Unknown filter value, bad page number, empty search | `errors: {"size": ["Must be one of: mega, large, ..."]}` |
| `404` | Unknown ticker, a type without pages, unknown slug, page out of range | `"No stock page for 'SPY'."` |
| `405` | Any method other than GET/HEAD/OPTIONS | |

### Caching

- Responses carry `Cache-Control: public, max-age=300` and an `ETag`.
- Send the ETag back as `If-None-Match`; if nothing changed you get `304 Not
  Modified` with an empty body.
- The server caches responses in Redis until the next successful data sync.
  **After deploying code that changes a response, run
  `python manage.py clear_api_cache`**, or old responses are served for up to
  24 hours.

---

## GET /overview/

Everything the home page shows except the search box.

```bash
curl -s http://localhost:8000/api/v1/overview/
```

| Field | Notes |
|---|---|
| `companies`, `total_market_cap`, `average_market_cap`, `total_employees` | across every stock with a page |
| `sectors_covered` | sectors with at least one company, excluding "Not classified" |
| `by_sector` | top 10 sectors by company count; "Not classified" always last |
| `by_exchange` | every exchange with companies |
| `by_size` | company count per size bucket |
| `largest` | 6 largest companies (stock rows) |
| `as_of` | last reference sync |

```json
{
  "success": true,
  "message": "",
  "data": {
    "companies": 5699,
    "total_market_cap": 19664395001555.46,
    "average_market_cap": 26645521682.32447,
    "total_employees": 10183010,
    "sectors_covered": 165,
    "by_sector": [
      { "slug": "pharmaceutical-preparations", "name": "Pharmaceutical Preparations",
        "companies": 75, "total_market_cap": 779966578094.68, "indexable": true }
    ],
    "by_exchange": [
      { "slug": "nasdaq", "name": "Nasdaq", "companies": 3529,
        "total_market_cap": 13805538334375.39, "indexable": true }
    ],
    "by_size": [
      { "slug": "mega", "name": "Mega cap", "companies": 16 }
    ],
    "largest": [
      {
        "ticker": "AAPL", "display_name": "Apple", "name": "Apple Inc.",
        "security_type": "common",
        "exchange": { "slug": "nasdaq", "name": "Nasdaq" },
        "sector": { "slug": "electronic-computers", "name": "Electronic Computers" },
        "hq": "Cupertino, CA", "total_employees": 166000,
        "market_cap": 4912984755200.0, "size_bucket": "mega", "indexable": true
      }
    ],
    "as_of": "2026-10-12T18:04:34.866850+00:00"
  }
}
```

---

## GET /stocks/

The stock directory. Also used for the company table on sector and exchange
hubs (`?sector=` / `?exchange=`).

| Query parameter | Values | Default |
|---|---|---|
| `exchange` | exchange slug | all |
| `sector` | sector slug, or `not-classified` | all |
| `type` | `common`, `adr`, `spac` | all |
| `size` | a `size_bucket` value | all |
| `q` | text; matches ticker prefix or name | — |
| `ordering` | `-market_cap`, `name`, `ticker`, `-employees` | `-market_cap` |
| `page` | 1, 2, … | 1 |
| `page_size` | 1–100 | 50 |

Filters combine with AND. Companies with no market cap (or no employee count)
sort last.

```bash
# Largest first, first page
curl -s "http://localhost:8000/api/v1/stocks/"

# Mega caps on Nasdaq, two per page
curl -s "http://localhost:8000/api/v1/stocks/?exchange=nasdaq&size=mega&page_size=2"

# All SPACs, A to Z
curl -s "http://localhost:8000/api/v1/stocks/?type=spac&ordering=name"

# A sector hub's company table, page 2
curl -s "http://localhost:8000/api/v1/stocks/?sector=pharmaceutical-preparations&page=2"

# Free-text filter
curl -s "http://localhost:8000/api/v1/stocks/?q=acquisition"
```

```json
{
  "success": true,
  "message": "",
  "data": {
    "count": 8,
    "page": 1,
    "page_size": 2,
    "num_pages": 4,
    "results": [
      {
        "ticker": "AAPL", "display_name": "Apple", "name": "Apple Inc.",
        "security_type": "common",
        "exchange": { "slug": "nasdaq", "name": "Nasdaq" },
        "sector": { "slug": "electronic-computers", "name": "Electronic Computers" },
        "hq": "Cupertino, CA", "total_employees": 166000,
        "market_cap": 4912984755200.0, "size_bucket": "mega", "indexable": true
      },
      {
        "ticker": "AMZN", "display_name": "Amazon.Com", "name": "Amazon.Com Inc",
        "security_type": "common",
        "exchange": { "slug": "nasdaq", "name": "Nasdaq" },
        "sector": { "slug": "retail-catalog-mail-order-houses", "name": "Retail-Catalog & Mail-Order Houses" },
        "hq": "Seattle, WA", "total_employees": 1576000,
        "market_cap": 2830652270699.96, "size_bucket": "mega", "indexable": true
      }
    ],
    "as_of": "2026-10-12T18:04:34.866850+00:00"
  }
}
```

Errors:

```bash
curl -s "http://localhost:8000/api/v1/stocks/?size=huge"   # 400
curl -s "http://localhost:8000/api/v1/stocks/?page=9999"   # 404
```

```json
{ "success": false, "message": "Request failed", "data": null,
  "errors": { "size": ["Must be one of: mega, large, mid, small, micro, nano, unknown."] } }
```

---

## GET /stocks/{ticker}/

The stock profile. The ticker is case-insensitive, and dotted tickers work
(`BRK.A`, `BF.B`).

```bash
curl -s http://localhost:8000/api/v1/stocks/AAPL/
curl -s http://localhost:8000/api/v1/stocks/brk.a/
curl -s http://localhost:8000/api/v1/stocks/SPY/   # 404: ETFs have no page
```

All the stock-row fields, plus:

| Field | Type | Notes |
|---|---|---|
| `description` | string \| null | from public filings via the provider |
| `website`, `phone` | string \| null | |
| `address` | `{line1, city, state, postal_code}` \| null | |
| `country`, `currency` | string | `US`, `USD` |
| `cik` | string \| null | SEC filer ID |
| `composite_figi`, `share_class_figi` | string \| null | global security IDs |
| `sic_code`, `ticker_root` | string \| null | |
| `round_lot` | number \| null | standard trading block |
| `shares_outstanding` | `{value, basis}` \| null | `basis` is `class` (this share class) or `weighted` (fallback, all classes) |
| `cap_per_employee` | number \| null | market cap ÷ employees |
| `list_date` | date \| null | |
| `active` | boolean | `false` for delisted companies |
| `edgar_url` | string \| null | SEC EDGAR filings page, from the CIK |
| `as_of` | timestamp \| null | when this company's profile was last fetched |

For the SPAC and ADR notices, use `security_type`.

```json
{
  "success": true,
  "message": "",
  "data": {
    "ticker": "AAPL", "display_name": "Apple", "name": "Apple Inc.",
    "security_type": "common",
    "exchange": { "slug": "nasdaq", "name": "Nasdaq" },
    "sector": { "slug": "electronic-computers", "name": "Electronic Computers" },
    "hq": "Cupertino, CA", "total_employees": 166000,
    "market_cap": 4912984755200.0, "size_bucket": "mega", "indexable": true,
    "description": "Apple is among the largest companies in the world, ...",
    "website": "https://www.apple.com",
    "phone": "(408) 996-1010",
    "address": { "line1": "One Apple Park Way", "city": "Cupertino", "state": "CA", "postal_code": "95014" },
    "country": "US",
    "currency": "USD",
    "cik": "0000320193",
    "composite_figi": "BBG000B9XRY4",
    "share_class_figi": "BBG001S5N8V8",
    "sic_code": "3571",
    "ticker_root": "AAPL",
    "round_lot": 40,
    "shares_outstanding": { "value": 14594180000, "basis": "class" },
    "cap_per_employee": 29596293.71,
    "list_date": null,
    "active": true,
    "edgar_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193",
    "as_of": "2026-10-11T23:47:50.329825+00:00"
  }
}
```

---

## GET /stocks/{ticker}/peers/

The comparison blocks on a profile. A separate call, so a profile stays
cached while other companies change.

```bash
curl -s http://localhost:8000/api/v1/stocks/AAPL/peers/
```

| Field | Notes |
|---|---|
| `rank` | position by market cap among companies with a known market cap; `null` if this one has none |
| `ranked_total` | how many companies have a known market cap |
| `context` | the 5 largest companies, plus this one if it is not among them ("market cap in context" bars) |
| `peers` | up to 5 largest in the same sector; the same exchange if the sector has fewer than 2 others. Always empty for SPACs |
| `related` | 3 companies: same sector first, then the same exchange |

```json
{
  "success": true,
  "message": "",
  "data": {
    "ticker": "AAPL",
    "rank": 1,
    "ranked_total": 738,
    "context": [ { "ticker": "AAPL", "display_name": "Apple", "market_cap": 4912984755200.0, "...": "stock row" } ],
    "peers":   [ { "ticker": "AMZN", "display_name": "Amazon.Com", "...": "stock row" } ],
    "related": [ { "ticker": "AMZN", "display_name": "Amazon.Com", "...": "stock row" } ],
    "as_of": "2026-10-12T18:04:34.866850+00:00"
  }
}
```

---

## GET /sectors/

Every sector with at least one company, by company count. "Not classified"
is always last.

```bash
curl -s http://localhost:8000/api/v1/sectors/
```

```json
{
  "success": true,
  "message": "",
  "data": {
    "results": [
      { "slug": "pharmaceutical-preparations", "name": "Pharmaceutical Preparations",
        "companies": 75, "total_market_cap": 779966578094.68, "indexable": true },
      { "slug": "not-classified", "name": "Not classified",
        "companies": 5093, "total_market_cap": 2942099831880.91, "indexable": false }
    ],
    "as_of": "2026-10-12T18:04:34.866850+00:00"
  }
}
```

---

## GET /sectors/{slug}/

A sector hub: stats, the editorial intro, and the 10 largest companies (for
the bar chart). For the full company table, call
`/stocks/?sector={slug}`. `not-classified` works as a slug.

```bash
curl -s http://localhost:8000/api/v1/sectors/blank-checks/
curl -s "http://localhost:8000/api/v1/stocks/?sector=blank-checks"   # the company table
```

| Field | Notes |
|---|---|
| `sic_code` | the industry code; `null` for not-classified |
| `primer` | short intro, written in the admin; `null` until written |
| `companies`, `total_market_cap`, `average_market_cap`, `total_employees` | `total_employees` is `null` when no company reports it |
| `largest` | 10 largest (stock rows) |

```json
{
  "success": true,
  "message": "",
  "data": {
    "slug": "blank-checks",
    "name": "Blank Checks",
    "sic_code": "6770",
    "primer": null,
    "companies": 43,
    "total_market_cap": 11861014228.75,
    "average_market_cap": 289293029.9695122,
    "total_employees": 25,
    "largest": [
      { "ticker": "BCSS", "display_name": "Bain Capital GSS Investment",
        "security_type": "spac", "market_cap": 597432000.0, "indexable": false, "...": "stock row" }
    ],
    "indexable": true,
    "as_of": "2026-10-12T18:04:34.866850+00:00"
  }
}
```

---

## GET /exchanges/

Every exchange with at least one company, by company count.

```bash
curl -s http://localhost:8000/api/v1/exchanges/
```

```json
{
  "success": true,
  "message": "",
  "data": {
    "results": [
      { "slug": "nasdaq", "name": "Nasdaq", "companies": 3529,
        "total_market_cap": 13805538334375.39, "indexable": true },
      { "slug": "nyse", "name": "NYSE", "companies": 1922,
        "total_market_cap": 5855496413564.38, "indexable": true }
    ],
    "as_of": "2026-10-12T18:04:34.866850+00:00"
  }
}
```

---

## GET /exchanges/{slug}/

An exchange hub. Same shape as a sector hub, with `mic` (the exchange code)
in place of `sic_code` and `primer`. For the full company table, call
`/stocks/?exchange={slug}`.

```bash
curl -s http://localhost:8000/api/v1/exchanges/nasdaq/
```

```json
{
  "success": true,
  "message": "",
  "data": {
    "slug": "nasdaq",
    "name": "Nasdaq",
    "mic": "XNAS",
    "companies": 3529,
    "total_market_cap": 13805538334375.39,
    "average_market_cap": 31163743418.454605,
    "total_employees": 3075655,
    "largest": [ { "ticker": "AAPL", "display_name": "Apple", "...": "stock row" } ],
    "indexable": true,
    "as_of": "2026-10-12T18:04:34.866850+00:00"
  }
}
```

---

## GET /search/

Typeahead for the search box. Up to 10 results, ranked: exact ticker, then
ticker prefix, then names starting with the text, then fuzzy name matches
on the full company name (so `microsft` still finds Microsoft; heavier typos
such as `nvdia` find nothing). Ties go to the larger company.

| Query parameter | Notes |
|---|---|
| `q` | required; up to 50 characters are used |

```bash
curl -s "http://localhost:8000/api/v1/search/?q=appl"
curl -s "http://localhost:8000/api/v1/search/?q=nvda"
curl -s "http://localhost:8000/api/v1/search/"          # 400: q is required
```

```json
{
  "success": true,
  "message": "",
  "data": {
    "query": "appl",
    "results": [
      { "ticker": "AAPL", "display_name": "Apple", "security_type": "common",
        "exchange": { "slug": "nasdaq", "name": "Nasdaq" } },
      { "ticker": "AMAT", "display_name": "Applied Materials", "security_type": "common",
        "exchange": { "slug": "nasdaq", "name": "Nasdaq" } }
    ]
  }
}
```

---

## GET /sitemap/

Every **indexable** stock, sector and exchange, with a last-modified date,
for building `sitemap.xml`. Pages with `indexable: false` are left out.

```bash
curl -s http://localhost:8000/api/v1/sitemap/
```

```json
{
  "success": true,
  "message": "",
  "data": {
    "stocks":    [ { "ticker": "A", "lastmod": "2026-10-11" }, { "ticker": "AA", "lastmod": "2026-10-11" } ],
    "sectors":   [ { "slug": "pharmaceutical-preparations", "lastmod": "2026-10-12" } ],
    "exchanges": [ { "slug": "nasdaq", "lastmod": "2026-10-12" }, { "slug": "nyse", "lastmod": "2026-10-12" } ]
  }
}
```

---

## Caching with curl

```bash
# See the headers
curl -si http://localhost:8000/api/v1/stocks/AAPL/ | head -n 12

# Send the ETag back: 304 Not Modified, empty body
curl -si http://localhost:8000/api/v1/stocks/AAPL/ \
  -H 'If-None-Match: "36b785134104c71f61ab84e9490b502b"'
```

The ETag above is an example; copy the one your server returns.

---

## Coming later

Not built yet; the profile shows placeholders for these.

| Endpoint | Fills |
|---|---|
| `GET /stocks/{ticker}/quote/` | Quote block: delayed price, change, day range, 52-week range |
| `GET /stocks/{ticker}/prices/?range=1y` | Price chart |
| `GET /stocks/{ticker}/financials/` | Revenue, net income, EPS, P/E, dividend yield |
| `GET /stocks/{ticker}/news/` | Latest news |

# StockPrices --- Project Summary

## 1. Project Overview

**StockPrices** is a U.S. stock market information platform focused on
providing users with current and historical information about publicly
traded U.S. companies.

The platform will provide:

-   Stock prices
-   Historical price charts
-   Market statistics
-   Company information
-   Financial data
-   Corporate actions
-   Market movers
-   Real-time price updates
-   Stock search and individual stock pages

The initial data provider will be **Massive**, subject to the
appropriate commercial/display licensing for production use.

------------------------------------------------------------------------

## 2. Main Objective

Build a reliable stock-data platform where a user can search for a U.S.
stock such as:

-   AAPL
-   MSFT
-   NVDA
-   TSLA
-   AMZN

and view:

-   Current Price
-   Price Change
-   Change %
-   Open
-   High
-   Low
-   Previous Close
-   Volume
-   Market Cap
-   Historical Chart
-   Company Information
-   Financial Information
-   Corporate Actions

The system should maintain its own database of historical/reference data
while using a real-time feed for current market information.

------------------------------------------------------------------------

## 3. Core Data Categories

### A. Stock / Company Data

Store relatively stable information:

-   Ticker
-   Company Name
-   Exchange
-   Primary Exchange
-   Currency
-   CIK
-   FIGI
-   Industry
-   Sector / SIC
-   Company Description
-   Website
-   Logo
-   Listing Date
-   Active / Inactive Status
-   Market Cap
-   Employee Count

### B. Current Market Data

Real-time data:

-   Last Traded Price
-   Price Change
-   Change %
-   Open
-   High
-   Low
-   Previous Close
-   Volume
-   VWAP
-   Bid Price
-   Bid Quantity
-   Ask Price
-   Ask Quantity
-   Timestamp

This data should primarily be handled through **Redis + WebSockets**,
rather than continuously writing every update to PostgreSQL.

### C. Historical Price Data

#### Daily

-   Date
-   Open
-   High
-   Low
-   Close
-   Volume
-   VWAP

Stored permanently in PostgreSQL.

#### Intraday

Initially support:

-   1 minute
-   5 minute
-   15 minute
-   1 hour

Do **not** store every individual trade/tick initially.

### D. Financial Data

For each company:

-   Revenue
-   Gross Profit
-   Operating Income
-   Net Income
-   EPS
-   Assets
-   Liabilities
-   Equity
-   Cash
-   Debt
-   Operating Cash Flow
-   Free Cash Flow

Display/calculated ratios:

-   P/E
-   P/B
-   EPS
-   ROE
-   ROCE
-   Debt / Equity
-   Dividend Yield

Financial data should be stored by reporting period rather than
overwritten.

### E. Corporate Data

#### Corporate Actions

-   Dividends
-   Stock Splits
-   Reverse Splits
-   Other Corporate Actions

#### Company Filings / Announcements

-   Announcement
-   Filing Type
-   Title
-   Description
-   Published Date
-   Document URL

------------------------------------------------------------------------

## 4. Main Website Features

### Home

-   Search stocks
-   Market overview
-   Top gainers
-   Top losers
-   Most active
-   Major indices

### Stock Search

Search by:

-   Ticker
-   Company name

Example:

``` text
Apple
→ AAPL
→ Apple Inc.
→ NASDAQ
```

### Stock Details Page

Example:

``` text
/stocks/AAPL
```

Contains:

-   Company name
-   Current price
-   Price change
-   Change %
-   Open
-   High
-   Low
-   Previous close
-   Volume
-   Market cap
-   Price chart
-   Company overview
-   Financials
-   Ratios
-   Dividends
-   Splits
-   Corporate actions
-   Historical data

------------------------------------------------------------------------

## 5. Backend Architecture

``` text
                         Massive
                            │
              ┌─────────────┴─────────────┐
              │                           │
           REST API                  WebSocket
              │                           │
              ▼                           ▼
       Django Data Layer          Real-time Worker
              │                           │
              ▼                           ▼
         PostgreSQL                     Redis
              │                           │
              └──────────────┬────────────┘
                             ▼
                       Django REST API
                             │
                             ▼
                         Frontend
```

### PostgreSQL

Permanent data:

-   Companies
-   Daily Prices
-   Intraday Bars
-   Financials
-   Corporate Actions
-   Announcements
-   Sync History

### Redis

Temporary/high-frequency data:

-   Current Quotes
-   Live Prices
-   WebSocket state
-   Caching
-   Celery broker/result backend

### Celery

Background processing:

-   Daily price synchronization
-   Ticker synchronization
-   Financial data synchronization
-   Corporate-action synchronization
-   Data validation
-   Periodic cleanup

------------------------------------------------------------------------

## 6. Django Application Structure

Start small:

``` text
stockprices/
│
├── config/
│
├── market/
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── urls.py
│   └── services/
│
├── data_provider/
│   ├── massive.py
│   └── services.py
│
├── sync/
│   ├── models.py
│   ├── tasks.py
│   └── services.py
│
├── realtime/
│   ├── consumers.py
│   └── services.py
│
└── fundamentals/
    ├── models.py
    ├── services.py
    └── tasks.py
```

Later:

``` text
accounts/
watchlists/
notifications/
```

------------------------------------------------------------------------

## 7. Initial Database Models

Start with:

-   Stock
-   DailyPrice
-   IntradayBar
-   DataSyncJob

Then add:

-   FinancialStatement
-   FinancialRatio
-   Dividend
-   StockSplit
-   CorporateAction
-   Announcement

Avoid creating 20+ models before the basic data pipeline works.

------------------------------------------------------------------------

## 8. Data Synchronization Strategy

### Stock Master

Synchronize periodically:

``` text
Massive
   ↓
Ticker Reference API
   ↓
Stock table
```

Keep inactive/delisted stocks instead of deleting them.

### Daily Prices

After the U.S. market closes:

``` text
Massive
   ↓
Daily market data
   ↓
Validate
   ↓
Upsert DailyPrice
   ↓
Mark synchronization successful
```

A `DataSyncJob` table should track:

-   Job Type
-   Provider
-   Data Date
-   Start Time
-   End Time
-   Status
-   Records Processed
-   Error

This prevents silent stale-data problems.

### Real-Time Prices

During market hours:

``` text
Massive WebSocket
        ↓
Real-time worker
        ↓
Redis
        ↓
Django WebSocket
        ↓
Frontend
```

Do not write every real-time update to PostgreSQL.

------------------------------------------------------------------------

## 9. Backend API

Initial endpoints:

``` http
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

Later:

``` http
GET /api/market/indices/
GET /api/stocks/{ticker}/news/
GET /api/stocks/{ticker}/financial-ratios/
```

------------------------------------------------------------------------

## 10. Development Chronology

### Phase 1 --- Data Foundation

``` text
Django
↓
PostgreSQL
↓
Redis
↓
Celery
↓
Massive API client
```

### Phase 2 --- Stock Master

``` text
Stock model
↓
Massive ticker API
↓
Import U.S. stocks
↓
Stock API
```

Target:

``` http
GET /api/stocks/AAPL/
```

### Phase 3 --- Historical Prices

``` text
DailyPrice model
↓
Massive historical API
↓
Import historical data
↓
Daily synchronization
```

Target:

``` http
GET /api/stocks/AAPL/prices/
```

### Phase 4 --- Intraday Data

``` text
IntradayBar model
↓
Massive aggregates
↓
1m / 5m / 15m
↓
Chart API
```

### Phase 5 --- Real-Time

``` text
Massive WebSocket
↓
Worker
↓
Redis
↓
Django WebSocket
```

### Phase 6 --- Fundamentals

Add:

-   Financials
-   Ratios
-   Dividends
-   Splits
-   Corporate actions

### Phase 7 --- Search and Market Features

Add:

-   Stock search
-   Top gainers
-   Top losers
-   Most active
-   Market overview
-   Indices

### Phase 8 --- User Features

Only after the data system is reliable:

-   Authentication
-   Watchlists
-   Favorites
-   Price alerts
-   User preferences

------------------------------------------------------------------------

## 11. MVP Definition

The first usable version should support:

``` text
Search
   ↓
AAPL
   ↓
Stock Details
   ├── Current Price
   ├── Change
   ├── OHLC
   ├── Volume
   ├── Historical Chart
   ├── Company Information
   └── Basic Financial Data
```

Behind it:

``` text
Massive
   ↓
Django
   ├── PostgreSQL
   ├── Redis
   └── Celery
```

Do not build the frontend first.

Get this pipeline working first:

``` text
Massive
   ↓
Django
   ↓
PostgreSQL
   ↓
GET /api/stocks/AAPL/
   ↓
Correct response
```

Then add historical data, real-time data, and finally the frontend.

------------------------------------------------------------------------

## 12. Project Goal

> **StockPrices is a U.S. stock market information platform that
> aggregates real-time, historical, company, financial, and
> corporate-action data into searchable stock profiles, charts, and
> market insights.**

# Massive APIs and Their Usage in ShockPrices

Based on the project documentation, here is the complete list of Massive APIs and what they are used for, along with an explanation of exactly how they fit into the scope of our app.

## Reference & Master Data APIs
These APIs provide structural data about the markets and companies.

* **Ticker list** (`GET /v3/reference/tickers`)
  * **Use:** Returns the master list of all stock tickers (active and delisted).
  * **Useful in our app?** **Yes.** We use this in our `sync_stocks` service to keep our `market_stock` database table populated with the universe of available stocks.
* **Ticker detail** (`GET /v3/reference/tickers/{ticker}`)
  * **Use:** Returns deep company profile data (description, SIC code, market cap, logo URLs, address).
  * **Useful in our app?** **Yes.** We use this in our `sync_stock_details` service to fill in the missing company profiles.
* **Ticker types** (`GET /v3/reference/tickers/types`)
  * **Use:** Lists asset types (Common Stock, ETF, Preferred, etc).
  * **Useful in our app?** **Yes.** It's useful for mapping the `asset_type` field to a human-readable format if we build a filter UI.
* **Exchanges** (`GET /v3/reference/exchanges`) & **Conditions** (`GET /v3/reference/conditions`)
  * **Use:** Reference data for exchange codes and trade conditions.
  * **Useful in our app?** **Yes.** Required for our "exchange reference data" scope.
* **Related companies** (`GET /v1/related-companies/{ticker}`)
  * **Use:** Returns a list of companies in a similar sector/industry.
  * **Useful in our app?** Currently **Out of Scope**, but would be useful if you build a "Similar Stocks" feature on the frontend.

## Pricing & Charting APIs (Aggregates)
These APIs provide OHLCV (Open, High, Low, Close, Volume) data over time.

* **Custom bars / Intraday** (`GET /v2/aggs/ticker/{stocksTicker}/range/{multiplier}/{timespan}/{from}/{to}`)
  * **Use:** Fetches historical pricing bars at any resolution (e.g., 1-minute, 1-hour, 1-day).
  * **Useful in our app?** **Yes.** This is the core API required for our "Historical daily OHLCV" and "Intraday bars (1m / 5m / 15m / 1h) for charting" features. We will need a service to pull this into the `market_daily_price` and `market_intraday_bar` tables.
* **Whole-market daily bars** (`GET /v2/aggs/grouped/locale/us/market/stocks/{date}`)
  * **Use:** Gets the daily Open/Close/High/Low for *every stock in the entire market* for a specific day in one call.
  * **Useful in our app?** **Yes.** Extremely useful for running a fast daily cron job to update all End-of-Day prices.
* **Previous day bar** (`GET /v2/aggs/ticker/{stocksTicker}/prev`) & **Daily open/close** (`GET /v1/open-close/...`)
  * **Use:** Quick lookups for yesterday's closing price or today's official open/close.
  * **Useful in our app?** **No.** It's usually better to just use the "Custom bars" or "Whole-market" endpoints to ingest data into our own DB rather than pinging this on the fly.

## Snapshots & Real-Time Data APIs
These provide "Right Now" data rather than historical data.

* **Single ticker snapshot** (`GET /v2/snapshot/locale/us/markets/stocks/tickers/{stocksTicker}`)
* **Full market snapshot** (`GET /v2/snapshot/locale/us/markets/stocks/tickers`)
  * **Use:** Gives the current minute's price, today's change %, and latest volume.
  * **Useful in our app?** **Yes.** Per your architecture docs, these will be used to serve "Current quotes / snapshots" directly from Redis cache.
* **Top movers** (`GET /v2/snapshot/locale/us/markets/stocks/{direction}`)
  * **Use:** Lists the biggest gainers and losers of the day.
  * **Useful in our app?** **Yes.** Specifically requested in scope ("Market movers").
* **Last trade / quote** (`GET /v2/last/trade/{stocksTicker}`, `GET /v2/last/nbbo/{stocksTicker}`)
  * **Use:** Gets the absolute latest trade execution or bid/ask spread.
  * **Useful in our app?** **Maybe.** Snapshots usually cover our needs, but NBBO (National Best Bid and Offer) is good if you need exact current spreads.

## Fundamental & Financial Data APIs
* **Income statements, Balance sheets, Cash flow statements, Ratios** (`GET /stocks/financials/v1/...`)
  * **Use:** Deep fundamental accounting data from SEC filings.
  * **Useful in our app?** **Yes.** Needed for the "Fundamentals" scope. We will need to build new database tables to store these metrics.

## Corporate Actions & News APIs
* **Dividends** (`GET /v3/reference/dividends`), **Splits** (`GET /v3/reference/splits`), **IPOs** (`GET /vX/reference/ipos`), **Ticker events** (`GET /vX/reference/tickers/{id}/events`)
  * **Use:** Tracks when companies split shares, pay out cash, go public, or change their ticker symbol.
  * **Useful in our app?** **Yes.** Needed for the "Corporate actions" scope. Handling splits is especially critical so our historical charts remain mathematically accurate.
* **News** (`GET /v2/reference/news`) & **Filings index** (`GET /stocks/filings/vX/index`)
  * **Use:** Fetches recent press releases, news articles, and SEC filings.
  * **Useful in our app?** **Yes.** Needed for the "Filings and news" scope.

## Market Utilities
* **Market status** (`GET /v1/marketstatus/now`, `GET /v1/marketstatus/upcoming`)
  * **Use:** Tells you if the NYSE/NASDAQ is currently Open, Closed, or in Pre-Market/After-Hours.
  * **Useful in our app?** **Yes.** Critical for knowing when our sync jobs should actually be running (there's no need to fetch real-time data at 2 AM on a Sunday).
* **Indicators** (`GET /v1/indicators/{sma,ema,rsi,macd}/{stockTicker}`)
  * **Use:** Calculates technical indicators server-side.
  * **Useful in our app?** **No.** It's generally better to calculate technical indicators on the frontend charting library (like TradingView or Highcharts) rather than paying for API calls to get them.

---

## Summary of What to Build Next
Based on this API list and your project scope, the next logical steps for your app would be to create the data providers and sync jobs for:
1. **Daily Prices:** Hitting the *Whole-market daily bars* endpoint every day at 4:15 PM EST to populate your `DailyPrice` model.
2. **Corporate Actions (Splits/Dividends):** Syncing splits so you can adjust historical prices when a stock like NVDA does a 10-for-1 split.
3. **WebSockets:** Connecting to `wss://delayed.massive.com/stocks` to stream live prices into your Redis cache.

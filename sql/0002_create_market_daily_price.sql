-- market_daily_price — one split-adjusted OHLCV bar per stock per trading day.
--
-- Source: Massive GET /v2/aggs/grouped/locale/us/market/stocks/{date} for the
-- nightly sync, and Flat Files for the historical backfill.
--
-- Sizing: ~10,000 tickers x ~252 sessions/year = ~2.5M rows per year. The
-- composite primary key (stock_id, date) is the access path for every chart
-- query, so it carries the clustering — a surrogate id would add 8 bytes and
-- a second index for nothing.

CREATE TABLE IF NOT EXISTS market_daily_price (
    stock_id      BIGINT        NOT NULL REFERENCES market_stock (id) ON DELETE CASCADE,
    date          DATE          NOT NULL,

    open          NUMERIC(18, 6) NOT NULL,
    high          NUMERIC(18, 6) NOT NULL,
    low           NUMERIC(18, 6) NOT NULL,
    close         NUMERIC(18, 6) NOT NULL,

    -- Massive types volume as a number rather than an integer; NUMERIC keeps
    -- us honest for OTC and for any fractional share reporting.
    volume        NUMERIC(20, 4) NOT NULL DEFAULT 0,
    vwap          NUMERIC(18, 6),
    transactions  BIGINT,

    -- Massive returns split-adjusted bars by default. We store the adjusted
    -- series, and record which it is so an unadjusted backfill can never be
    -- silently mixed in.
    adjusted      BOOLEAN       NOT NULL DEFAULT TRUE,

    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT market_daily_price_pkey PRIMARY KEY (stock_id, date),

    -- A bar where the high is not the highest is a mapping bug in the sync
    -- task. Catch it at write time, not six months later on a chart.
    CONSTRAINT market_daily_price_ohlc_sane
        CHECK (high >= low AND high >= open AND high >= close
               AND low <= open AND low <= close),
    CONSTRAINT market_daily_price_volume_non_negative
        CHECK (volume >= 0)
);

-- "What moved on 2026-09-21?" — market-wide queries for a single session,
-- which the PK cannot serve because stock_id leads it.
CREATE INDEX IF NOT EXISTS market_daily_price_date_idx
    ON market_daily_price (date);

DROP TRIGGER IF EXISTS market_daily_price_set_updated_at ON market_daily_price;
CREATE TRIGGER market_daily_price_set_updated_at
    BEFORE UPDATE ON market_daily_price
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

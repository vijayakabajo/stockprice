-- market_intraday_bar — OHLCV bars at sub-daily resolution, for charting.
--
-- Source: Massive GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
--
-- Sizing: this is the table that gets big. One ticker at 1-minute resolution
-- is ~960 bars/day including pre- and post-market, so 500 tickers is ~480k
-- rows/day. Two decisions follow from that:
--
--   1. Retention is a policy, not an accident. 1m bars are pruned on a
--      schedule; 15m and 1h are kept long. See the cleanup task in sync/.
--   2. This table is the first candidate for monthly range partitioning on
--      `ts`. It is deliberately NOT partitioned yet — partitioning an empty
--      table is speculation, and converting later is a contained change while
--      the retention window is short.

CREATE TABLE IF NOT EXISTS market_intraday_bar (
    stock_id      BIGINT         NOT NULL REFERENCES market_stock (id) ON DELETE CASCADE,

    -- '1m' | '5m' | '15m' | '1h' — see market.models.Timespan.
    timespan      VARCHAR(5)     NOT NULL,

    -- Start of the aggregate window. Massive sends Unix milliseconds; the sync
    -- task converts to an aware UTC datetime. Bars cover pre-market, regular
    -- and after-hours sessions.
    ts            TIMESTAMPTZ    NOT NULL,

    open          NUMERIC(18, 6) NOT NULL,
    high          NUMERIC(18, 6) NOT NULL,
    low           NUMERIC(18, 6) NOT NULL,
    close         NUMERIC(18, 6) NOT NULL,
    volume        NUMERIC(20, 4) NOT NULL DEFAULT 0,
    vwap          NUMERIC(18, 6),
    transactions  BIGINT,

    created_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    -- Leading with (stock_id, timespan) matches the only query that matters:
    -- one ticker, one resolution, a time range.
    CONSTRAINT market_intraday_bar_pkey PRIMARY KEY (stock_id, timespan, ts),

    CONSTRAINT market_intraday_bar_timespan_valid
        CHECK (timespan IN ('1m', '5m', '15m', '1h')),
    CONSTRAINT market_intraday_bar_ohlc_sane
        CHECK (high >= low AND high >= open AND high >= close
               AND low <= open AND low <= close),
    CONSTRAINT market_intraday_bar_volume_non_negative
        CHECK (volume >= 0)
);

-- Supports the retention sweep: "delete 1m bars older than N days" across all
-- tickers at once.
CREATE INDEX IF NOT EXISTS market_intraday_bar_timespan_ts_idx
    ON market_intraday_bar (timespan, ts);

DROP TRIGGER IF EXISTS market_intraday_bar_set_updated_at ON market_intraday_bar;
CREATE TRIGGER market_intraday_bar_set_updated_at
    BEFORE UPDATE ON market_intraday_bar
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

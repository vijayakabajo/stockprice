-- market_exchange — U.S. stock exchanges, keyed by MIC.
--
-- Source: Massive GET /v3/reference/exchanges?asset_class=stocks&locale=us.
-- The provider columns are overwritten on every sync. display_name and slug
-- are ours: set when a row is first inserted, then edited in the admin and
-- never touched by the sync.
--
-- market_stock.primary_exchange holds the MIC but is not a foreign key here:
-- the ticker sync can deliver a stock before its exchange row exists, and
-- some tickers arrive with no exchange at all.

CREATE TABLE IF NOT EXISTS market_exchange (
    mic             VARCHAR(10)  PRIMARY KEY,              -- e.g. XNAS

    -- Provider ---------------------------------------------------------------
    operating_mic   VARCHAR(10)  NOT NULL DEFAULT '',
    name            VARCHAR(255) NOT NULL DEFAULT '',      -- "Nasdaq Stock Market"
    acronym         VARCHAR(50)  NOT NULL DEFAULT '',
    exchange_type   VARCHAR(20)  NOT NULL DEFAULT '',      -- Massive `type`: exchange, TRF, SIP
    url             VARCHAR(500) NOT NULL DEFAULT '',
    provider_id     INTEGER,                               -- Massive `id`

    -- Editorial --------------------------------------------------------------
    display_name    VARCHAR(100) NOT NULL,                 -- "Nasdaq"
    slug            VARCHAR(100) NOT NULL,                 -- /exchanges/nasdaq

    -- Bookkeeping ------------------------------------------------------------
    last_synced_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS market_exchange_slug_key
    ON market_exchange (slug);

DROP TRIGGER IF EXISTS market_exchange_set_updated_at ON market_exchange;
CREATE TRIGGER market_exchange_set_updated_at
    BEFORE UPDATE ON market_exchange
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

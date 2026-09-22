-- market_stock — the ticker master.
--
-- Source: Massive GET /v3/reference/tickers and /v3/reference/tickers/{ticker}
-- Delisted rows are kept (active = false), never deleted: historical prices
-- still reference them.

CREATE TABLE IF NOT EXISTS market_stock (
    id                              BIGSERIAL PRIMARY KEY,

    -- Identity -------------------------------------------------------------
    ticker                          VARCHAR(20)  NOT NULL,
    name                            VARCHAR(255) NOT NULL DEFAULT '',
    ticker_root                     VARCHAR(20)  NOT NULL DEFAULT '',
    ticker_suffix                   VARCHAR(20)  NOT NULL DEFAULT '',

    -- Classification -------------------------------------------------------
    market                          VARCHAR(20)  NOT NULL DEFAULT 'stocks',
    locale                          VARCHAR(10)  NOT NULL DEFAULT 'us',
    asset_type                      VARCHAR(20)  NOT NULL DEFAULT '',  -- Massive `type`: CS, ETF, ADRC, ...
    primary_exchange                VARCHAR(20)  NOT NULL DEFAULT '',  -- ISO MIC, e.g. XNAS
    currency_name                   VARCHAR(20)  NOT NULL DEFAULT 'usd',
    active                          BOOLEAN      NOT NULL DEFAULT TRUE,

    -- External identifiers -------------------------------------------------
    cik                             VARCHAR(20)  NOT NULL DEFAULT '',
    composite_figi                  VARCHAR(20)  NOT NULL DEFAULT '',
    share_class_figi                VARCHAR(20)  NOT NULL DEFAULT '',

    -- Industry -------------------------------------------------------------
    sic_code                        VARCHAR(10)  NOT NULL DEFAULT '',
    sic_description                 VARCHAR(255) NOT NULL DEFAULT '',

    -- Profile --------------------------------------------------------------
    description                     TEXT         NOT NULL DEFAULT '',
    homepage_url                    VARCHAR(500) NOT NULL DEFAULT '',
    phone_number                    VARCHAR(50)  NOT NULL DEFAULT '',
    logo_url                        VARCHAR(500) NOT NULL DEFAULT '',
    icon_url                        VARCHAR(500) NOT NULL DEFAULT '',
    address1                        VARCHAR(255) NOT NULL DEFAULT '',
    city                            VARCHAR(100) NOT NULL DEFAULT '',
    state                           VARCHAR(50)  NOT NULL DEFAULT '',
    postal_code                     VARCHAR(20)  NOT NULL DEFAULT '',

    -- Size -----------------------------------------------------------------
    -- market_cap needs the headroom: a USD 4T company is 4e12, and NUMERIC
    -- costs nothing to over-size.
    market_cap                      NUMERIC(24, 2),
    share_class_shares_outstanding  BIGINT,
    weighted_shares_outstanding     BIGINT,
    round_lot                       INTEGER,
    total_employees                 INTEGER,

    -- Dates ----------------------------------------------------------------
    list_date                       DATE,
    delisted_utc                    TIMESTAMPTZ,

    -- Bookkeeping ----------------------------------------------------------
    -- When this row was last refreshed from the provider, as opposed to
    -- updated_at which changes on any write.
    last_synced_at                  TIMESTAMPTZ,
    created_at                      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Ticker is the lookup key for every /api/stocks/{ticker}/ request.
--
-- Note: an exchange can reassign a delisted symbol to a different company
-- years later. If that ever bites, this becomes a partial unique index on
-- (ticker) WHERE active, with composite_figi as the stable identity. Until
-- then a plain unique constraint keeps the ORM straightforward.
CREATE UNIQUE INDEX IF NOT EXISTS market_stock_ticker_key
    ON market_stock (ticker);

-- Company-name search: "appl" -> "Apple Inc.". Requires pg_trgm (0000).
CREATE INDEX IF NOT EXISTS market_stock_name_trgm_idx
    ON market_stock USING GIN (name gin_trgm_ops);

-- Nearly every list query filters to active = true first.
CREATE INDEX IF NOT EXISTS market_stock_active_idx
    ON market_stock (active);

CREATE INDEX IF NOT EXISTS market_stock_primary_exchange_idx
    ON market_stock (primary_exchange);

CREATE INDEX IF NOT EXISTS market_stock_composite_figi_idx
    ON market_stock (composite_figi)
    WHERE composite_figi <> '';

DROP TRIGGER IF EXISTS market_stock_set_updated_at ON market_stock;
CREATE TRIGGER market_stock_set_updated_at
    BEFORE UPDATE ON market_stock
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

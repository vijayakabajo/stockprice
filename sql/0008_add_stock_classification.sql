-- market_stock classification: the labels the site filters and groups by.
--
-- display_name is written by the ticker sync (the cleanup rules are regex,
-- which belongs in Python). security_type and size_bucket are generated
-- columns: Postgres recomputes them whenever asset_type, SIC, description or
-- market_cap change, whoever the writer is, so they cannot go stale.
--
-- Changing a rule below means a new file that drops and re-adds the column.

ALTER TABLE market_stock
    ADD COLUMN IF NOT EXISTS display_name VARCHAR(255) NOT NULL DEFAULT '';

-- SPACs are listed as common stock; SIC 6770 "BLANK CHECKS" is the reliable
-- signal. The description is only consulted when the SIC code is missing, so
-- a company that merged out of a SPAC ("formerly a blank check company") is
-- not caught by it. ADRC is a common-share ADR; ADR preferreds, rights and
-- warrants (ADRP, ADRR, ADRW) keep their own type.
ALTER TABLE market_stock
    ADD COLUMN IF NOT EXISTS security_type VARCHAR(20) GENERATED ALWAYS AS (
        CASE
            WHEN asset_type = 'CS' AND (
                     sic_code = '6770'
                  OR sic_description ILIKE '%blank check%'
                  OR (sic_code = '' AND description ILIKE '%blank check%')
                 ) THEN 'spac'
            WHEN asset_type = 'ADRC' THEN 'adr'
            WHEN asset_type = 'CS'   THEN 'common'
            ELSE LOWER(asset_type)
        END
    ) STORED;

-- Conventional market-cap buckets. market_cap is NULL until the profile is
-- fetched, and for most ETFs, warrants and units.
ALTER TABLE market_stock
    ADD COLUMN IF NOT EXISTS size_bucket VARCHAR(10) GENERATED ALWAYS AS (
        CASE
            WHEN market_cap IS NULL            THEN 'unknown'
            WHEN market_cap >= 200000000000    THEN 'mega'
            WHEN market_cap >= 10000000000     THEN 'large'
            WHEN market_cap >= 2000000000      THEN 'mid'
            WHEN market_cap >= 300000000       THEN 'small'
            WHEN market_cap >= 50000000        THEN 'micro'
            ELSE 'nano'
        END
    ) STORED;

-- Directory filters and hub groupings. Partial on active: inactive listings
-- never appear in a directory or hub.
CREATE INDEX IF NOT EXISTS market_stock_security_type_idx
    ON market_stock (security_type) WHERE active;

CREATE INDEX IF NOT EXISTS market_stock_size_bucket_idx
    ON market_stock (size_bucket) WHERE active;

CREATE INDEX IF NOT EXISTS market_stock_sic_code_idx
    ON market_stock (sic_code) WHERE sic_code <> '';

-- The default directory sort, and "largest companies" on every hub.
CREATE INDEX IF NOT EXISTS market_stock_active_market_cap_idx
    ON market_stock (market_cap DESC NULLS LAST) WHERE active;

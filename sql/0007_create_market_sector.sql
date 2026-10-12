-- market_sector — one row per SIC code in use, backing the sector hub pages.
--
-- There is no provider endpoint for this. refresh_sectors builds it from the
-- distinct SIC codes in market_stock, which arrive with the ticker-details
-- sync. New codes are inserted with a cleaned-up name and slug; after that,
-- name, slug and primer are editorial and only sic_description is refreshed.
--
-- Not a foreign key from market_stock.sic_code: most stocks have '' until
-- their profile is fetched, and rows here are created after the stocks.

CREATE TABLE IF NOT EXISTS market_sector (
    sic_code         VARCHAR(10)  PRIMARY KEY,             -- e.g. 3826
    sic_description  VARCHAR(255) NOT NULL DEFAULT '',     -- provider text, upper case

    -- Editorial --------------------------------------------------------------
    name             VARCHAR(255) NOT NULL,                -- "Laboratory Analytical Instruments"
    slug             VARCHAR(255) NOT NULL,                -- /sectors/laboratory-analytical-instruments
    primer           TEXT         NOT NULL DEFAULT '',     -- short intro for the hub page

    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS market_sector_slug_key
    ON market_sector (slug);

DROP TRIGGER IF EXISTS market_sector_set_updated_at ON market_sector;
CREATE TRIGGER market_sector_set_updated_at
    BEFORE UPDATE ON market_sector
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

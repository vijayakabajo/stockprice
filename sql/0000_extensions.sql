-- Extensions and shared helpers. Must run before any table file.

-- Trigram matching, for company-name search (see the GIN index on
-- market_stock.name). Without this, "appl" will not find "Apple Inc.".
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- Keeps updated_at honest for every writer, not just Django. Bulk COPY
-- during a backfill and a psql session both go through this.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

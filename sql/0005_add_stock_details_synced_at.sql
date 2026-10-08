-- market_stock.details_synced_at — when the profile (GET /v3/reference/tickers/{ticker})
-- was last fetched, whether or not Massive had anything to say.
--
-- The details sync used to pick rows by description = '', which never clears
-- for tickers Massive has no description for (many ETFs, warrants, units), so
-- they were re-fetched on every run. This column lets the sync process
-- never-fetched rows first and then refresh the oldest, on a rolling cycle.

ALTER TABLE market_stock
    ADD COLUMN IF NOT EXISTS details_synced_at TIMESTAMPTZ;

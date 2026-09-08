-- ============================================================
--  Unified Master Hub Schema — data/market.db (SQLite, WAL mode)
--  RECONSTRUCTED from every SQL query in the codebase because this
--  file was missing from the repository (fresh clones created no
--  tables and every query failed silently).
--  If you still have your original local schema.sql, diff it against
--  this one and keep whichever matches your live data.
-- ============================================================

PRAGMA journal_mode = WAL;

-- ------------------------------------------------------------
-- Canonical products: one row per real-world product across markets
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS canonical_products (
    canonical_key           TEXT PRIMARY KEY,
    title_fa                TEXT NOT NULL,
    brand                   TEXT NOT NULL DEFAULT 'other',
    category_key            TEXT NOT NULL DEFAULT 'digital',
    specs_json              TEXT DEFAULT '{}',
    digikala_price_toman    INTEGER DEFAULT 0,
    torob_min_price_toman   INTEGER DEFAULT 0,
    torob_shops_count       INTEGER DEFAULT 0,
    divar_avg_price_toman   INTEGER DEFAULT 0,
    divar_min_price_toman   INTEGER DEFAULT 0,
    esam_avg_price_toman    INTEGER DEFAULT 0,
    esam_min_price_toman    INTEGER DEFAULT 0,
    depreciation_percent    REAL DEFAULT 0,
    last_synced_at          TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_canonical_brand     ON canonical_products(brand);
CREATE INDEX IF NOT EXISTS idx_canonical_category  ON canonical_products(category_key);
CREATE INDEX IF NOT EXISTS idx_canonical_synced    ON canonical_products(last_synced_at);

-- ------------------------------------------------------------
-- Store listings: one row per observed listing/ad per store
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS store_listings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key     TEXT NOT NULL,
    store_key         TEXT NOT NULL,                 -- digikala | torob | divar | esam
    item_id           TEXT NOT NULL,
    title_fa          TEXT NOT NULL,
    price_toman       INTEGER NOT NULL DEFAULT 0,
    condition         TEXT DEFAULT '',
    is_auction        INTEGER DEFAULT 0,
    bids_count        INTEGER DEFAULT 0,
    seller_name       TEXT DEFAULT '',
    seller_score      TEXT DEFAULT '',
    warranty          TEXT DEFAULT '',
    location_district TEXT DEFAULT '',
    description       TEXT DEFAULT '',
    specs_json        TEXT DEFAULT '{}',
    rating_score      REAL DEFAULT 0,
    reviews_count     INTEGER DEFAULT 0,
    url               TEXT DEFAULT '',
    image_url         TEXT DEFAULT '',
    rrp_price_toman   INTEGER DEFAULT 0,
    observed_at       TEXT DEFAULT CURRENT_TIMESTAMP,
    -- purification columns (data_cleaner / agent audit loop)
    is_verified       INTEGER DEFAULT 0,
    quality_status    TEXT DEFAULT 'PENDING',
    rejection_reason  TEXT DEFAULT '',
    confidence_score  REAL DEFAULT 0,
    UNIQUE (store_key, item_id)
);
CREATE INDEX IF NOT EXISTS idx_listings_canonical   ON store_listings(canonical_key);
CREATE INDEX IF NOT EXISTS idx_listings_store       ON store_listings(store_key);
CREATE INDEX IF NOT EXISTS idx_listings_verified    ON store_listings(canonical_key, is_verified);
CREATE INDEX IF NOT EXISTS idx_listings_price       ON store_listings(price_toman);

-- ------------------------------------------------------------
-- Arbitrage opportunities (rebuilt on every scan)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key           TEXT NOT NULL,
    title_fa                TEXT DEFAULT '',
    source_store            TEXT NOT NULL,           -- divar | esam
    target_store            TEXT DEFAULT '',         -- torob | digikala
    buy_price_toman         INTEGER DEFAULT 0,
    market_ref_price_toman  INTEGER DEFAULT 0,
    profit_spread_toman     INTEGER DEFAULT 0,
    discount_percent        REAL DEFAULT 0,
    condition               TEXT DEFAULT '',
    deal_type               TEXT DEFAULT '',         -- GOLDEN_FLIP | SUPER_DEAL | UNDERVALUED
    item_url                TEXT DEFAULT '',
    image_url               TEXT DEFAULT '',
    seller_info             TEXT DEFAULT '',
    detected_at             TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_arb_canonical  ON arbitrage_opportunities(canonical_key);
CREATE INDEX IF NOT EXISTS idx_arb_type      ON arbitrage_opportunities(deal_type);
CREATE INDEX IF NOT EXISTS idx_arb_discount  ON arbitrage_opportunities(discount_percent);

-- ------------------------------------------------------------
-- Price history (append-only, feeds ML dataset & trend analysis)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS price_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_key  TEXT NOT NULL,
    store_key      TEXT NOT NULL,
    price_toman    INTEGER NOT NULL,
    condition      TEXT DEFAULT '',
    recorded_at    TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_history_canonical ON price_history(canonical_key, store_key);

-- ------------------------------------------------------------
-- Learned junk signals — patterns confirmed by the user
-- (each confirmed junk title teaches its leading word as a
--  permanent, free auto-reject pattern)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS learned_junk_signals (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    signal        TEXT UNIQUE NOT NULL,
    example_title TEXT DEFAULT '',
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    times_hit     INTEGER DEFAULT 0
);

-- ------------------------------------------------------------
-- AI review cache — one row per unique title, so each title is sent
-- to the LLM only once, ever. Re-runs of the pipeline reuse verdicts.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_review_cache (
    title_hash  TEXT PRIMARY KEY,
    title       TEXT,
    is_device   INTEGER NOT NULL,
    reason_fa   TEXT DEFAULT '',
    confidence  REAL DEFAULT 0,
    model       TEXT DEFAULT '',
    category    TEXT DEFAULT '',
    reviewed_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- Sync logs (orchestrator & streaming pull runs)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_logs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    source               TEXT DEFAULT '',
    items_synced         INTEGER DEFAULT 0,
    matches_found        INTEGER DEFAULT 0,
    opportunities_found  INTEGER DEFAULT 0,
    status               TEXT DEFAULT '',
    details              TEXT DEFAULT '',
    created_at           TEXT DEFAULT CURRENT_TIMESTAMP
);

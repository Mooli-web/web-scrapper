-- Dedicated CockroachDB Schema for Esam (esam.ir) Crawler & Market Intelligence
-- Isolated, independent database with zero foreign dependencies

CREATE TABLE IF NOT EXISTS esam_items (
    id SERIAL PRIMARY KEY,
    item_id VARCHAR(100) UNIQUE NOT NULL,
    title_fa TEXT NOT NULL,
    category_key VARCHAR(100) NOT NULL,
    category_name_fa VARCHAR(150),
    brand VARCHAR(150),
    condition VARCHAR(100) DEFAULT 'دست دوم',
    is_auction BOOLEAN DEFAULT FALSE,
    selling_price_toman BIGINT DEFAULT 0,
    base_price_toman BIGINT DEFAULT 0,
    buy_now_price_toman BIGINT DEFAULT 0,
    bids_count INT DEFAULT 0,
    time_remaining VARCHAR(100),
    seller_name VARCHAR(150),
    seller_score VARCHAR(50),
    seller_city VARCHAR(100),
    url TEXT NOT NULL,
    image_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    price_updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_esam_items_category ON esam_items(category_key);
CREATE INDEX IF NOT EXISTS idx_esam_items_price ON esam_items(selling_price_toman);
CREATE INDEX IF NOT EXISTS idx_esam_items_auction ON esam_items(is_auction);
CREATE INDEX IF NOT EXISTS idx_esam_items_condition ON esam_items(condition);
CREATE INDEX IF NOT EXISTS idx_esam_items_last_seen ON esam_items(last_seen_at);

CREATE TABLE IF NOT EXISTS esam_price_observations (
    id SERIAL PRIMARY KEY,
    item_id VARCHAR(100) NOT NULL REFERENCES esam_items(item_id) ON DELETE CASCADE,
    price_toman BIGINT NOT NULL,
    is_auction BOOLEAN DEFAULT FALSE,
    bids_count INT DEFAULT 0,
    observed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_esam_obs_item_time ON esam_price_observations(item_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS esam_price_events (
    id SERIAL PRIMARY KEY,
    item_id VARCHAR(100) NOT NULL REFERENCES esam_items(item_id) ON DELETE CASCADE,
    title_fa TEXT NOT NULL,
    event_type VARCHAR(50) NOT NULL, -- 'NEW_LISTING', 'PRICE_DROP', 'PRICE_HIKE', 'NEW_BID', 'AUCTION_HEATED'
    old_price_toman BIGINT,
    new_price_toman BIGINT,
    price_change_toman BIGINT,
    change_percent NUMERIC(6, 2),
    severity VARCHAR(20) DEFAULT 'INFO', -- 'INFO', 'WARNING', 'CRITICAL', 'GOLDEN'
    detected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_esam_events_detected ON esam_price_events(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_esam_events_severity ON esam_price_events(severity);

CREATE TABLE IF NOT EXISTS esam_categories (
    id SERIAL PRIMARY KEY,
    category_key VARCHAR(100) UNIQUE NOT NULL,
    title_fa VARCHAR(150) NOT NULL,
    category_code VARCHAR(50),
    query_slug VARCHAR(200),
    is_auction_feed BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    items_count INT DEFAULT 0,
    last_crawled_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS crawler_telemetry (
    key VARCHAR(50) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crawler_logs (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    category_key VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

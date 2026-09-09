-- ============================================================================
-- Multi-Store Market Intelligence Platform - Core Schema
-- 100% Optimized for CockroachDB Serverless & PostgreSQL
-- Zero Fake Data | Multi-Store Adapter Architecture | Delta-Only Price Ledger
-- ============================================================================

-- 1. STORES TABLE
CREATE TABLE IF NOT EXISTS stores (
    store_key VARCHAR(50) PRIMARY KEY,
    name_fa VARCHAR(100) NOT NULL,
    base_url TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. CATEGORIES TABLE
CREATE TABLE IF NOT EXISTS categories (
    category_key VARCHAR(100) PRIMARY KEY,
    title_fa VARCHAR(255) NOT NULL,
    parent_key VARCHAR(100) REFERENCES categories(category_key) ON DELETE SET NULL,
    depth INT NOT NULL DEFAULT 0,
    is_leaf BOOLEAN NOT NULL DEFAULT TRUE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    product_count INT NOT NULL DEFAULT 0,
    last_crawled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_categories_leaf ON categories(is_leaf, is_active);

-- 3. MASTER PRODUCTS CATALOG (Canonical Products across all stores)
CREATE TABLE IF NOT EXISTS master_products (
    product_id BIGINT PRIMARY KEY,
    title_fa TEXT NOT NULL,
    brand VARCHAR(150),
    category_key VARCHAR(100) REFERENCES categories(category_key) ON DELETE SET NULL,
    image_url TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_master_products_cat ON master_products(category_key);
CREATE INDEX IF NOT EXISTS idx_master_products_brand ON master_products(brand);

-- 4. STORE LISTINGS (Current live price and availability snapshot per store)
CREATE TABLE IF NOT EXISTS store_listings (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES master_products(product_id) ON DELETE CASCADE,
    store_key VARCHAR(50) NOT NULL REFERENCES stores(store_key) ON DELETE CASCADE,
    store_product_id VARCHAR(100) NOT NULL,
    selling_price_toman BIGINT NOT NULL DEFAULT 0,
    rrp_price_toman BIGINT NOT NULL DEFAULT 0,
    discount_percent NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    seller_name VARCHAR(255) NOT NULL DEFAULT 'فروشنده پیش‌فرض',
    available BOOLEAN NOT NULL DEFAULT TRUE,
    product_url TEXT NOT NULL,
    min_price_30d BIGINT DEFAULT 0,
    avg_price_30d BIGINT DEFAULT 0,
    last_updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_product_store UNIQUE (product_id, store_key)
);

CREATE INDEX IF NOT EXISTS idx_store_listings_prod ON store_listings(product_id);
CREATE INDEX IF NOT EXISTS idx_store_listings_price ON store_listings(selling_price_toman);
CREATE INDEX IF NOT EXISTS idx_store_listings_discount ON store_listings(discount_percent DESC);
CREATE INDEX IF NOT EXISTS idx_store_listings_avail ON store_listings(available);

-- 5. PRICE OBSERVATIONS (DELTA-ONLY LEDGER: Inserted STRICTLY when price/stock changes)
CREATE TABLE IF NOT EXISTS price_observations (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES master_products(product_id) ON DELETE CASCADE,
    store_key VARCHAR(50) NOT NULL REFERENCES stores(store_key) ON DELETE CASCADE,
    selling_price_toman BIGINT NOT NULL,
    rrp_price_toman BIGINT NOT NULL,
    discount_percent NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    seller_name VARCHAR(255),
    available BOOLEAN NOT NULL DEFAULT TRUE,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_price_obs_prod ON price_observations(product_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_obs_time ON price_observations(observed_at DESC);

-- 6. PRICE EVENTS (Recorded drops and alerts)
CREATE TABLE IF NOT EXISTS price_events (
    id BIGSERIAL PRIMARY KEY,
    product_id BIGINT NOT NULL REFERENCES master_products(product_id) ON DELETE CASCADE,
    store_key VARCHAR(50) NOT NULL REFERENCES stores(store_key) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL DEFAULT 'price_drop', -- 'price_drop', 'price_spike', 'back_in_stock', 'out_of_stock'
    old_price_toman BIGINT NOT NULL,
    new_price_toman BIGINT NOT NULL,
    drop_percent NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    real_drop_percent_30d NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    baseline_avg_price BIGINT NOT NULL DEFAULT 0,
    severity VARCHAR(20) NOT NULL DEFAULT 'low',
    is_lowest_30d BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_price_events_created ON price_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_events_prod ON price_events(product_id);

-- 7. CRAWL LOGS & AUDIT TRAIL
CREATE TABLE IF NOT EXISTS crawl_logs (
    id BIGSERIAL PRIMARY KEY,
    log_level VARCHAR(20) NOT NULL DEFAULT 'INFO',
    module VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    context_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crawl_logs_created ON crawl_logs(created_at DESC);

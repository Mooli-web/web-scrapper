-- ============================================================================
-- Divar Cloud Database Schema (CockroachDB Serverless & PostgreSQL)
-- 100% Independent Schema for Divar 24/7 Crawler Engine
-- ============================================================================

-- 1. CATEGORIES
CREATE TABLE IF NOT EXISTS divar_categories (
    category_key VARCHAR(150) PRIMARY KEY,
    slug VARCHAR(150) NOT NULL,
    title_fa VARCHAR(255) NOT NULL,
    query_text VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    post_count INT NOT NULL DEFAULT 0,
    last_crawled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. DIVAR POSTS (Live snapshot of current active ads)
CREATE TABLE IF NOT EXISTS divar_posts (
    token VARCHAR(255) PRIMARY KEY,
    title_fa TEXT NOT NULL,
    brand VARCHAR(150) NOT NULL DEFAULT 'متفرقه',
    category_key VARCHAR(150) REFERENCES divar_categories(category_key) ON DELETE SET NULL,
    selling_price_toman BIGINT NOT NULL DEFAULT 0,
    condition VARCHAR(100) NOT NULL DEFAULT 'کارکرده',
    city VARCHAR(100) NOT NULL DEFAULT 'تهران',
    district TEXT,
    image_url TEXT,
    post_url TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_divar_posts_cat ON divar_posts(category_key);
CREATE INDEX IF NOT EXISTS idx_divar_posts_price ON divar_posts(selling_price_toman);
CREATE INDEX IF NOT EXISTS idx_divar_posts_city ON divar_posts(city);
CREATE INDEX IF NOT EXISTS idx_divar_posts_condition ON divar_posts(condition);
CREATE INDEX IF NOT EXISTS idx_divar_posts_seen ON divar_posts(last_seen_at DESC);

-- 3. PRICE OBSERVATIONS (Delta-only historical price log)
CREATE TABLE IF NOT EXISTS divar_price_observations (
    id BIGSERIAL PRIMARY KEY,
    token VARCHAR(255) NOT NULL REFERENCES divar_posts(token) ON DELETE CASCADE,
    selling_price_toman BIGINT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_divar_obs_token ON divar_price_observations(token, observed_at DESC);

-- 4. PRICE EVENTS (Price drop alarms & flippings)
CREATE TABLE IF NOT EXISTS divar_price_events (
    id BIGSERIAL PRIMARY KEY,
    token VARCHAR(255) NOT NULL REFERENCES divar_posts(token) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL DEFAULT 'price_drop',
    old_price_toman BIGINT NOT NULL,
    new_price_toman BIGINT NOT NULL,
    drop_percent NUMERIC(5, 2) NOT NULL DEFAULT 0.0,
    severity VARCHAR(20) NOT NULL DEFAULT 'low',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_divar_events_created ON divar_price_events(created_at DESC);

-- 5. CRAWL LOGS
CREATE TABLE IF NOT EXISTS divar_crawl_logs (
    id BIGSERIAL PRIMARY KEY,
    log_level VARCHAR(20) NOT NULL DEFAULT 'INFO',
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

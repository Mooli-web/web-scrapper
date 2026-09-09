-- ============================================================================
-- Clean, High-Yield Divar Category Slugs & Queries
-- ============================================================================

INSERT INTO divar_categories (category_key, slug, title_fa, query_text, is_active)
VALUES
('mobile-phones', 'mobile-phones', 'همه گوشی‌های موبایل', '', TRUE),
('mobile-apple', 'mobile-phones', 'گوشی‌های اپل (iPhone)', 'آیفون', TRUE),
('mobile-samsung', 'mobile-phones', 'گوشی‌های سامسونگ (Galaxy)', 'سامسونگ', TRUE),
('mobile-xiaomi', 'mobile-phones', 'گوشی‌های شیائومی (Poco / Redmi)', 'شیائومی', TRUE),
('laptops', 'laptops', 'همه لپ‌تاپ‌ها و رایانه‌ها', '', TRUE),
('laptops-apple', 'laptops', 'مک‌بوک‌های اپل (MacBook)', 'مک بوک', TRUE),
('laptops-gaming', 'laptops', 'لپ‌تاپ‌های گیمینگ', 'گیمینگ', TRUE),
('gaming-consoles', 'game-consoles', 'کنسول‌های بازی (PS5 / Xbox)', 'ps5', TRUE),
('gaming-ps4', 'game-consoles', 'کنسول‌های پلی‌استیشن ۴', 'ps4', TRUE),
('graphic-cards', 'electronic-devices', 'کارت‌های گرافیک (GPU)', 'کارت گرافیک', TRUE),
('processors', 'electronic-devices', 'پردازنده‌ها (CPU)', 'پردازنده', TRUE),
('smart-watches', 'smart-watch', 'ساعت و مچ‌بند هوشمند', '', TRUE),
('headphones', 'headphone', 'هدفون و هندزفری', '', TRUE),
('tablets', 'tablet', 'تبلت و کتابخوان', '', TRUE)
ON CONFLICT (category_key) DO UPDATE 
SET title_fa = EXCLUDED.title_fa,
    slug = EXCLUDED.slug,
    query_text = EXCLUDED.query_text,
    is_active = EXCLUDED.is_active;

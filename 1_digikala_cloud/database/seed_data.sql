-- ============================================================================
-- Seed Digikala Store & Digital Categories
-- ============================================================================

-- 1. STORE
INSERT INTO stores (store_key, name_fa, base_url, is_active)
VALUES
('digikala', 'دیجی‌کالا (کالای نو)', 'https://www.digikala.com', TRUE)
ON CONFLICT (store_key) DO UPDATE SET is_active = EXCLUDED.is_active;

-- 2. CATEGORIES
INSERT INTO categories (category_key, title_fa, parent_key, depth, is_leaf, is_active)
VALUES
('electronic-devices', 'کالای دیجیتال', NULL, 0, FALSE, TRUE),
('mobile-phone', 'گوشی موبایل', 'electronic-devices', 1, FALSE, TRUE),
('laptops', 'لپ‌تاپ و الترابوک', 'electronic-devices', 1, FALSE, TRUE),
('headphones', 'هدفون و هندزفری', 'electronic-devices', 1, TRUE, TRUE),
('smart-watches', 'ساعت و مچ‌بند هوشمند', 'electronic-devices', 1, TRUE, TRUE),
('gaming-consoles', 'کنسول بازی و لوازم', 'electronic-devices', 1, FALSE, TRUE),
('storage-devices', 'حافظه و ذخیره‌سازی (SSD/HDD)', 'electronic-devices', 1, TRUE, TRUE),
('tablets', 'تبلت و کتابخوان', 'electronic-devices', 1, TRUE, TRUE),
('computer-components', 'قطعات کامپیوتر (CPU/GPU/RAM)', 'electronic-devices', 1, FALSE, TRUE),

-- Sub-branches
('mobile-apple', 'گوشی‌های اپل (iPhone)', 'mobile-phone', 2, TRUE, TRUE),
('mobile-samsung', 'گوشی‌های سامسونگ (Galaxy)', 'mobile-phone', 2, TRUE, TRUE),
('mobile-xiaomi', 'گوشی‌های شیائومی و پوکو', 'mobile-phone', 2, TRUE, TRUE),
('laptop-asus', 'لپ‌تاپ‌های ایسوس (ASUS ROG/TUF)', 'laptops', 2, TRUE, TRUE),
('laptop-apple', 'مک‌بوک‌های اپل (MacBook Pro/Air)', 'laptops', 2, TRUE, TRUE),
('laptop-lenovo', 'لپ‌تاپ‌های لنوو (Lenovo)', 'laptops', 2, TRUE, TRUE),
('gaming-playstation', 'پلی‌استیشن ۵ (PS5)', 'gaming-consoles', 2, TRUE, TRUE),
('gaming-xbox', 'ایکس‌باکس (Xbox Series)', 'gaming-consoles', 2, TRUE, TRUE),
('graphic-cards', 'کارت گرافیک (GPU)', 'computer-components', 2, TRUE, TRUE),
('processors', 'پردازنده (CPU)', 'computer-components', 2, TRUE, TRUE)
ON CONFLICT (category_key) DO UPDATE 
SET title_fa = EXCLUDED.title_fa,
    parent_key = EXCLUDED.parent_key,
    depth = EXCLUDED.depth,
    is_leaf = EXCLUDED.is_leaf,
    is_active = EXCLUDED.is_active;

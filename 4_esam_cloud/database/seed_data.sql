-- Initial Tracked Categories and Auction Feeds for Esam.ir

INSERT INTO esam_categories (category_key, title_fa, category_code, query_slug, is_auction_feed, is_active)
VALUES
  -- 1. مزایدات داغ و رو به پایان
  ('auctions_ending', 'مزایدات رو به اتمام (فرصت خرید فوری)', 'auctions', 'auctions?activeTab=TowardTheEnd', TRUE, TRUE),
  ('auctions_hot', 'مزایدات دارای پیشنهاد داغ', 'auctions', 'auctions?activeTab=HasBid', TRUE, TRUE),

  -- 2. لپ‌تاپ و کامپیوتر (cc=40000)
  ('laptop', 'لپ‌تاپ و نوت‌بوک (نو، استوک و کارکرده)', '40100', 'search/laptop?cc=40100', FALSE, TRUE),
  ('gpu', 'کارت گرافیک (GPU)', '40201', 'search/graphic-card?cc=40201', FALSE, TRUE),
  ('cpu', 'پردازنده کامپیوتر (CPU)', '40202', 'search/cpu?cc=40202', FALSE, TRUE),
  ('ram', 'حافظه رم کامپیوتر و لپ‌تاپ (RAM)', '40203', 'search/ram?cc=40203', FALSE, TRUE),
  ('motherboard', 'مادربرد (Motherboard)', '40204', 'search/motherboard?cc=40204', FALSE, TRUE),
  ('ssd_hdd', 'هارد و حافظه SSD', '40206', 'search/storage?cc=40206', FALSE, TRUE),
  ('monitor', 'مانیتور و نمایشگر', '40300', 'search/monitor?cc=40300', FALSE, TRUE),

  -- 3. موبایل و تبلت (cc=30000)
  ('mobile_apple', 'گوشی موبایل اپل (آیفون استوک و نو)', '30101', 'search/apple-iphone?cc=30101', FALSE, TRUE),
  ('mobile_samsung', 'گوشی موبایل سامسونگ (Samsung)', '30102', 'search/samsung-mobile?cc=30102', FALSE, TRUE),
  ('mobile_xiaomi', 'گوشی موبایل شیائومی (Xiaomi)', '30103', 'search/xiaomi-mobile?cc=30103', FALSE, TRUE),
  ('tablet', 'تبلت و کتابخوان الکترونیکی', '30500', 'search/tablet?cc=30500', FALSE, TRUE),
  ('smartwatch', 'ساعت هوشمند و مچ‌بند', '30700', 'search/smartwatch?cc=30700', FALSE, TRUE),

  -- 4. کنسول‌های بازی (cc=50000)
  ('console_ps5_ps4', 'کنسول بازی پلی‌استیشن (PS5 / PS4)', '50100', 'search/playstation?cc=50100', FALSE, TRUE),
  ('console_xbox', 'کنسول بازی ایکس‌باکس (Xbox Series / One)', '50200', 'search/xbox?cc=50200', FALSE, TRUE),
  ('console_nintendo', 'کنسول بازی نینتندو (Nintendo Switch)', '50300', 'search/nintendo?cc=50300', FALSE, TRUE),

  -- 5. صوتی و تصویری (cc=60000)
  ('headphones', 'هدفون، هندزفری و هدست گیمینگ', '60100', 'search/headphones?cc=60100', FALSE, TRUE),

  -- 6. نوستالژی و کلکسیونی (cc=90000)
  ('vintage_mobile', 'گوشی‌های کلکسیونی و قدیمی (نوکیا / سونی اریکسون)', '93401', 'search/vintage-mobile?cc=93401', FALSE, TRUE)
ON CONFLICT (category_key) DO UPDATE SET
  title_fa = EXCLUDED.title_fa,
  category_code = EXCLUDED.category_code,
  query_slug = EXCLUDED.query_slug,
  is_auction_feed = EXCLUDED.is_auction_feed;

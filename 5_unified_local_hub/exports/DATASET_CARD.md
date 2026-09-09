# 🎓 کارت دیتاست بازار چهارگانه (Quad-Market Dataset Card)

> تولید خودکار توسط `export_training_bundle.py` در 2026-09-09T13:46:24
> منبع: `market.db` (212.2MB)

## ۱) ماهیت داده
آگهی‌ها و قیمت‌های چهار بازار کالای دیجیتال ایران: دیجی‌کالا، ترب، دیوار و ایسام؛
گردآوری‌شده توسط خزنده‌های مستقل و تجمیع‌شده در هاب لوکال. سه وظیفه‌ی یادگیری:

1. **دسته‌بندی** (۱۴ دسته): `title`+`description` → `category_std`
2. **کیفیت/چرت**: `title`+`description`+`price` → `clean | junk` (+ دلیل)
3. **پیش‌بینی قیمت/آربیتراژ**: ویژگی‌های جدولی → قیمت مرجع و درصد تخفیف

## ۲) فایل‌ها

| فایل | ردیف | حجم | نقش |
|---|---:|---:|---|
| `canonical_products.jsonl` | 11,135 | 5.7MB | محصول کانونیکال + دسته و قیمت مرجع هر بازار |
| `category_history.jsonl` | 1,391 | 325.8KB | اصلاحات انسانی X→Y — گران‌بهاترین بخش (hard examples) |
| `learned_junk_signals.jsonl` | 235 | 55.4KB | الگوهای چرت تأییدشده (weak supervision) |
| `ai_review_cache.jsonl` | 7,739 | 2.2MB | قضاوت LLM با confidence (داده‌ی تقطیر/distillation) |
| `listings.jsonl` | 20,345 | 13.4MB | نمونه‌های خام با برچسب کیفیت (هسته‌ی هر سه وظیفه) |
| `price_summary.csv` | 11,798 | 1.1MB | آمار قیمت به تفکیک محصول×سایت |
| `price_history_sample.csv` | 10,050 | 638.3KB | نمونه‌ی یکنواخت ردیف‌های خام تاریخچه |

## ۳) برچسب‌ها و منبع آن‌ها

`label_source` در فایل‌های `ml_training/` یکی از این سه است و باید وزن‌دهی شود:

- `human` / `manual` — تأیید ✋، حذف 🗑 یا تغییر دسته 🗂 توسط انسان (قابل‌اعتمادترین)
- `ai` — قضاوت مدل زبانی (Groq) با `confidence`
- `rule` — قاعده‌ی Regex/قیمتی در `core/data_cleaner.py` (پرخطاترین)

### توزیع آگهی‌ها بر حسب سایت و وضعیت کیفیت

| سایت/وضعیت | تعداد |
|---|---:|
| `digikala/VERIFIED` | 6,870 |
| `divar/VERIFIED` | 4,187 |
| `esam/AI_REJECTED` | 2,521 |
| `torob/VERIFIED` | 2,330 |
| `divar/ACCESSORY_OR_JUNK` | 784 |
| `divar/CONFIRMED_JUNK` | 668 |
| `esam/FAKE_PRICE` | 656 |
| `esam/VERIFIED` | 634 |
| `esam/ACCESSORY_OR_JUNK` | 457 |
| `torob/ACCESSORY_OR_JUNK` | 377 |
| `digikala/ACCESSORY_OR_JUNK` | 322 |
| `divar/FAKE_PRICE` | 210 |
| `divar/AI_REJECTED` | 204 |
| `torob/CONFIRMED_JUNK` | 42 |
| `esam/CONFIRMED_JUNK` | 38 |
| `digikala/AI_REJECTED` | 27 |
| `divar/DEFECTIVE_PARTS` | 8 |
| `esam/DEFECTIVE_PARTS` | 7 |
| `digikala/CONFIRMED_JUNK` | 2 |
| `torob/FAKE_PRICE` | 1 |

### توزیع محصولات بر حسب منبع دسته‌بندی

| منبع | تعداد |
|---|---:|
| `rule` | 8,984 |
| `manual` | 1,129 |
| `ai` | 1,022 |

### توزیع محصولات بر حسب دسته‌ی استاندارد

| دسته | تعداد |
|---|---:|
| `other` | 2,491 |
| `mobile` | 1,798 |
| `headphone` | 1,620 |
| `watch` | 1,391 |
| `laptop` | 1,302 |
| `storage` | 822 |
| `tablet` | 358 |
| `cpu` | 288 |
| `desktop-pc` | 254 |
| `console` | 253 |
| `ram` | 191 |
| `gpu` | 139 |
| `motherboard` | 134 |
| `monitor` | 94 |

## ۴) حریم شخصی
- ستون‌های `seller_name`, `location_district`, `url`, `image_url` صادر نمی‌شوند.
- در متن `title_fa`/`description`: شماره‌موبایل → `<PHONE>`، ایمیل → `<EMAIL>`،
  لینک → `<URL>`، و الگوی کد ملی/شبا → `<ID>`.
- فایل `.env` (کلیدهای Groq) هیچ‌وقت خوانده یا صادر نمی‌شود.

## ۵) شکاف‌های شناخته‌شده (قبل از آموزش بخوانید)
- **تکراری/نشتی:** عنوان‌های نزدیک بین آگهی‌ها تکرار می‌شوند؛ قبل از split باید بر اساس
  `canonical_key` گروه‌بندی شود (GroupKFold) وگرنه آزمون خوش‌بینانه می‌شود.
- **پوشش توضیحات:** بخشی از آگهی‌ها `description` خالی دارند؛ مدل نباید به آن وابسته شود.
- **نام‌بالانس:** `other` و `mobile` بزرگ‌اند و `monitor`/`motherboard` کوچک → وزن‌دهی لازم است.
- **برچسب `rule`:** بخش بزرگی از دسته‌ها قاعده‌ای است؛ برای ارزیابی فقط از `human`/`manual`
  به‌عنوان مجموعه‌ی طلایی استفاده کنید.
- **زمان:** `price_history` بازه‌ی کوتاهی دارد؛ برای پیش‌بینی سری زمانی کافی نیست.

## ۶) split پیشنهادی
- `train` ۸۰٪ / `valid` ۱۰٪ / `test` ۱۰٪ **به تفکیک `canonical_key`** (نه ردیف).
- مجموعه‌ی طلایی تست: فقط ردیف‌هایی با `label_source in (human, manual)`.

## ۷) بازتولید
```bash
cd 5_unified_local_hub
python export_training_bundle.py      # این بسته + همین کارت
python export_training_data.py       # ml_training/*.jsonl
python pre_training_audit.py         # کارنامه‌ی آمادگی
```

## ۸) اثرانگشت فایل‌ها

| فایل | sha256 (۱۲ نویسه) |
|---|---|
| `canonical_products.jsonl` | `5b91c04377c3` |
| `category_history.jsonl` | `b258fe0d9c93` |
| `learned_junk_signals.jsonl` | `377506079bbf` |
| `ai_review_cache.jsonl` | `477c58631a53` |
| `listings.jsonl` | `96c6256d2a10` |
| `price_summary.csv` | `27be4c538884` |
| `price_history_sample.csv` | `1b4e94e2b149` |

مجموع بسته: **23.4MB**

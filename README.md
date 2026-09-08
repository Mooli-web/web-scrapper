# 🔄 کیت نصب رله Groq روی Render — راه قطعی عبور از 403

## این رله چیست و چرا مشکل را حل می‌کند؟

```
[بدون رله — وضعیت الان]
  کامپیوتر تو (ایران/IP بن‌شده) ──❌ 403──▶ api.groq.com

[با رله]
  کامپیوتر تو ──▶ سرور Render تو (آمریکا، IP سالم) ──▶ api.groq.com ✅
                 (این مسیر از قبل باز است — همون جایی که خزنده‌ها باهاش کار می‌کنند)
```

سرورهای Render از IP آمریکا باقی می‌مانند و Groq آن‌ها را نمی‌بلاکد.
کلید Groq فقط از کامپیوتر تو پاس داده می‌شود؛ روی Render ذخیره نمی‌شود.

---

## 📦 محتویات این کیت (۴ فایل)

| فایل در این کیت | مقصد در مخزن تو |
|---|---|
| `server/ai_relay.py` | در **هر سه** پوشه: `1_digikala_cloud/server/` و `2_divar_cloud/server/` و `4_esam_cloud/server/` (یک فایل مشترک، سه نسخه یکسان) |
| `1_digikala_cloud/server/app.py` | جایگزین `1_digikala_cloud/server/app.py` |
| `2_divar_cloud/server/app.py` | جایگزین `2_divar_cloud/server/app.py` |
| `4_esam_cloud/server/app.py` | جایگزین `4_esam_cloud/server/app.py` |

⚠️ فایل‌های `app.py` فقط **دو خط** اضافه دارند (import و ثبت روتر رله).
اگر نسخه محلی‌ات با گیت‌هاب فرق دارد، به‌جای جایگزینی کل فایل این دو خط را دستی اضافه کن:

```python
# بعد از خط: from server.routes import router ...
from server.ai_relay import router as ai_relay_router  # NEW: Groq relay for local hub

# بعد از خط: app.include_router(router)
app.include_router(ai_relay_router)  # NEW: /ai-relay/v1/* forwards to Groq
```

---

## 🚀 مراحل نصب (۱۰ دقیقه)

### قدم ۱ — کپی فایل‌ها
چهار فایل را از این کیت در مسیرهای جدول بالا داخل **مخزن محلی** خودت کپی کن
(همان پوشه‌ای که `5_unified_local_hub` در آن است).

### قدم ۲ — کامیت و پوش
```bash
cd web-scrapper
git add 1_digikala_cloud/server/ai_relay.py 1_digikala_cloud/server/app.py
git add 2_divar_cloud/server/ai_relay.py 2_divar_cloud/server/app.py
git add 4_esam_cloud/server/ai_relay.py 4_esam_cloud/server/app.py
git commit -m "feat: Groq AI relay endpoint for local hub (bypass regional block)"
git push origin main
```

### قدم ۳ — صبر برای دیپلوی Render
- Render معمولاً خودش ظرف ۲ تا ۵ دقیقه دیپلوی می‌کند.
- برای مطمئن شدن: dashboard.render.com → سرویس → تب **Events** → صبر کن وضعیت
  آخرین commit شود **Deploy succeeded** (یا **Live**).

### قدم ۴ — تست سلامت رله در مرورگر
یکی از این آدرس‌ها را باز کن (هر کدام که دیپلوی شده):

- دیجی‌کالا: `https://dcp-s1y4.onrender.com/ai-relay/v1/health`
- دیوار: `https://wall-crawler.onrender.com/ai-relay/v1/health`
- ایسام: `https://ec-fjpk.onrender.com/ai-relay/v1/health`

باید این JSON را ببینی:
```json
{"status": "ok", "service": "groq-relay", "upstream": "https://api.groq.com/openai"}
```
اگر صفحه لودکن شد و جواب آمد، رله زنده است ✅ (اولین بازکردن تا ~۱ دقیقه طول
می‌کشد چون سرویس رایگان از خواب بیدار می‌شود.)

### قدم ۵ — تنظیم هاب
فایل `.env` هاب را باز کن و این خط را اضافه کن (کلید Groq سر جایش می‌ماند):

```
GROQ_API_KEY=gsk_همان_کلید_قبلی
GROQ_BASE_URL=https://dcp-s1y4.onrender.com/ai-relay/v1
```

(به‌جای dcp-s1y4 همان سرویسی را بگذار که در قدم ۴ جواب داد.)

### قدم ۶ — ری‌استارت هاب و تست نهایی
هاب را ببند و `run_windows.bat` را دوباره اجرا کن، بعد در CMD داخل پوشه هاب:

```bash
python groq_diagnostic.py --relay https://dcp-s1y4.onrender.com/ai-relay/v1
```

انتظار: `GET /models [رله ...] PASS ✅` و `POST /chat PASS ✅`

### قدم ۷ — خالی کردن صف بازبینی (۶,۱۰۷ آگهی)
در داشبورد → تب کیفیت → دکمه بنفش «🤖 بازبینی هوشمند» را چند بار بزن،
یا یک‌جا با PowerShell (هر خط = ۲,۵۰۰ آگهی):

```powershell
curl.exe -X POST http://localhost:7000/api/audit/ai-review -H "Content-Type: application/json" -d "{\"max_batches\": 50, \"batch_size\": 50}"
```

---

## ❓ سوالات متداول

**باید VPN یا Proxifier روشن باشد؟**
نه! بعد از این کار هیچ VPN لازم نیست — درخواست‌ها از Render خارج می‌شوند.
قانون python.exe در Proxifier را هم می‌توانی حذف کنی.

**هزینه دارد؟** رله فقط یک پاس‌دهنده است؛ توکن‌ها همان مصرف خودِ Groq است.

**اولین درخواست کند است؟** بله، تا ~۱ دقیقه (بیدار شدن سرویس رایگان Render).
timeout هاب را برای همین ۱۲۰ ثانیه گذاشته‌ایم. دفعه‌های بعد سریع است.

**امنیت؟** رله کلید را ذخیره نمی‌کند؛ فقط درخواست‌هایی با هدر
`Authorization: Bearer gsk_...` را پاس می‌دهد (کلید غلط را خود Groq رد می‌کند).

**اگر باز هم 403 داد؟** یعنی کلید گروی تو خودش بن شده:
با مرورگر (Windscribe روشن) وارد console.groq.com شو، کلید جدید بساز،
فقط `GROQ_API_KEY` را در `.env` عوض کن — رله دست نمی‌خورد.

**همه سه سرویس را باید آپدیت کنم؟** نه، یکی کافی است؛ ولی چون فایل مشترک است
ضرری ندارد هر سه را آپدیت کنی تا هر وقت یکی خواب بود از دیگری استفاده کنی
(فقط GROQ_BASE_URL را عوض کن).

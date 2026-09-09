# 🚀 راهنمای گام‌به‌گام راه‌اندازی از صفر مطلق (Zero to Production)
### سامانه هوش و مانیتورینگ بازار دیجیتال

این راهنما برای زمانی است که **هیچ حساب کاربری، ریپازیتوری یا دیتابیسی از قبل وجود ندارد** و می‌خواهید پروژه را از نقطه صفر راه‌اندازی کنید.

---

## 📑 فهرست مراحل:
1. [ساخت پایگاه داده رایگان CockroachDB](#-مرحله-۱-ساخت-پایگاه-داده-رایگان-cockroachdb)
2. [ساخت ریپازیتوری GitHub و آپلود کدها](#-مرحله-۲-ساخت-ریپازیتوری-github-و-آپلود-کدها)
3. [استقرار خودکار روی سرور ابری Render](#-مرحله-۳-استقرار-خودکار-روی-سرور-ابری-render)
4. [اجرای کلاینت محلی ویندوز برای ترب](#-مرحله-۴-اجرای-کلاینت-محلی-ویندوز-برای-ترب)

---

### 🗄️ مرحله ۱: ساخت پایگاه داده رایگان CockroachDB

1. به وب‌سایت [cockroachlabs.cloud](https://cockroachlabs.cloud) مراجعه کرده و ثبت‌نام کنید.
2. روی دکمه **Create Cluster** کلیک کنید:
   * پلن را روی **Serverless (Free)** بگذارید.
   * منطقه دیتاسنتر را **GCP / Frankfurt (europe-west3)** یا نزدیک‌ترین منطقه انتخاب کنید.
   * نام کلاستر را بگذارید و **Create** را بزنید.
3. در پنجره تولید رمز، روی **Generate Password** کلیک کنید و رشته اتصال دیتابیس را بردارید:
   ```text
   postgresql://mahdi:PASS@cluster-name.cockroachlabs.cloud:26257/defaultdb?sslmode=require
   ```
4. در منوی سمت چپ پنل CockroachDB، وارد **SQL Shell** شوید:
   * اسکریپت `database/schema.sql` را کپی کرده و Run کنید.
   * اسکریپت `database/seed_data.sql` را کپی کرده و Run کنید.

---

### 📦 مرحله ۲: ساخت ریپازیتوری GitHub و آپلود کدها

1. وارد [github.com](https://github.com) شوید و یک ریپازیتوری جدید با نام `market-intelligence-engine` بسازید.
2. در ترمینال سیستم خود داخل پوشه پروژه دستورات زیر را اجرا کنید:

```bash
git init
git config user.name "Your Name"
git config user.email "your-email@example.com"
git add .
git commit -m "feat: complete market intelligence engine with digikala, divar and torob"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/market-intelligence-engine.git
git push -u origin main --force
```

---

### 🌐 مرحله ۳: استقرار خودکار روی سرور ابری Render

1. به سایت [render.com](https://render.com) رفته و با اکانت GitHub لاگین کنید.
2. از بالای صفحه **New +** $\rightarrow$ **Web Service** را انتخاب کرده و ریپازیتوری `market-intelligence-engine` را Connect کنید.
3. تنظیمات زیر را وارد نمایید:
   * **Language:** `Python 3`
   * **Region:** `Frankfurt (EU Central)`
   * **Build Command:**
     ```bash
     pip install -r requirements.txt && cd dashboard && npm install && npm run build && cd ..
     ```
   * **Start Command:**
     ```bash
     python -m uvicorn server.app:app --host 0.0.0.0 --port $PORT
     ```
   * **Plan:** `Free`
4. در بخش **Environment Variables** متغیرهای زیر را ذخیره کنید:
   * `DATABASE_URL` = (رشته اتصال CockroachDB از مرحله ۱)
   * `DASHBOARD_ADMIN_USER` = `admin`
   * `DASHBOARD_ADMIN_PASS` = `admin123`
   * `CRAWLER_DELAY_SEC` = `1.8`
   * `ENABLE_INTERNAL_SCHEDULER` = `true`
5. روی **Create Web Service** کلیک کنید. پس از ۳ دقیقه آدرس وب‌سرویس فعال می‌شود (مثلاً `https://market-engine.onrender.com`).

---

### 💻 مرحله ۴: اجرای کلاینت محلی ویندوز برای ترب

1. پوشه `local_agent` را باز کنید.
2. روی فایل `run_windows.bat` دو بار کلیک کنید.
3. داشبورد محلی در آدرس `http://localhost:5000` باز شده و خزش کاتالوگ ترب را آغاز می‌کند.

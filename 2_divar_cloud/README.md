# 📱 سامانه ابری مستقل پایش پیوسته دیوار (Divar Cloud Crawler)
### پلتفرم پایش ۲۴/۷ آگهی‌های کارکرده، در حد نو و استوک دیجیتال روی Render و CockroachDB

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.13-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React%2018-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![CockroachDB](https://img.shields.io/badge/CockroachDB-Serverless-6933FF?style=for-the-badge&logo=cockroachlabs&logoColor=white)
![Render](https://img.shields.io/badge/Render-Web%20Service-46E3B7?style=for-the-badge&logo=render&logoColor=black)

---

## 🎯 معرفی پروژه
این پروژه یک وب‌سرویس و داشبورد کاملاً مستقل و اختصاصی برای **پایش ۲۴ ساعته آگهی‌های دیجیتال دیوار** است که روی سرور ابری **Render** اجرا شده و مستقیماً داده‌های استخراج‌شده را در دیتابیس اختصاصی خود در **CockroachDB Serverless** ذخیره می‌کند.

---

## 🚀 راهنمای راه‌اندازی از صفر در Render و CockroachDB:

### ۱. ساخت دیتابیس اختصاصی دیوار در CockroachDB (رایگان):
1. در [cockroachlabs.cloud](https://cockroachlabs.cloud) یک کلاستر جدید رایگان به نام `divar-db` بسازید.
2. رشته اتصال تولیدشده را کپی کنید:
   ```text
   postgresql://USER:PASSWORD@host.cockroachlabs.cloud:26257/defaultdb?sslmode=require
   ```
3. در بخش **SQL Shell**، محتوای فایل `database/schema.sql` و سپس `database/seed_data.sql` را اجرا کنید تا جداول اختصاصی دیوار ساخته شوند.

### ۲. استقرار وب‌سرویس دیوار در Render:
1. این پوشه را به عنوان یک ریپازیتوری مستقل در GitHub پوش کنید.
2. در [render.com](https://render.com) یک **Web Service** جدید بسازید و ریپازیتوری را متصل کنید.
3. تنظیمات را قرار دهید:
   * **Build Command:**
     ```bash
     pip install -r requirements.txt && cd dashboard && npm install && npm run build && cd ..
     ```
   * **Start Command:**
     ```bash
     python -m uvicorn server.app:app --host 0.0.0.0 --port $PORT
     ```
   * **Environment Variables:**
     * `DATABASE_URL` = رشته اتصال دیتابیس CockroachDB اختصاصی دیوار
     * `DASHBOARD_ADMIN_USER` = `admin`
     * `DASHBOARD_ADMIN_PASS` = `admin123`
     * `ENABLE_INTERNAL_SCHEDULER` = `true`

---

## 💻 دستورات CLI:
```bash
# ساخت جداول در دیتابیس CockroachDB
python -m crawler.cli init-db

# تست اتصال زنده به دیتابیس CockroachDB
python -m crawler.cli test-db

# تست اتصال به API دیوار
python -m crawler.cli test-divar

# اجرای مستقیم خزش ۲۴ ساعته دیوار
python -m crawler.cli crawl
```

# -*- coding: utf-8 -*-
"""
📦 بسته‌ی قابل push برای آموزش AI — export_training_bundle.py
=============================================================
از دیتابیس لوکال (data/market.db) یک بسته‌ی «کوچک، بدون اطلاعات شخصی و
قابل commit» می‌سازد تا بدون ارسال دیتابیس ۲۱۲ مگابایتی، همه‌ی چیزی که
برای ساخت/ارزیابی مدل لازم است در گیت قرار بگیرد.

خروجی در exports/training_bundle/ :
    MANIFEST.json              تعداد ردیف‌ها + sha256 هر فایل + انگشت DB
    canonical_products.jsonl   همه‌ی محصولات کانونیکال (بدون PII)
    category_history.jsonl     همه‌ی اصلاحات انسانی X→Y (طلای آموزش)
    learned_junk_signals.jsonl الگوهای چرتِ تأییدشده
    ai_review_cache.jsonl      قضاوت‌های کش‌شده‌ی LLM (داده‌ی تقطیر)
    listings.jsonl             آگهی‌ها (عنوان/توضیح/قیمت/وضعیت کیفیت) — PII پاک شده
    price_summary.csv          خلاصه‌ی قیمت به تفکیک محصول×سایت
    price_history_sample.csv   نمونه‌ی یکنواخت از ردیف‌های خام تاریخچه
    ../DATASET_CARD.md         کارت مستندات دیتاست (همان فایل خالی پر می‌شود)
    ../ml_training/*.jsonl     با صدا زدن خودِ export_training_data.py تولید می‌شود

ویژگی‌ها:
  • فقط stdlib — دیتابیس read-only باز می‌شود (هیچ نوشتنی روی DB نیست).
  • شماره‌موبایل/ایمیل/URL از متن‌ها پاک می‌شود؛ ستون‌های seller_name،
    location_district، url و image_url اصلاً صادر نمی‌شوند.
  • .env خوانده نمی‌شود.

اجرا (پوشه 5_unified_local_hub):
    python export_training_bundle.py
    python export_training_bundle.py --price-sample 50000 --db data/market.db
"""

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HUB = Path(__file__).resolve().parent
OUT = HUB / "exports" / "training_bundle"
CARD = HUB / "exports" / "DATASET_CARD.md"

# ----------------------------------------------------------------------------
# پاک‌سازی اطلاعات شخصی
# ----------------------------------------------------------------------------
# فقط شماره‌موبایل ایران. شکل قبلی یک شاخه‌ی آزاد داشت
# (\d{2,3}[- ]?\d{3,4}[- ]?\d{4}) که «هر» رشته‌ی ۹ تا ۱۱ رقمی را شماره می‌گرفت و
# کد محصول را می‌بلعید: «مدل 6224598712» می‌شد «مدل <PHONE>» (id 9387).
# کرانه‌های (?<!\d)/(?!\d) جلوی خوردن بخشی از یک عدد بلندتر را هم می‌گیرند
# (پیش‌تر «0912 345 6789» به «0<PHONE>» تبدیل می‌شد).
PHONE_RE = re.compile(r"(?<!\d)(?:\+?98|0098|0)?9\d{2}[-\s]?\d{3}[-\s]?\d{4}(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
URL_RE = re.compile(r"https?://\S+|www\.\S+")
ID_RE = re.compile(r"\b(?:کد ملی|شبا|IBAN|کدملی)\b[:\s]*[\w-]+", re.I)


def scrub(text):
    if not text:
        return ""
    t = URL_RE.sub("<URL>", str(text))
    t = EMAIL_RE.sub("<EMAIL>", t)
    t = PHONE_RE.sub("<PHONE>", t)
    t = ID_RE.sub("<ID>", t)
    return " ".join(t.split())[:600]


def sha256_of(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}"
        n /= 1024.0


def write_jsonl(path: Path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def cols(cur, table):
    try:
        return [r[1] for r in cur.execute(f"PRAGMA table_info({table});")]
    except sqlite3.Error:
        return []


# ----------------------------------------------------------------------------
def build(db_path: Path, price_sample: int, desc_chars: int):
    OUT.mkdir(parents=True, exist_ok=True)
    uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_db": str(db_path),
        "source_db_bytes": db_path.stat().st_size,
        "pii_scrubbed": True,
        "files": {},
        "notes": [],
    }

    def record(name, n, extra=None):
        p = OUT / name
        entry = {"rows": n, "bytes": p.stat().st_size, "sha256": sha256_of(p)}
        if extra:
            entry.update(extra)
        manifest["files"][name] = entry
        print(f"  ✔ {name:<28} {n:>9,} ردیف   {human(entry['bytes'])}")

    # ---------------- ۱) محصولات کانونیکال ----------------
    have = cols(cur, "canonical_products")
    sel = [c for c in ("canonical_key", "title_fa", "brand", "category_key",
                       "category_std", "category_source", "specs_json",
                       "digikala_price_toman", "torob_min_price_toman",
                       "torob_shops_count", "divar_avg_price_toman", "divar_min_price_toman",
                       "esam_avg_price_toman", "esam_min_price_toman",
                       "depreciation_percent", "last_synced_at") if c in have]
    rows = []
    for r in cur.execute(f"SELECT {','.join(sel)} FROM canonical_products;"):
        d = dict(r)
        d["title_fa"] = scrub(d.get("title_fa"))
        rows.append(d)
    write_jsonl(OUT / "canonical_products.jsonl", rows)
    record("canonical_products.jsonl", len(rows))

    # ---------------- ۲) تاریخچه‌ی اصلاح دسته (طلای آموزش) ----------------
    if "category_history" in [t[0] for t in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table';")]:
        rows = [dict(r) for r in cur.execute(
            "SELECT * FROM category_history ORDER BY id;")]
        write_jsonl(OUT / "category_history.jsonl", rows)
        record("category_history.jsonl", len(rows))
    else:
        manifest["notes"].append("جدول category_history وجود ندارد.")

    # ---------------- ۳) سیگنال‌های چرتِ آموخته‌شده ----------------
    rows = [dict(r) for r in cur.execute("SELECT * FROM learned_junk_signals ORDER BY id;")]
    write_jsonl(OUT / "learned_junk_signals.jsonl", rows)
    record("learned_junk_signals.jsonl", len(rows))

    # ---------------- ۴) کش قضاوت‌های LLM ----------------
    rows = []
    for r in cur.execute("SELECT * FROM ai_review_cache ORDER BY reviewed_at;"):
        d = dict(r)
        d["title"] = scrub(d.get("title"))
        rows.append(d)
    write_jsonl(OUT / "ai_review_cache.jsonl", rows)
    record("ai_review_cache.jsonl", len(rows))

    # ---------------- ۵) آگهی‌ها (بدون PII) ----------------
    lc = cols(cur, "store_listings")
    keep = [c for c in ("id", "canonical_key", "store_key", "item_id", "condition",
                        "is_auction", "bids_count", "seller_score", "warranty",
                        "rating_score", "reviews_count", "rrp_price_toman",
                        "price_toman", "observed_at", "is_verified", "quality_status",
                        "rejection_reason", "confidence_score") if c in lc]
    dropped = [c for c in ("seller_name", "location_district", "url", "image_url") if c in lc]
    rows = []
    q = (f"SELECT {','.join(keep)}, title_fa, description, specs_json "
         f"FROM store_listings ORDER BY id;")
    for r in cur.execute(q):
        d = dict(r)
        d["title_fa"] = scrub(d.get("title_fa"))
        d["description"] = scrub(d.get("description"))[:desc_chars]
        d.pop("specs_json", None)
        rows.append(d)
    write_jsonl(OUT / "listings.jsonl", rows)
    record("listings.jsonl", len(rows), {"pii_columns_dropped": dropped})

    by_status = {}
    for r in cur.execute("SELECT store_key, quality_status, COUNT(*) c FROM store_listings "
                         "GROUP BY 1,2 ORDER BY 3 DESC;"):
        by_status[f"{r['store_key']}/{r['quality_status'] or '(empty)'}"] = r["c"]
    by_source = {r["category_source"] or "(empty)": r["c"] for r in cur.execute(
        "SELECT category_source, COUNT(*) c FROM canonical_products GROUP BY 1;")} if "category_source" in have else {}
    by_cat = {r["category_std"] or "(empty)": r["c"] for r in cur.execute(
        "SELECT category_std, COUNT(*) c FROM canonical_products GROUP BY 1 ORDER BY 2 DESC;")} if "category_std" in have else {}

    # ---------------- ۶) خلاصه‌ی قیمت (محصول × سایت) ----------------
    with open(OUT / "price_summary.csv", "w", newline="", encoding="utf-8") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["canonical_key", "store_key", "n_obs", "min_price",
                       "avg_price", "max_price", "first_seen", "last_seen"])
        n = 0
        for r in cur.execute("""
                SELECT canonical_key, store_key, COUNT(*) n, MIN(price_toman) mn,
                       CAST(ROUND(AVG(price_toman)) AS INTEGER) av, MAX(price_toman) mx,
                       MIN(recorded_at) f, MAX(recorded_at) l
                FROM price_history GROUP BY 1,2 ORDER BY 1,2;"""):
            wcsv.writerow([r["canonical_key"], r["store_key"], r["n"], r["mn"],
                           r["av"], r["mx"], r["f"], r["l"]])
            n += 1
    record("price_summary.csv", n)

    # ---------------- ۷) نمونه‌ی خام تاریخچه (یکنواخت و قطعی) ----------------
    total = cur.execute("SELECT COUNT(*) c FROM price_history;").fetchone()["c"]
    step = max(1, total // max(1, price_sample))
    with open(OUT / "price_history_sample.csv", "w", newline="", encoding="utf-8") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["canonical_key", "store_key", "price_toman", "condition", "recorded_at"])
        n = 0
        for r in cur.execute(f"""
                SELECT canonical_key, store_key, price_toman, condition, recorded_at
                FROM price_history WHERE id % {step} = 0 ORDER BY id;"""):
            wcsv.writerow([r["canonical_key"], r["store_key"], r["price_toman"],
                           scrub(r["condition"]), r["recorded_at"]])
            n += 1
    record("price_history_sample.csv", n,
           {"sampled_from": total, "step": step})

    conn.close()

    manifest["stats"] = {
        "listings_by_store_status": by_status,
        "canonical_by_category_source": by_source,
        "canonical_by_category_std": by_cat,
        "price_history_rows_total": total,
    }
    total_bytes = sum(v["bytes"] for v in manifest["files"].values())
    manifest["total_bytes"] = total_bytes
    if total_bytes > 40 * 1024 * 1024:
        manifest["notes"].append(f"⚠️ حجم بسته {human(total_bytes)} است — برای گیت بزرگ است.")
    with open(OUT / "MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


# ----------------------------------------------------------------------------
def write_dataset_card(manifest):
    s = manifest["stats"]
    lines = [
        "# 🎓 کارت دیتاست بازار چهارگانه (Quad-Market Dataset Card)",
        "",
        f"> تولید خودکار توسط `export_training_bundle.py` در {manifest['generated_at']}",
        f"> منبع: `{Path(manifest['source_db']).name}` ({human(manifest['source_db_bytes'])})",
        "",
        "## ۱) ماهیت داده",
        "آگهی‌ها و قیمت‌های چهار بازار کالای دیجیتال ایران: دیجی‌کالا، ترب، دیوار و ایسام؛",
        "گردآوری‌شده توسط خزنده‌های مستقل و تجمیع‌شده در هاب لوکال. سه وظیفه‌ی یادگیری:",
        "",
        "1. **دسته‌بندی** (۱۴ دسته): `title`+`description` → `category_std`",
        "2. **کیفیت/چرت**: `title`+`description`+`price` → `clean | junk` (+ دلیل)",
        "3. **پیش‌بینی قیمت/آربیتراژ**: ویژگی‌های جدولی → قیمت مرجع و درصد تخفیف",
        "",
        "## ۲) فایل‌ها",
        "",
        "| فایل | ردیف | حجم | نقش |",
        "|---|---:|---:|---|",
    ]
    role = {
        "canonical_products.jsonl": "محصول کانونیکال + دسته و قیمت مرجع هر بازار",
        "listings.jsonl": "نمونه‌های خام با برچسب کیفیت (هسته‌ی هر سه وظیفه)",
        "category_history.jsonl": "اصلاحات انسانی X→Y — گران‌بهاترین بخش (hard examples)",
        "learned_junk_signals.jsonl": "الگوهای چرت تأییدشده (weak supervision)",
        "ai_review_cache.jsonl": "قضاوت LLM با confidence (داده‌ی تقطیر/distillation)",
        "price_summary.csv": "آمار قیمت به تفکیک محصول×سایت",
        "price_history_sample.csv": "نمونه‌ی یکنواخت ردیف‌های خام تاریخچه",
    }
    for name, meta in manifest["files"].items():
        lines.append(f"| `{name}` | {meta['rows']:,} | {human(meta['bytes'])} | {role.get(name, '')} |")

    lines += ["", "## ۳) برچسب‌ها و منبع آن‌ها", "",
              "`label_source` در فایل‌های `ml_training/` یکی از این سه است و باید وزن‌دهی شود:",
              "",
              "- `human` / `manual` — تأیید ✋، حذف 🗑 یا تغییر دسته 🗂 توسط انسان (قابل‌اعتمادترین)",
              "- `ai` — قضاوت مدل زبانی (Groq) با `confidence`",
              "- `rule` — قاعده‌ی Regex/قیمتی در `core/data_cleaner.py` (پرخطاترین)",
              "",
              "### توزیع آگهی‌ها بر حسب سایت و وضعیت کیفیت",
              "",
              "| سایت/وضعیت | تعداد |", "|---|---:|"]
    for k, v in sorted(s["listings_by_store_status"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{k}` | {v:,} |")

    lines += ["", "### توزیع محصولات بر حسب منبع دسته‌بندی", "", "| منبع | تعداد |", "|---|---:|"]
    for k, v in sorted(s["canonical_by_category_source"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{k}` | {v:,} |")

    lines += ["", "### توزیع محصولات بر حسب دسته‌ی استاندارد", "", "| دسته | تعداد |", "|---|---:|"]
    for k, v in sorted(s["canonical_by_category_std"].items(), key=lambda x: -x[1]):
        lines.append(f"| `{k}` | {v:,} |")

    lines += [
        "",
        "## ۴) حریم شخصی",
        "- ستون‌های `seller_name`, `location_district`, `url`, `image_url` صادر نمی‌شوند.",
        "- در متن `title_fa`/`description`: شماره‌موبایل → `<PHONE>`، ایمیل → `<EMAIL>`،",
        "  لینک → `<URL>`، و الگوی کد ملی/شبا → `<ID>`.",
        "- فایل `.env` (کلیدهای Groq) هیچ‌وقت خوانده یا صادر نمی‌شود.",
        "",
        "## ۵) شکاف‌های شناخته‌شده (قبل از آموزش بخوانید)",
        "- **تکراری/نشتی:** عنوان‌های نزدیک بین آگهی‌ها تکرار می‌شوند؛ قبل از split باید بر اساس",
        "  `canonical_key` گروه‌بندی شود (GroupKFold) وگرنه آزمون خوش‌بینانه می‌شود.",
        "- **پوشش توضیحات:** بخشی از آگهی‌ها `description` خالی دارند؛ مدل نباید به آن وابسته شود.",
        "- **نام‌بالانس:** `other` و `mobile` بزرگ‌اند و `monitor`/`motherboard` کوچک → وزن‌دهی لازم است.",
        "- **برچسب `rule`:** بخش بزرگی از دسته‌ها قاعده‌ای است؛ برای ارزیابی فقط از `human`/`manual`",
        "  به‌عنوان مجموعه‌ی طلایی استفاده کنید.",
        "- **زمان:** `price_history` بازه‌ی کوتاهی دارد؛ برای پیش‌بینی سری زمانی کافی نیست.",
        "",
        "## ۶) split پیشنهادی",
        "- `train` ۸۰٪ / `valid` ۱۰٪ / `test` ۱۰٪ **به تفکیک `canonical_key`** (نه ردیف).",
        "- مجموعه‌ی طلایی تست: فقط ردیف‌هایی با `label_source in (human, manual)`.",
        "",
        "## ۷) بازتولید",
        "```bash",
        "cd 5_unified_local_hub",
        "python export_training_bundle.py      # این بسته + همین کارت",
        "python export_training_data.py       # ml_training/*.jsonl",
        "python pre_training_audit.py         # کارنامه‌ی آمادگی",
        "```",
        "",
        "## ۸) اثرانگشت فایل‌ها",
        "",
        "| فایل | sha256 (۱۲ نویسه) |", "|---|---|",
    ]
    for name, meta in manifest["files"].items():
        lines.append(f"| `{name}` | `{meta['sha256'][:12]}` |")
    lines += ["", f"مجموع بسته: **{human(manifest['total_bytes'])}**", ""]

    CARD.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✔ DATASET_CARD.md               {len(lines):,} خط   {human(CARD.stat().st_size)}")


# ----------------------------------------------------------------------------
def run_ml_training_export():
    """صدا زدن همان اسکریپت موجود — بدون کپی‌کردن منطقش."""
    sys.path.insert(0, str(HUB))
    try:
        from core.taxonomy import ensure_category_columns
        ensure_category_columns()
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️ ensure_category_columns: {e}")
    try:
        import export_training_data
        export_training_data.main()
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ export_training_data.py اجرا نشد: {type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(HUB / "data" / "market.db"))
    ap.add_argument("--price-sample", type=int, default=30000)
    ap.add_argument("--desc-chars", type=int, default=400)
    ap.add_argument("--skip-ml-export", action="store_true")
    a = ap.parse_args()

    db_path = Path(a.db)
    print("=" * 64)
    print("📦 ساخت بسته‌ی قابل push برای آموزش AI")
    print("=" * 64)
    if not db_path.exists():
        print(f"❌ دیتابیس پیدا نشد: {db_path}")
        sys.exit(1)
    print(f"منبع: {db_path}  ({human(db_path.stat().st_size)}) — فقط خواندنی\n")

    manifest = build(db_path, a.price_sample, a.desc_chars)
    print()
    write_dataset_card(manifest)

    if not a.skip_ml_export:
        print("\n—— ml_training (با اسکریپت موجود) ——")
        run_ml_training_export()

    print("\n" + "=" * 64)
    print(f"✅ بسته آماده است: {OUT}")
    print(f"   حجم کل: {human(manifest['total_bytes'])}")
    for n in manifest["notes"]:
        print(f"   {n}")
    print("\nقدم بعدی:")
    print("   git add 5_unified_local_hub/exports/training_bundle "
          "5_unified_local_hub/exports/ml_training/*.jsonl "
          "5_unified_local_hub/exports/DATASET_CARD.md")


if __name__ == "__main__":
    main()

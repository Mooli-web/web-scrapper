# -*- coding: utf-8 -*-
"""
📋 انبارگردانی لوکال — inventory_local.py
==========================================
یک اسکریپت «فقط خواندنی» که از وضعیت واقعی کامپیوتر تو یک گزارش متنی می‌سازد
تا بدون ارسال هیچ داده‌ی حجیم یا سری، بفهمیم چه فایل‌هایی باید push شوند.

ویژگی‌ها:
  • فقط stdlib پایتون — هیچ پکیجی لازم ندارد (نه pip، نه venv).
  • هیچ فایلی را تغییر، حذف یا جابه‌جا نمی‌کند (دیتابیس‌ها read-only باز می‌شوند).
  • محتوای .env و کلیدهای API هرگز چاپ نمی‌شود — فقط «نام متغیر» و «طول مقدار».
  • همه‌چیز در یک فایل خروجی می‌نویسد: inventory_local_report.txt

اجرا (از ریشه‌ی مخزن web-scrapper):
    python inventory_local.py
یا با مسیر دلخواه خروجی:
    python inventory_local.py C:\\Users\\me\\Desktop\\report.txt
"""

import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------------
# تنظیمات
# ----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "inventory_local_report.txt"

# پوشه‌هایی که فایل‌به‌فایل لیست نمی‌شوند (فقط حجم و تعدادشان گزارش می‌شود)
HEAVY_DIRS = {
    "node_modules", ".venv", "venv", "env", "__pycache__", ".git",
    "chrome_profile", ".idea", ".vscode", "dist", "build", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".cache", ".next", ".nuxt", ".output",
    ".turbo", ".parcel-cache", ".svelte-kit", ".tox", ".nox", "htmlcov",
}

MAX_FILES_PER_DIR = 300          # سقف لیست فایل در هر پوشه
MAX_LISTED_GIT_ENTRIES = 200     # سقف لیست untracked/ignored
DATA_EXT = {".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3",
            ".csv", ".json", ".jsonl", ".json.gz", ".parquet", ".xlsx"}
COUNT_TABLES_LIMIT = 400         # اگر جدولی بزرگ‌تر از این بود هم شمرده می‌شود (فقط برای اطلاع)

_out_lines = []


def w(line=""):
    """یک خط در گزارش (و روی کنسول)."""
    _out_lines.append(line)


def hr(title):
    w("")
    w("=" * 74)
    w(f"== {title}")
    w("=" * 74)


def safe(fn, default="(خطا)"):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return f"{default}: {type(e).__name__}: {e}"


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}TB"


def sh(args, cwd=None, timeout=60):
    """اجرای دستور و بازگرداندن (rc, stdout+stderr)."""
    try:
        p = subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True,
                           text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {e}"


def git(args, cwd=None):
    return sh(["git"] + args, cwd=cwd)


# ----------------------------------------------------------------------------
# ۰) سربرگ و محیط
# ----------------------------------------------------------------------------
def sec_header():
    hr("۰) محیط و زمان اجرا")
    w(f"زمان:            {datetime.now().isoformat(timespec='seconds')}")
    w(f"سیستم‌عامل:      {platform.platform()}")
    w(f"پایتون:          {sys.version.splitlines()[0]}  ({sys.executable})")
    rc, out = git(["--version"])
    w(f"گیت:             {out.splitlines()[0] if out else '(git پیدا نشد)'}")
    w(f"مسیر اجرا:       {ROOT}")
    try:
        w(f"نام کاربر/میزبان: {os.environ.get('USERNAME') or os.environ.get('USER', '?')} @ {platform.node()}")
    except Exception:  # noqa: BLE001
        pass


# ----------------------------------------------------------------------------
# ۱) وضعیت گیت مخزن اصلی
# ----------------------------------------------------------------------------
def sec_git():
    hr("۱) وضعیت گیت — مخزن اصلی (web-scrapper)")
    for label, args in (
        ("برنچ فعلی", ["rev-parse", "--abbrev-ref", "HEAD"]),
        ("HEAD", ["log", "-1", "--format=%h %ad %s", "--date=iso"]),
        ("remote", ["remote", "-v"]),
        ("آخرین fetch", ["log", "-1", "--format=%h %s", "origin/main"]),
    ):
        rc, out = git(args, ROOT)
        w(f"[{label}] rc={rc}")
        for ln in (out or "").splitlines()[:12]:
            w(f"    {ln}")

    rc, out = git(["ls-files"], ROOT)
    files = [x for x in (out or "").splitlines() if x]
    w(f"\nتعداد فایل‌های track‌شده: {len(files)}")

    w("\n-- submodule pointer ها (mode 160000) --")
    rc, out = git(["ls-tree", "HEAD"], ROOT)
    subs = [ln for ln in (out or "").splitlines() if ln.startswith("160000")]
    if subs:
        for ln in subs:
            w(f"    {ln}")
    else:
        w("    (هیچ)")
    w(f"    فایل .gitmodules وجود دارد؟ {'بله' if (ROOT / '.gitmodules').exists() else 'خیر ❌'}")

    rc, out = git(["submodule", "status"], ROOT)
    w(f"\n[git submodule status] rc={rc}")
    for ln in (out or "").splitlines()[:10]:
        w(f"    {ln}")

    w("\n-- تغییرات/فایل‌های track‌نشده/ignore‌شده (git status --porcelain --ignored) --")
    rc, out = git(["status", "--porcelain", "--ignored=matching"], ROOT)
    entries = [x for x in (out or "").splitlines() if x.strip()]
    w(f"    تعداد کل: {len(entries)}")
    for ln in entries[:MAX_LISTED_GIT_ENTRIES]:
        w(f"    {ln}")
    if len(entries) > MAX_LISTED_GIT_ENTRIES:
        w(f"    ... و {len(entries) - MAX_LISTED_GIT_ENTRIES} مورد دیگر (بریده شد)")

    w("\n-- آیا برنچ‌های دیگری هم داری؟ --")
    rc, out = git(["branch", "-a", "-vv"], ROOT)
    for ln in (out or "").splitlines()[:20]:
        w(f"    {ln}")

    w("\n-- آخرین ۱۰ کامیت --")
    rc, out = git(["log", "--oneline", "-10"], ROOT)
    for ln in (out or "").splitlines():
        w(f"    {ln}")


# ----------------------------------------------------------------------------
# ۲) درخت پوشه‌ها (با حجم)
# ----------------------------------------------------------------------------
def dir_stats(path: Path):
    """(تعداد فایل، مجموع بایت) برای یک پوشه، بدون دنبال‌کردن symlink."""
    n, total = 0, 0
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in HEAVY_DIRS]
        for f in filenames:
            try:
                total += (Path(dirpath) / f).stat().st_size
                n += 1
            except OSError:
                pass
    return n, total


def sec_tree():
    hr("۲) درخت پوشه‌ها و فایل‌ها")
    entries = sorted(ROOT.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    for p in entries:
        if p.name in {".git"}:
            w(f"[dir] .git  (پوشیده)")
            continue
        if p.is_dir():
            n, total = dir_stats(p)
            w(f"[dir] {p.name}/   → {n} فایل، {human(total)}")
            _list_dir(p, prefix="    ")
        else:
            w(f"[file] {p.name}   {human(p.stat().st_size)}")


def _list_dir(path: Path, prefix="    ", depth=0):
    if depth > 3:
        return
    try:
        kids = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    except OSError as e:
        w(f"{prefix}(خوانده نشد: {e})")
        return
    listed = 0
    for k in kids:
        if listed >= MAX_FILES_PER_DIR:
            w(f"{prefix}... بقیه‌ی فایل‌های این پوشه بریده شد")
            break
        if k.is_dir():
            if k.name in HEAVY_DIRS:
                n, total = dir_stats(k)
                w(f"{prefix}{k.name}/   [سنگین/نادیده در لیست] {n} فایل، {human(total)}")
                continue
            n, total = dir_stats(k)
            w(f"{prefix}{k.name}/   ({n} فایل، {human(total)})")
            _list_dir(k, prefix + "    ", depth + 1)
        else:
            try:
                st = k.stat()
                w(f"{prefix}{k.name}   {human(st.st_size)}   {datetime.fromtimestamp(st.st_mtime).date()}")
            except OSError:
                w(f"{prefix}{k.name}   (stat نشد)")
            listed += 1


# ----------------------------------------------------------------------------
# ۳) آیا هر پروژه خودش یک مخزن گیت جداست؟
# ----------------------------------------------------------------------------
def sec_nested_git():
    hr("۳) مخزن‌های گیت تودرتو (آیا هر پروژه remote خودش را دارد؟)")
    candidates = [p for p in ROOT.iterdir() if p.is_dir() and p.name != ".git"]
    found = False
    for p in candidates:
        g = p / ".git"
        if not g.exists():
            w(f"• {p.name}/  → .git ندارد (جزئی از مخزن اصلی یا پوشه‌ی خالی)")
            continue
        found = True
        w(f"• {p.name}/  → مخزن گیت مستقل ({'dir' if g.is_dir() else 'gitfile'})")
        for label, args in (("remote", ["remote", "-v"]),
                            ("branch", ["rev-parse", "--abbrev-ref", "HEAD"]),
                            ("HEAD", ["log", "-1", "--format=%h %ad %s", "--date=iso"])):
            rc, out = git(args, p)
            for ln in (out or "").splitlines()[:6]:
                w(f"      [{label}] {ln}")
        rc, out = git(["status", "--porcelain", "--ignored=matching"], p)
        ent = [x for x in (out or "").splitlines() if x.strip()]
        w(f"      [untracked/ignored] {len(ent)} مورد")
        for ln in ent[:60]:
            w(f"        {ln}")
        if len(ent) > 60:
            w(f"        ... و {len(ent) - 60} مورد دیگر")
    if not found:
        w("(هیچ مخزن تودرتویی پیدا نشد)")


# ----------------------------------------------------------------------------
# ۴) فایل‌های داده (دیتابیس/CSV/JSON) — مهم‌ترین بخش برای تصمیم push
# ----------------------------------------------------------------------------
def find_data_files():
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in HEAVY_DIRS]
        for f in filenames:
            p = Path(dirpath) / f
            if p.suffix.lower() in DATA_EXT and p.name != Path(__file__).name:
                try:
                    found.append(p)
                except OSError:
                    pass
    return sorted(found, key=lambda p: -p.stat().st_size if p.exists() else 0)


def sec_data_files():
    hr("۴) فایل‌های داده (به ترتیب حجم)")
    files = find_data_files()
    w(f"تعداد: {len(files)}")
    for p in files[:120]:
        try:
            st = p.stat()
            w(f"  {human(st.st_size):>10}  {datetime.fromtimestamp(st.st_mtime).date()}  "
              f"{p.relative_to(ROOT)}")
        except OSError:
            w(f"  (stat نشد)  {p.relative_to(ROOT)}")
    if len(files) > 120:
        w(f"  ... و {len(files) - 120} فایل کوچک‌تر دیگر")


def _db_counts(db_path: Path):
    """آمار جداول — فقط خواندنی (mode=ro)."""
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    try:
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")]
        w(f"    جداول: {len(tables)}")
        for t in tables:
            try:
                n = cur.execute(f'SELECT COUNT(*) FROM "{t}";').fetchone()[0]
            except Exception as e:  # noqa: BLE001
                w(f"      {t}: (شمارش نشد: {e})")
                continue
            w(f"      {t:<28} {n:>10,} ردیف")

        def q(sql, label):
            try:
                rows = cur.execute(sql).fetchall()
            except Exception:
                return
            if not rows:
                return
            w(f"    -- {label}")
            for r in rows[:25]:
                w("       " + " | ".join("" if c is None else str(c) for c in r))

        q("""SELECT store_key, quality_status, COUNT(*) FROM store_listings
             GROUP BY store_key, quality_status ORDER BY 3 DESC;""",
          "store_listings بر حسب سایت/وضعیت کیفیت")
        q("""SELECT category_source, COUNT(*) FROM canonical_products
             GROUP BY category_source ORDER BY 2 DESC;""",
          "canonical_products بر حسب منبع دسته")
        q("""SELECT category_std, COUNT(*) FROM canonical_products
             GROUP BY category_std ORDER BY 2 DESC;""",
          "canonical_products بر حسب دسته‌ی استاندارد")
        q("SELECT COUNT(*), SUM(is_uncertain), SUM(CASE WHEN note<>'' THEN 1 ELSE 0 END) "
          "FROM category_history;", "category_history: کل / نامطمئن / دارای note")
        q("SELECT COUNT(*) FROM learned_junk_signals;", "learned_junk_signals")
        q("SELECT COUNT(*), MIN(reviewed_at), MAX(reviewed_at) FROM ai_review_cache;",
          "ai_review_cache: تعداد و بازه‌ی زمانی")
        q("SELECT COUNT(*), MIN(recorded_at), MAX(recorded_at) FROM price_history;",
          "price_history: تعداد و بازه‌ی زمانی")
        q("SELECT COUNT(*) FROM store_listings WHERE COALESCE(description,'')<>'';",
          "آگهی‌های دارای توضیحات")
    finally:
        conn.close()


def sec_db_stats():
    hr("۵) آمار داخلی دیتابیس‌ها (SQLite، فقط خواندنی)")
    dbs = []
    for dirpath, dirnames, filenames in os.walk(ROOT, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in HEAVY_DIRS]
        for f in filenames:
            if Path(f).suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                dbs.append(Path(dirpath) / f)
    if not dbs:
        w("❌ هیچ فایل .db/.sqlite پیدا نشد — یعنی داده‌ای برای export نیست.")
        return
    for p in sorted(dbs, key=lambda x: -x.stat().st_size):
        w(f"\n▶ {p.relative_to(ROOT)}   ({human(p.stat().st_size)})")
        try:
            _db_counts(p)
        except Exception as e:  # noqa: BLE001
            w(f"    ❌ باز نشد: {type(e).__name__}: {e}")


# ----------------------------------------------------------------------------
# ۶) پوشه‌ی exports و حلقه‌ی بازبینی ایجنتی
# ----------------------------------------------------------------------------
def _count_lines(p: Path):
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return -1


def sec_exports():
    hr("۶) خروجی‌ها و بسته‌های بازبینی (exports/)")
    exp = ROOT / "5_unified_local_hub" / "exports"
    if not exp.exists():
        w("❌ پوشه‌ی exports پیدا نشد.")
        return
    for p in sorted(exp.rglob("*")):
        if not p.is_file():
            continue
        extra = ""
        if p.suffix.lower() in {".jsonl", ".csv", ".txt"}:
            extra = f"  ({_count_lines(p):,} خط)"
        elif p.suffix.lower() == ".json":
            try:
                with open(p, "r", encoding="utf-8") as f:
                    d = json.load(f)
                if isinstance(d, list):
                    extra = f"  (لیست، {len(d):,} آیتم)"
                elif isinstance(d, dict):
                    extra = f"  (dict، کلیدها: {', '.join(list(d)[:8])})"
            except Exception as e:  # noqa: BLE001
                extra = f"  (parse نشد: {type(e).__name__})"
        w(f"  {human(p.stat().st_size):>10}  {p.relative_to(ROOT)}{extra}")

    w("\n-- نتیجه‌ی بازبینی ایجنت‌ها برگشته؟ --")
    results = sorted((exp / "review_batches").glob("result_*.json")) if (exp / "review_batches").exists() else []
    if not results:
        w("  ❌ هیچ result_*.json نیست → برچسب‌های ایجنت هنوز import نشده‌اند.")
    for r in results:
        try:
            with open(r, "r", encoding="utf-8") as f:
                d = json.load(f)
            dec = d.get("decisions", d) if isinstance(d, dict) else d
            w(f"  ✅ {r.name}: {len(dec):,} تصمیم")
        except Exception as e:  # noqa: BLE001
            w(f"  ⚠️ {r.name}: parse نشد ({type(e).__name__})")

    card = exp / "DATASET_CARD.md"
    if card.exists():
        w(f"\n-- DATASET_CARD.md: {card.stat().st_size} بایت "
          f"{'(خالی ❌)' if card.stat().st_size == 0 else ''}")


# ----------------------------------------------------------------------------
# ۷) فایل‌های سری — فقط نام و اندازه، هرگز محتوا
# ----------------------------------------------------------------------------
def sec_secrets():
    hr("۷) فایل‌های حاوی کلید (فقط نام/اندازه/نام متغیر — مقدار چاپ نمی‌شود)")
    pats = [".env", ".env.*", "*.env", "gsk_*", "*api_key*", "*apikey*", "*.pem", "credentials*"]
    hits = set()
    for pat in pats:
        for p in ROOT.rglob(pat):
            if not any(part in HEAVY_DIRS for part in p.parts):
                hits.add(p)
    if not hits:
        w("هیچ فایل سری پیدا نشد.")
    for p in sorted(hits):
        try:
            w(f"  🔒 {p.relative_to(ROOT)}   {human(p.stat().st_size)}")
        except OSError:
            continue
        if p.name.startswith(".env") or p.suffix.lower() in {".env", ".txt"}:
            try:
                for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    masked = "تنظیم‌شده" if v.strip() else "خالی"
                    w(f"       • {k.strip()} → {masked} (طول {len(v.strip())})")
            except OSError:
                pass
    w("\n  ⚠️ هیچ‌کدام از این فایل‌ها را push نکن؛ اگر لازم بود فقط نام متغیرها را بگو.")


# ----------------------------------------------------------------------------
# ۸) ماژول‌ها و وابستگی‌های پایتون
# ----------------------------------------------------------------------------
def sec_python_env():
    hr("۸) محیط پایتون و وابستگی‌ها")
    rc, out = sh([sys.executable, "-m", "pip", "freeze"], ROOT, timeout=120)
    lines = [x for x in (out or "").splitlines() if x.strip()]
    w(f"pip freeze: {len(lines)} پکیج")
    keys = ("fastapi", "uvicorn", "pydantic", "requests", "pytest", "httpx",
            "numpy", "pandas", "scikit", "sklearn", "torch", "transformers",
            "fasttext", "groq", "playwright", "selenium", "bs4", "lxml", "openai")
    low = [x.lower() for x in lines]
    for k in keys:
        hit = [x for x in lines if x.lower().startswith(k) or f"=={k}" in x.lower()]
        if hit:
            w(f"  ✅ {hit[0]}")
        elif k in low:
            w(f"  ✅ {k}")
    w("\n  -- کتابخانه‌های ML نصب‌شده (numpy/pandas/sklearn/torch/fasttext) --")
    ml = [x for x in lines if any(x.lower().startswith(k) for k in
          ("numpy", "pandas", "scikit", "torch", "transformers", "fasttext", "xgboost", "lightgbm"))]
    w("  " + (", ".join(ml) if ml else "❌ هیچ‌کدام نصب نیست"))

    w("\n  -- ماژول خزنده‌ی دیوار (که تست‌ها لازم دارند) --")
    for cand in ("2_divar_cloud/crawler/junk_filter.py", "2_divar_cloud/junk_filter.py",
                 "2_divar_cloud/crawler/__init__.py"):
        p = ROOT / cand
        w(f"  {'✅' if p.exists() else '❌'} {cand}")

    w("\n  -- فایل‌های رله‌ی Groq (مطابق README ریشه) --")
    for d in ("1_digikala_cloud", "2_divar_cloud", "4_esam_cloud"):
        p = ROOT / d / "server" / "ai_relay.py"
        w(f"  {'✅' if p.exists() else '❌'} {d}/server/ai_relay.py")


# ----------------------------------------------------------------------------
# ۹) جمع‌بندی خودکار: چه چیزهایی کاندیدای push هستند؟
# ----------------------------------------------------------------------------
def sec_hints():
    hr("۹) جمع‌بندی خودکار (کاندیداهای push)")
    hints = []

    rc, out = git(["ls-tree", "HEAD"], ROOT)
    if any(ln.startswith("160000") for ln in (out or "").splitlines()):
        hints.append("submodule pointer بدون .gitmodules → پوشه‌های خزنده در مخزن اصلی خالی‌اند.")

    dbs = []
    for dirpath, dirnames, filenames in os.walk(ROOT, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in HEAVY_DIRS]
        dbs += [Path(dirpath) / f for f in filenames
                if Path(f).suffix.lower() in {".db", ".sqlite", ".sqlite3"}]
    if dbs:
        hints.append(f"{len(dbs)} دیتابیس لوکال پیدا شد → به‌جای push فایل .db، خروجی JSONL/CSV بگیرید.")
    else:
        hints.append("هیچ دیتابیس لوکالی پیدا نشد → داده‌ای برای export وجود ندارد.")

    exp = ROOT / "5_unified_local_hub" / "exports"
    if exp.exists() and not list((exp / "review_batches").glob("result_*.json")):
        hints.append("result_*.json وجود ندارد → بازبینی ایجنت‌ها هنوز برنگشته/import نشده.")
    if (exp / "DATASET_CARD.md").exists() and (exp / "DATASET_CARD.md").stat().st_size == 0:
        hints.append("DATASET_CARD.md خالی است.")

    ml_dir = exp / "ml_training"
    if not ml_dir.exists() or not any(ml_dir.iterdir()):
        hints.append("exports/ml_training/ خالی یا ناموجود → export_training_data.py اجرا نشده.")

    rc, out = git(["status", "--porcelain"], ROOT)
    dirty = [x for x in (out or "").splitlines() if x.strip()]
    hints.append(f"{len(dirty)} فایل تغییر کرده/track‌نشده (بدون ignore) در مخزن اصلی.")

    for i, h in enumerate(hints, 1):
        w(f"  {i}. {h}")


# ----------------------------------------------------------------------------
def main():
    out_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUT
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    print("در حال انبارگردانی… (چیزی تغییر نمی‌کند)")
    for fn in (sec_header, sec_git, sec_tree, sec_nested_git, sec_data_files,
               sec_db_stats, sec_exports, sec_secrets, sec_python_env, sec_hints):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            hr(f"خطا در بخش {fn.__name__}")
            w(f"{type(e).__name__}: {e}")
        print(f"  ✔ {fn.__name__}")

    w("")
    w("=" * 74)
    body = "\n".join(_out_lines) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(body)

    print(f"\n✅ گزارش نوشته شد:\n   {out_path}")
    print(f"   {len(_out_lines):,} خط، {human(out_path.stat().st_size)}")
    print("   همین یک فایل را برای ایجنت بفرست.")


if __name__ == "__main__":
    main()

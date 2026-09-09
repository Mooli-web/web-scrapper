# -*- coding: utf-8 -*-
"""
🚚 push تکه‌تکه با تلاش مجدد — push_in_chunks.py
=================================================
وقتی `git push` روی یک pack بزرگ (مثلاً ۲۹ مگابایت) با
`HTTP 408 / curl 22 / the remote end hung up unexpectedly` شکست می‌خورد،
علت معمولاً یک درخواست HTTPS بزرگ روی لینک پرنوسان است. این اسکریپت تغییرات
را به چند کامیت کوچک تقسیم می‌کند و بعد از هر کامیت یک push کوچک می‌زند
(با تلاش مجدد)، تا یک قطعی شبکه کل کار را خراب نکند.

چه کار می‌کند:
  1. `git fetch origin main` و تنظیم چند پارامتر git (فقط در همین مخزن).
  2. اگر کامیت بزرگی ساخته‌ای، آن را با `reset --mixed` برمی‌گرداند
     (فایل‌ها روی دیسک دست‌نخورده می‌مانند — فقط از حالت کامیت خارج می‌شوند).
  3. مسیرها را گروه‌گروه `add` + `commit` + `push` می‌کند (کوچک → بزرگ).
  4. اگر جایی شکست خورد، همان‌جا می‌ایستد و می‌گوید چطور ادامه بدهی
     (گروه‌های قبلی روی GitHub مانده‌اند؛ اجرای دوباره از همان‌جا ادامه می‌دهد).

اجرا (از ریشه‌ی مخزن web-scrapper):
    python push_in_chunks.py --dry-run     # فقط نشان می‌دهد چه خواهد شد
    python push_in_chunks.py --yes         # واقعاً انجام می‌دهد
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BRANCH = "main"

# ترتیب مهم است: اول کوچک‌ها، بعد داده‌های بزرگ؛ «بقیه‌ی هاب» آخر از همه و
# با استثنا کردن exports تا داده‌ها دوباره در یک کامیت بزرگ جمع نشوند.
GROUPS = [
    ("ابزارها و رفع باگ‌های هاب",
     ["inventory_local.py", ".gitignore", "push_in_chunks.py",
      "5_unified_local_hub/export_training_bundle.py",
      "5_unified_local_hub/export_training_data.py",
      "5_unified_local_hub/pre_training_audit.py",
      "5_unified_local_hub/check_human_labels.py"]),
    ("کد خزنده‌ی ترب", ["3_torob_windows"]),
    ("کد خزنده‌ی دیجی‌کالا", ["1_digikala_cloud"]),
    ("کد خزنده‌ی دیوار", ["2_divar_cloud"]),
    ("کد خزنده‌ی ایسام", ["4_esam_cloud"]),
    ("دیتاست آموزش (ml_training)", ["5_unified_local_hub/exports/ml_training"]),
    ("بسته‌ی آموزش: آگهی‌ها (بزرگ‌ترین فایل)",
     ["5_unified_local_hub/exports/training_bundle/listings.jsonl"]),
    ("بسته‌ی آموزش: محصولات کانونیکال",
     ["5_unified_local_hub/exports/training_bundle/canonical_products.jsonl"]),
    ("بسته‌ی آموزش: کش AI، تاریخچه و سیگنال‌ها",
     ["5_unified_local_hub/exports/training_bundle/ai_review_cache.jsonl",
      "5_unified_local_hub/exports/training_bundle/category_history.jsonl",
      "5_unified_local_hub/exports/training_bundle/learned_junk_signals.jsonl"]),
    ("بسته‌ی آموزش: قیمت و مستندات",
     ["5_unified_local_hub/exports/training_bundle/price_summary.csv",
      "5_unified_local_hub/exports/training_bundle/price_history_sample.csv",
      "5_unified_local_hub/exports/training_bundle/MANIFEST.json",
      "5_unified_local_hub/exports/DATASET_CARD.md"]),
    ("بقیه‌ی تغییرات هاب (بدون exports)",
     ["5_unified_local_hub", ":(exclude)5_unified_local_hub/exports"]),
]


def git(args, timeout=1800):
    p = subprocess.run(["git"] + args, cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def must_git(args, what):
    rc, out = git(args)
    if rc != 0:
        print(f"❌ {what} ناموفق بود:\n{out}")
        sys.exit(1)
    return out


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}"
        n /= 1024.0


def staged_info():
    """(تعداد فایل stage‌شده، مجموع بایت، خلاصه‌ی diff)"""
    rc, files = git(["diff", "--cached", "--name-only"])
    names = [x for x in (files or "").splitlines() if x]
    size = sum((ROOT / f).stat().st_size for f in names if (ROOT / f).is_file())
    rc, short = git(["diff", "--cached", "--shortstat"])
    return len(names), size, (short or "(چیزی stage نشد)")


CRAWLER_DIRS = ["1_digikala_cloud", "2_divar_cloud", "4_esam_cloud"]


def fix_gitlinks(nested_mode):
    """
    دو مانع را برطرف می‌کند:
      ۱) gitlink در index: تا وقتی `1_digikala_cloud` با mode 160000 در index است،
         git داخل پوشه نمی‌رود و `git add` هیچ فایلی اضافه نمی‌کند.
      ۲) `.git` تودرتو: اگر بماند، `git add` دوباره gitlink می‌سازد (embedded repo).
         با --nested-git auto به بیرون از مخزن منتقل می‌شود (برگشت‌پذیر).
    """
    print("\n[۲٫۵] بررسی gitlink و .git تودرتو")
    for t in CRAWLER_DIRS:
        rc, out = git(["ls-files", "-s", "--", t])
        if out and out.split()[0] == "160000":
            git(["rm", "--cached", "-q", "--", t])
            print(f"    ✔ gitlink «{t}» از index حذف شد")

    blockers = []
    for t in CRAWLER_DIRS:
        g = ROOT / t / ".git"
        if not g.exists():
            continue
        if nested_mode != "auto":
            blockers.append(t)
            continue
        dest = ROOT.parent / "git_backup" / f"{t}.git"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            print(f"    ⚠️ {dest} از قبل هست — «{t}/.git» دست‌نخورده ماند")
            blockers.append(t)
            continue
        shutil.move(str(g), str(dest))
        print(f"    ↪ {t}/.git  →  {dest}  (برای برگرداندن: دوباره جابه‌جایش کن)")
    return blockers


def push_with_retry(attempts=3):
    for i in range(1, attempts + 1):
        print(f"   ↗ push تلاش {i}/{attempts} …")
        rc, out = git(["push", "origin", f"HEAD:{BRANCH}"])
        if rc == 0:
            print("   ✅ push شد")
            return True
        print("   ⚠️ " + " | ".join(out.splitlines()[-3:]))
        if i < attempts:
            wait = 10 * i
            print(f"   … {wait} ثانیه صبر")
            time.sleep(wait)
    return False


def main():
    global BRANCH
    ap = argparse.ArgumentParser()
    ap.add_argument("--yes", action="store_true", help="بدون پرسش انجام بده")
    ap.add_argument("--dry-run", action="store_true", help="فقط گزارش، بدون تغییر")
    ap.add_argument("--branch", default=BRANCH)
    ap.add_argument("--no-tune", action="store_true", help="دست نزن به تنظیمات git")
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--nested-git", choices=("abort", "auto"), default="abort",
                    help="auto = پوشه‌های .git تودرتو را به ../git_backup منتقل کن")
    a = ap.parse_args()
    BRANCH = a.branch

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    print("=" * 66)
    print(f"🚚 push تکه‌تکه به origin/{BRANCH}")
    print("=" * 66)

    cur = must_git(["rev-parse", "--abbrev-ref", "HEAD"], "خواندن برنچ")
    if cur != BRANCH:
        print(f"❌ روی برنچ «{cur}» هستی، نه «{BRANCH}». اول:  git checkout {BRANCH}")
        sys.exit(1)

    rc, name = git(["config", "user.name"])
    rc2, mail = git(["config", "user.email"])
    if not name or not mail:
        print("❌ هویت git تنظیم نیست (کامیت‌کردن با آن ممکن نیست). اول:")
        print('       git config user.name  "نام تو"')
        print('       git config user.email "ایمیل تو"')
        sys.exit(1)

    print("\n[۱] fetch و تنظیمات شبکه‌ی git (فقط در همین مخزن)")
    git(["fetch", "origin", BRANCH])
    if not a.no_tune:
        for k, v in (("http.postBuffer", "524288000"),
                     ("http.version", "HTTP/1.1"),
                     ("http.lowSpeedLimit", "0"),
                     ("http.lowSpeedTime", "999999"),
                     ("core.compression", "0")):
            git(["config", k, v])
            print(f"    git config {k} = {v}")

    rc, base = git(["rev-parse", f"origin/{BRANCH}"])
    if rc != 0:
        print(f"❌ origin/{BRANCH} پیدا نشد — remote درست تنظیم شده؟")
        sys.exit(1)

    rc, ahead = git(["log", "--oneline", f"origin/{BRANCH}..HEAD"])
    ahead_list = [x for x in (ahead or "").splitlines() if x]
    if ahead_list:
        print(f"\n[۲] {len(ahead_list)} کامیت جلوتر از origin/{BRANCH} داری:")
        for c in ahead_list[:15]:
            print(f"      {c}")
        print("    با reset --mixed برمی‌گردند (فایل‌ها روی دیسک می‌مانند)")
        print("    تا تکه‌تکه کامیت و push شوند.")
        if not a.yes and not a.dry_run:
            if input("    ادامه؟ (y/N) ").strip().lower() != "y":
                print("    لغو شد.")
                return
        if not a.dry_run:
            must_git(["reset", "--mixed", base], "reset --mixed")
            print("    ✔ reset انجام شد")
    else:
        print("\n[۲] کامیت جلو‌افتاده‌ای نیست — از تغییرات روی دیسک شروع می‌کنم")

    blockers = fix_gitlinks(a.nested_git)
    if blockers:
        print("\n❌ این پوشه‌ها هنوز .git تودرتو دارند و git آن‌ها را به‌عنوان")
        print("   «مخزن جاسازی‌شده» اضافه می‌کند (نه فایل‌هایشان). اول منتقلشان کن:")
        print("       mkdir ..\\git_backup")
        for t in blockers:
            print(f"       move {t}\\.git ..\\git_backup\\{t}.git")
        print("   بعد دوباره اجرا کن:  python push_in_chunks.py --yes")
        print("   (یا همین حالا با:  python push_in_chunks.py --yes --nested-git auto)")
        sys.exit(3)

    print("\n[۳] گروه‌ها")
    done = 0
    for title, paths in GROUPS:
        # فقط مسیرهای موجود (pathspec استثناء با «:(» شروع می‌شود)
        add_paths = [p for p in paths if p.startswith(":(") or (ROOT / p).exists()]
        if not any(not p.startswith(":(") for p in add_paths):
            continue
        if a.dry_run:
            # مقایسه با origin/BRANCH (نه working tree) — چون در dry-run هنوز
            # reset نکرده‌ایم و ممکن است همه‌چیز کامیت‌شده و «تمیز» به‌نظر برسد.
            rc, out = git(["diff", "--name-only", base, "--"] + add_paths)
            n = len([x for x in (out or "").splitlines() if x.strip()])
            print(f"    • {title:<44} {n} فایل")
            continue

        # توجه: اینجا عمداً `git reset` نمی‌زنیم — بعد از هر کامیت index با HEAD
        # برابر است، و reset زدن gitlink های حذف‌شده را برمی‌گرداند و باعث می‌شود
        # git دوباره داخل پوشه‌های خزنده نرود (تست‌شده).
        must_git(["add", "--"] + add_paths, f"add «{title}»")
        n, size, short = staged_info()
        if n == 0:
            print(f"    – {title}: تغییری ندارد، رد شد")
            continue
        print(f"\n    ● {title}  ({n} فایل، {human(size)})")
        print(f"      {short}")
        must_git(["commit", "-q", "-m", f"chunk: {title}"], f"commit «{title}»")
        if not push_with_retry(a.attempts):
            print("\n❌ push این گروه شکست خورد.")
            print("   گروه‌های قبلی روی GitHub هستند؛ برای ادامه از همان‌جا:")
            print(f"       python {Path(__file__).name} --yes")
            sys.exit(2)
        done += 1

    if a.dry_run:
        print(f"\n(dry-run — چیزی تغییر نکرد. برای اجرا:  python {Path(__file__).name} --yes)")
        return

    print(f"\n[۴] وضعیت نهایی — {done} گروه push شد")
    rc, out = git(["log", "--oneline", "-12"])
    print(out)
    rc, out = git(["status", "--porcelain"])
    left = [x for x in (out or "").splitlines() if x.strip()]
    if left:
        print(f"\n⚠️ {len(left)} مورد هنوز کامیت نشده:")
        for x in left[:20]:
            print(f"    {x}")
    else:
        print("✔ چیزی باقی نمانده")
    rc, out = git(["ls-remote", "origin", f"refs/heads/{BRANCH}"])
    print(f"\nریموت: {out}")
    print(f"لوکال: {must_git(['rev-parse', 'HEAD'], 'rev-parse HEAD')}")


if __name__ == "__main__":
    main()

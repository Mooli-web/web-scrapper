#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""آموزش نهایی و ذخیره‌ی مدل‌های قابل‌استقرار (پایه‌ی CPU).

دو مدل:
  A) حذف/نگه‌داشتن — دودویی، روی همه‌ی نمونه‌های برچسب‌خورده.
  B) دسته‌بندی — روی ۱۵ دسته‌ی واقعی (بدون `other`)؛ `other` به‌عنوان
     fallback آستانه‌ای: اگر بیشترین احتمال زیر آستانه T بود → `other`.

چرا `other` را یاد نمی‌دهیم: کلاس catch-all ناهمگن است و هیچ مدلی مرزش را
یاد نمی‌گیرد (F1 ~.33–.42). به‌جایش، آستانه روی احتمال، «هیچ‌کدام» را می‌گیرد.

خروجی: exports/ml/model_quality.pkl و model_category.pkl (joblib).
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from collections import defaultdict
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, classification_report
from sklearn.model_selection import train_test_split
from scipy.sparse import hstack, csr_matrix

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))
from ml_baseline import normalize_text as norm, numeric as nums, REP_DIG  # noqa

ML = HUB / "exports" / "ml"
SEED = 42


def load(name):
    return [json.loads(l) for l in (ML / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def canon_map():
    out = {}
    for l in (HUB / "exports/training_bundle/listings.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(l)
        out[r["id"]] = r.get("canonical_key") or ""
    return out


def split_keys(rows, canon, sizes):
    """تقسیم بر canonical_key به len(sizes) بخش (بدون نشت)."""
    k2i = defaultdict(list)
    for i, r in enumerate(rows):
        k2i[canon.get(r["id"], r["id"])].append(i)
    ks = list(k2i)
    tr_frac, rest = sizes[0], sizes[1:]
    tr_k, tmp_k = train_test_split(ks, test_size=1 - tr_frac, random_state=SEED)
    if len(rest) == 1:
        parts = [tr_k, tmp_k]
    else:
        v_frac = rest[0] / sum(rest)
        v_k, te_k = train_test_split(tmp_k, test_size=1 - v_frac, random_state=SEED)
        parts = [tr_k, v_k, te_k]
    return [[i for k in p for i in k2i[k]] for p in parts]


def make_vectorizers(texts):
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=60000)
    word = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, max_features=30000)
    char.fit(texts); word.fit(texts)
    return char, word


def apply_vec(char, word, texts, num):
    return hstack([char.transform(texts), word.transform(texts), csr_matrix(num)])


def main():
    canon = canon_map()
    # ── تسک A ───────────────────────────────────────────────
    A = load("quality_train.jsonl")
    textsA = [norm(r["title"]) for r in A]
    numA = nums(A)
    yA = np.array([r["label"] for r in A])
    trA, teA = split_keys(A, canon, (0.8, 0.2))
    chA, wdA = make_vectorizers([textsA[i] for i in trA])
    XA = apply_vec(chA, wdA, textsA, numA)
    mA = LogisticRegression(class_weight="balanced", max_iter=2000).fit(XA[trA], yA[trA])
    pA = mA.predict(XA[teA])
    print("=" * 58)
    print("تسک A — حذف/نگه‌داشتن")
    print(f"  accuracy={accuracy_score(yA[teA], pA):.3f}  macroF1={f1_score(yA[teA], pA, average='macro'):.3f}")
    joblib.dump({"model": mA, "char": chA, "word": wdA, "classes": list(mA.classes_)},
                ML / "model_quality.pkl")

    # ── تسک B: ۱۶ دسته مستقیم ───────────────────────────────
    # آزمایش شد: fallback آستانه‌ای `other` را بدتر کرد (F1 .19 در برابر .42)،
    # چون آگهی‌های other در ۱۵ دسته‌ی دیگر با اعتماد متوسط جذب می‌شوند نه پایین.
    # پس همان ۱۶-دسته‌ی مستقیم بهترین گزینه‌ی ساده است.
    B = load("category_train.jsonl")
    cats = sorted({r["label"] for r in B})
    c2i = {c: i for i, c in enumerate(cats)}
    textsB = [norm(r["title"]) for r in B]
    numB = nums(B)
    yB = np.array([c2i[r["label"]] for r in B])
    trB, teB = split_keys(B, canon, (0.8, 0.2))
    chB, wdB = make_vectorizers([textsB[i] for i in trB])
    XB = apply_vec(chB, wdB, textsB, numB)
    mB = LogisticRegression(class_weight="balanced", max_iter=3000).fit(XB[trB], yB[trB])
    pB = mB.predict(XB[teB])
    print("=" * 58)
    print("تسک B — ۱۶ دسته مستقیم (LogisticRegression)")
    print(f"  accuracy={accuracy_score(yB[teB], pB):.3f}  "
          f"macroF1={f1_score(yB[teB], pB, average='macro'):.3f}")
    rep = classification_report(yB[teB], pB, target_names=cats, digits=2, output_dict=True)
    for c in ("other", "accessories"):
        print(f"    {c:<12} F1={rep[c]['f1-score']:.2f} (n={int(rep[c]['support'])})")
    joblib.dump({"model": mB, "char": chB, "word": wdB, "cats": cats},
                ML / "model_category.pkl")
    print("=" * 58)
    print("مدل‌ها ذخیره شدند: exports/ml/model_quality.pkl , model_category.pkl")


if __name__ == "__main__":
    main()

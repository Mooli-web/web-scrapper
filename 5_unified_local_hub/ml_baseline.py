#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""baseline سریع CPU برای دو تسک حذف(A) و دسته(B).

ورودی: عنوان (متن فارسی) + قیمت → ویژگی‌ها:
  - TF-IDF char_wb n-gram(3,5)   (ریخت‌شناسی، مقاوم به کلمه‌ی ندیده)
  - TF-IDF word n-gram(1,2)      (کلیدواژه‌هایی مثل «مانیتور»، «گوشی»)
  - عددی: log1p(قیمت)، قیمت==0، الگوی ارقام تکراری، طول عنوان

خروجی:
  A) دودویی keep/delete  → بردار ۲بعدی (احتمال)، آستانه→{0,1}
  B) چندرده‌ای ۱۶ دسته   → بردار ۱۶بعدی (softmax)، argmax→دسته

الگوریتم پایه: Logistic Regression با class_weight=balanced.
تقسیم بر canonical_key (نه ردیف) تا تکرار یک کالا در چند فروشگاه نشت نکند.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
import numpy as np
from collections import defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, f1_score, precision_score,
                             recall_score, classification_report)
from sklearn.model_selection import train_test_split
from scipy.sparse import hstack, csr_matrix

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))
from review_queue import strip_invisible  # noqa: E402

ML = HUB / "exports" / "ml"
SEED = 42
REP_DIG = re.compile(r"^(\d)\1{5,}$")


def load(name):
    for line in (ML / name).read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def clean(t):
    return strip_invisible(t or "").lower()


def numeric(rows):
    X = []
    for r in rows:
        p = r.get("price") or 0
        X.append([np.log1p(p), 1.0 if p == 0 else 0.0,
                  1.0 if REP_DIG.match(str(p)) else 0.0, len(r["title"])])
    return np.asarray(X, dtype=float)


def feat(texts, nums):
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                           min_df=2, max_features=60000)
    word = TfidfVectorizer(analyzer="word", ngram_range=(1, 2),
                           min_df=2, max_features=30000)
    Xc, Xw = char.fit_transform(texts), word.fit_transform(texts)
    dims = {"char": Xc.shape[1], "word": Xw.shape[1], "numeric": nums.shape[1]}
    return hstack([Xc, Xw, csr_matrix(nums)]), dims, (char, word)


def split_by_key(ids, keys, y):
    key2idx = defaultdict(list)
    for i, k in enumerate(keys):
        key2idx[k].append(i)
    ukeys = list(key2idx)
    tr_k, te_k = train_test_split(ukeys, test_size=0.2, random_state=SEED)
    tr = [i for k in tr_k for i in key2idx[k]]
    te = [i for k in te_k for i in key2idx[k]]
    return tr, te


def main():
    canon = {}
    for line in (HUB / "exports/training_bundle/listings.jsonl").read_text(
            encoding="utf-8").splitlines():
        r = json.loads(line)
        canon[r["id"]] = r.get("canonical_key") or ""

    # ---- تسک A ----
    A = list(load("quality_train.jsonl"))
    yA = np.array([r["label"] for r in A])
    keysA = [canon.get(r["id"], r["id"]) for r in A]
    tr, te = split_by_key([r["id"] for r in A], keysA, yA)
    texts = [clean(r["title"]) for r in A]
    XA, dims, _ = feat(texts, numeric(A))
    m = LogisticRegression(class_weight="balanced", max_iter=2000)
    m.fit(XA[tr], yA[tr])
    p = m.predict(XA[te])
    print("=" * 60)
    print("تسک A — حذف/نگه‌داشتن (LogisticRegression, balanced)")
    print(f"  ورودی: char={dims['char']:,} + word={dims['word']:,} + num={dims['numeric']} "
          f"= {sum(dims.values()):,} بعد | خروجی: 2")
    print(f"  train={len(tr):,} test={len(te):,}")
    print(f"  accuracy={accuracy_score(yA[te], p):.3f}  macroF1={f1_score(yA[te], p, average='macro'):.3f}")
    print(f"  precision(delete)={precision_score(yA[te], p, pos_label=0):.3f}  "
          f"recall(delete)={recall_score(yA[te], p, pos_label=0):.3f}")

    # ---- تسک B ----
    B = list(load("category_train.jsonl"))
    cats = sorted({r["label"] for r in B})
    c2i = {c: i for i, c in enumerate(cats)}
    yB = np.array([c2i[r["label"]] for r in B])
    keysB = [canon.get(r["id"], r["id"]) for r in B]
    trb, teb = split_by_key([r["id"] for r in B], keysB, yB)
    textsB = [clean(r["title"]) for r in B]
    XB, dimsB, _ = feat(textsB, numeric(B))
    mb = LogisticRegression(class_weight="balanced", max_iter=3000)
    mb.fit(XB[trb], yB[trb])
    pb = mb.predict(XB[teb])
    print("=" * 60)
    print(f"تسک B — دسته‌بندی ({len(cats)} کلاس)")
    print(f"  ورودی: {sum(dimsB.values()):,} بعد | خروجی: {len(cats)}")
    print(f"  train={len(trb):,} test={len(teb):,}")
    print(f"  accuracy={accuracy_score(yB[teb], pb):.3f}  macroF1={f1_score(yB[teb], pb, average='macro'):.3f}")
    rep = classification_report(yB[teb], pb, target_names=cats, digits=2,
                                output_dict=True)
    order = sorted(cats, key=lambda c: rep[c]["f1-score"])
    print("  ضعیف‌ترین کلاس‌ها:")
    for c in order[:4]:
        print(f"     {c:<12} F1={rep[c]['f1-score']:.2f} (n_test={int(rep[c]['support'])})")
    print("  قوی‌ترین کلاس‌ها:")
    for c in order[-3:]:
        print(f"     {c:<12} F1={rep[c]['f1-score']:.2f} (n_test={int(rep[c]['support'])})")


if __name__ == "__main__":
    main()

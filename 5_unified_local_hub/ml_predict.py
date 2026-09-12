#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inference با مدل‌های ذخیره‌شده (model_quality.pkl , model_category.pkl).

استفاده:
    from ml_predict import predict
    predict("گوشی موبایل سامسونگ Galaxy S24", 45000000)
    # → {'keep': True, 'category': 'mobile', 'delete_prob': 0.03}

یا از خط فرمان:
    echo '{"title":"مانیتور سامسونگ 24 اینچ","price":8000000}' | python ml_predict.py
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
import numpy as np
import joblib
from scipy.sparse import hstack, csr_matrix

HUB = Path(__file__).resolve().parent
sys.path.insert(0, str(HUB))
from ml_baseline import normalize_text as norm  # noqa

ML = HUB / "exports" / "ml"
REP = re.compile(r"^(\d)\1{5,}$")


def _num(title, price):
    p = price or 0
    return np.array([[np.log1p(p), 1.0 if p == 0 else 0.0,
                      1.0 if REP.match(str(p)) else 0.0, len(title)]])


def _feat(bundle, title, price):
    t = [norm(title)]
    return hstack([bundle["char"].transform(t), bundle["word"].transform(t),
                   csr_matrix(_num(title, price))])


_Q = joblib.load(ML / "model_quality.pkl")
_C = joblib.load(ML / "model_category.pkl")


def predict(title: str, price: int = 0) -> dict:
    """کیفیت (حذف/نگه‌داشت) + دسته + درصد اطمینان دسته."""
    pq = _Q["model"].predict_proba(_feat(_Q, title, price))[0]
    keep_cls = list(_Q["classes"]).index(1)          # 1 = keep
    delete_prob = float(pq[1 - keep_cls])
    keep = bool(pq[keep_cls] >= 0.5)
    pc = _C["model"].predict_proba(_feat(_C, title, price))[0]
    ci = int(pc.argmax())
    cat = _C["cats"][ci]
    cat_conf = float(pc[ci])
    # دومین دسته‌ی محتمل — برای وقتی اطمینان پایین است و انسان باید تصمیم بگیرد
    order = pc.argsort()[::-1]
    second = _C["cats"][int(order[1])] if len(order) > 1 else ""
    return {"keep": keep, "category": cat, "category_conf": round(cat_conf, 3),
            "second": second, "delete_prob": round(delete_prob, 3)}


if __name__ == "__main__":
    if len(sys.argv) > 1:                          # آرگومان: عنوان [قیمت]
        print(json.dumps(predict(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0),
                         ensure_ascii=False))
    else:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            print(json.dumps(predict(r.get("title", ""), r.get("price", 0)), ensure_ascii=False))

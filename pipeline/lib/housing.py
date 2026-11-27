"""아파트 실거래 건별 원자료(data/raw/econ/housing/*.csv, 읽기만) -> 시군구별 거래 값 배열.

원자료: 국토교통부 실거래가 공개시스템 내려받기 CSV (CP949). 앞에 안내문 줄이 있고 "NO" 로 시작하는 줄이 머리글이다.
  매매: 시군구, 전용면적(㎡), 거래금액(만원), 해제사유발생일 …
  전월세: 시군구, 전월세구분(전세/월세), 보증금(만원), 월세금(만원) …

세는 규칙 (원자료 행 하나는 아래 중 정확히 하나에 든다)
  매매: 포함 / 해제(해제사유발생일이 있는 거래) / 주소 대응 실패 / 값 오류(금액·면적을 숫자로 읽지 못함)
  전월세: 전세 포함 / 월세(전세가 아님) / 주소 대응 실패 / 값 오류
빈 칸을 0 으로 읽지 않는다. 숫자로 읽지 못하면 값 오류로 센다.
"""
import csv
import glob
import hashlib
import json
import os
import re

import numpy as np

from .common import build, raw

SALE_COLS = ("시군구", "전용면적(㎡)", "거래금액(만원)", "해제사유발생일")
LEASE_COLS = ("시군구", "전월세구분", "보증금(만원)", "월세금(만원)")


def _num(s):
    s = (s or "").replace(",", "").strip()
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _read(path):
    with open(path, encoding="cp949", newline="") as f:
        lines = f.read().splitlines()
    k = next((i for i, l in enumerate(lines) if l.startswith('"NO"')), None)
    if k is None:
        raise ValueError(f"머리글 줄(NO …)을 찾지 못함: {path}")
    rows = list(csv.reader(lines[k:]))
    return rows[0], rows[1:]


def files():
    d = raw("econ", "housing")
    sale = sorted(glob.glob(os.path.join(d, "molit-apartment-sale-*.csv")))
    lease = sorted(glob.glob(os.path.join(d, "molit-apartment-lease-*.csv")))
    month = lambda p: re.search(r"(\d{4}-\d{2})\.csv$", p).group(1)  # noqa: E731
    return {month(p): p for p in sale}, {month(p): p for p in lease}


def load(resolver):
    """-> dict(months=[…], sale={code: {'per_m2': arr, 'price': arr}}, jeonse={code: arr}, counts={…}, unit_of={code: [codes]})

    단위는 resolver 가 돌려준 코드 집합이다. 원자료가 현재 이름을 쓰므로 거의 모두 시군구 하나다.
    결과를 data/build/housing_cache.npz 에 원자료 파일 크기·수정 시각 열쇠로 저장해 두고 다시 쓴다.
    """
    sale_f, lease_f = files()
    months = sorted(set(sale_f) & set(lease_f))
    key_src = json.dumps([(os.path.basename(p), os.path.getsize(p), int(os.path.getmtime(p)))
                          for p in list(sale_f.values()) + list(lease_f.values())])
    key = hashlib.sha1(key_src.encode()).hexdigest()
    cache = build("housing_cache.npz")
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=False)
        if str(z["key"]) == key:
            meta = json.loads(str(z["meta"]))
            out = {"months": meta["months"], "counts": meta["counts"], "units": meta["units"], "sale": {}, "jeonse": {}}
            for u in meta["units"]:
                out["sale"][u] = {"per_m2": z[f"s_m2_{u}"], "price": z[f"s_p_{u}"]}
                out["jeonse"][u] = z[f"j_{u}"]
            return out

    cache_res = {}

    def unit(text):
        if text not in cache_res:
            r = resolver.resolve(text)
            cache_res[text] = "+".join(sorted(r["codes"])) if r else None
        return cache_res[text]

    counts = {"sale": {"rows": 0, "included": 0, "cancelled": 0, "unmapped": 0, "bad_value": 0, "by_month": {}},
              "lease": {"rows": 0, "jeonse": 0, "monthly": 0, "unmapped": 0, "bad_value": 0, "by_month": {}}}
    sale, jeon = {}, {}
    unmapped_names = {}
    for m in months:
        hdr, rows = _read(sale_f[m])
        ix = [hdr.index(c) for c in SALE_COLS]
        cs = counts["sale"]
        cs["by_month"][m] = len(rows)
        for r in rows:
            cs["rows"] += 1
            u = unit(r[ix[0]])
            if u is None:
                cs["unmapped"] += 1
                unmapped_names[r[ix[0]]] = unmapped_names.get(r[ix[0]], 0) + 1
                continue
            cancel = (r[ix[3]] or "").strip()
            if cancel not in ("", "-"):
                cs["cancelled"] += 1
                continue
            area, price = _num(r[ix[1]]), _num(r[ix[2]])
            if area is None or price is None or area <= 0:
                cs["bad_value"] += 1
                continue
            cs["included"] += 1
            d = sale.setdefault(u, ([], []))
            d[0].append(price / area)
            d[1].append(price)
        hdr, rows = _read(lease_f[m])
        ix = [hdr.index(c) for c in LEASE_COLS]
        cl = counts["lease"]
        cl["by_month"][m] = len(rows)
        for r in rows:
            cl["rows"] += 1
            u = unit(r[ix[0]])
            if u is None:
                cl["unmapped"] += 1
                unmapped_names[r[ix[0]]] = unmapped_names.get(r[ix[0]], 0) + 1
                continue
            kind = (r[ix[1]] or "").strip()
            if kind != "전세":
                cl["monthly"] += 1
                continue
            dep = _num(r[ix[2]])
            if dep is None:
                cl["bad_value"] += 1
                continue
            cl["jeonse"] += 1
            jeon.setdefault(u, []).append(dep)
    counts["unmapped_names"] = dict(sorted(unmapped_names.items(), key=lambda kv: -kv[1])[:30])
    units = sorted(set(sale) | set(jeon))
    arrs = {"key": np.array(key), "meta": np.array(json.dumps({"months": months, "counts": counts, "units": units},
                                                                ensure_ascii=False))}
    out = {"months": months, "counts": counts, "units": units, "sale": {}, "jeonse": {}}
    for u in units:
        s = sale.get(u, ([], []))
        out["sale"][u] = {"per_m2": np.array(s[0], float), "price": np.array(s[1], float)}
        out["jeonse"][u] = np.array(jeon.get(u, []), float)
        arrs[f"s_m2_{u}"] = out["sale"][u]["per_m2"]
        arrs[f"s_p_{u}"] = out["sale"][u]["price"]
        arrs[f"j_{u}"] = out["jeonse"][u]
    np.savez_compressed(cache, **arrs)
    return out


def summarize(H, codes):
    """codes(현재 시군구 코드 집합)를 빈틈없이 덮는 단위들의 거래를 모은 전체 중위값. 단위가 걸치면(일부만 포함) None."""
    codes = set(codes)
    per, price, dep = [], [], []
    for u in H["units"]:
        us = set(u.split("+"))
        if us <= codes:
            per.append(H["sale"][u]["per_m2"])
            price.append(H["sale"][u]["price"])
            dep.append(H["jeonse"][u])
        elif us & codes:
            return None
    per = np.concatenate(per) if per else np.array([])
    price = np.concatenate(price) if price else np.array([])
    dep = np.concatenate(dep) if dep else np.array([])
    return {
        "sale_per_m2": round(float(np.median(per)), 1) if len(per) else None,
        "sale_median": round(float(np.median(price)), 1) if len(price) else None,
        "jeonse_median": round(float(np.median(dep)), 1) if len(dep) else None,
        "trades": int(len(price)), "jeonse_trades": int(len(dep)),
    }

"""인구 지표: 5세 계급 배열에서 계산한다. 모든 '평균·중위 연령'은 계급 중간값으로 낸 추정치다."""
import glob
import os
import re

from . import jumin
from .common import raw

AGE_MID = jumin.AGE_MID


def add(a, b):
    return [x + y for x, y in zip(a, b)]


def empty():
    return {"total": 0, "male": [0] * 21, "female": [0] * 21, "ages": [0] * 21}


def merge(recs):
    out = empty()
    for r in recs:
        out["total"] += r["total"]
        out["male"] = add(out["male"], r["male"])
        out["female"] = add(out["female"], r["female"])
        out["ages"] = add(out["ages"], r["ages"])
    return out


def indicators(p):
    """-> dict. 인구가 0이면 비율 지표는 None (자료 없음)."""
    t = p["total"]
    a, f, m = p["ages"], p["female"], p["male"]
    under15 = sum(a[0:3])
    working = sum(a[3:13])
    over65 = sum(a[13:])
    w2039 = sum(f[4:8])
    m2039 = sum(m[4:8])
    if t == 0:
        return {"total": 0, "mean_est": None, "median_est": None, "under15": None, "working": None,
                "over65": None, "women_20_39": None, "extinction_index": None, "sex_ratio_20_39": None,
                "n_over65": 0, "n_women_20_39": 0, "n_under15": 0}
    mean = sum(n * x for n, x in zip(a, AGE_MID)) / t
    # 중위: 누적 비율이 50%를 넘는 계급 안에서 선형 보간
    half, cum, median = t / 2, 0, None
    for k, n in enumerate(a):
        if n and cum + n >= half:
            lo = 5 * k
            median = lo + 5 * (half - cum) / n
            break
        cum += n
    return {
        "total": t,
        "mean_est": mean, "median_est": median,
        "under15": 100 * under15 / t, "working": 100 * working / t, "over65": 100 * over65 / t,
        "women_20_39": 100 * w2039 / t,
        "extinction_index": (w2039 / over65) if over65 else None,
        "sex_ratio_20_39": (100 * m2039 / w2039) if w2039 else None,
        "n_over65": over65, "n_women_20_39": w2039, "n_under15": under15,
    }


def extinction_stage(v):
    """한국고용정보원식 5단계 구분 (명세 §5): 1.5 이상, 1.0–1.5, 0.5–1.0, 0.2–0.5, 0.2 미만."""
    if v is None:
        return None
    if v >= 1.5:
        return "매우 낮음"
    if v >= 1.0:
        return "보통"
    if v >= 0.5:
        return "주의"
    if v >= 0.2:
        return "소멸위험"
    return "소멸 고위험"


def latest_files():
    """-> (ym, sgg 파일, emd 파일 또는 None, 전국 파일)"""
    d = raw("population")
    sgg = sorted(glob.glob(os.path.join(d, "jumin_age5_sgg_??????.csv")))
    # 12월이 아닌 최신 월 파일을 기준 시점으로 (과거 12월 파일과 구분)
    latest = sgg[-1]
    ym = re.search(r"(\d{6})\.csv$", latest).group(1)
    emd = os.path.join(d, f"jumin_age5_emd_{ym}.csv")
    nat = os.path.join(d, f"jumin_age5_nation_{ym}.csv")
    return ym, latest, emd if os.path.exists(emd) else None, nat if os.path.exists(nat) else None


def dong_population(f_emd, dongs):
    """읍면동 인구를 경계의 행정동(adm_cd2)에 붙인다.

    - 코드가 같으면 그대로.
    - 출장소 행(경계에 없는 코드)은 상위 읍면에 더한다: 같은 시군구에서 이름이 출장소 이름의 앞부분인 동,
      없으면 같은 시군구에서 코드가 바로 아래인 동. 원자료에서 출장소 인구는 상위 읍면 행에 들어 있지 않다
      (읍면동 행의 시군구별 합이 시군구 행과 같음을 확인).
    - 인구 0인 폐지 동 행은 버린다.
    -> (dong 코드 -> rec, 보고 목록)
    """
    _, erecs = jumin.read(f_emd)
    rows = {}
    for r in jumin.emd_rows(erecs):
        if r["code"] in rows and rows[r["code"]]["total"] != r["total"]:
            raise ValueError(f"읍면동 중복 행 값이 다름: {r['code']}")
        rows[r["code"]] = r
    by_code = {d["code"]: d for d in dongs}
    norm = lambda s: s.replace(" ", "")  # noqa: E731
    out = {d["code"]: empty() for d in dongs}
    report = []
    for c, r in sorted(rows.items()):
        if c in by_code:
            out[c] = merge([out[c], r])
            continue
        if r["total"] == 0:
            report.append({"code": c, "name": r["name"], "total": 0, "to": None, "how": "인구 0, 버림"})
            continue
        same = [d for d in dongs if d["sgg"] == c[:5]]
        nm = norm(r["name"])
        pref = [d for d in same if nm.startswith(norm(d["name"])) and nm != norm(d["name"])]
        if pref:
            tgt, how = max(pref, key=lambda d: len(d["name"])), "이름 앞부분"
        else:
            lower = [d for d in same if d["code"] < c]
            if not lower:
                raise ValueError(f"상위 동을 찾지 못한 읍면동 행: {c} {r['name']}")
            tgt, how = max(lower, key=lambda d: d["code"]), "바로 아래 코드"
        out[tgt["code"]] = merge([out[tgt["code"]], r])
        report.append({"code": c, "name": r["name"], "total": r["total"], "to": tgt["code"], "to_name": tgt["name"], "how": how})
    return out, report


def year_files():
    d = raw("population")
    out = {}
    for y in range(2020, 2026):
        p = os.path.join(d, f"jumin_age5_sgg_{y}12.csv")
        if os.path.exists(p):
            out[y] = p
    return out

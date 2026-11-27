"""6단계 (명세 docs/SPEC_PHASE6.md): 렌즈 정리·건강 지수, 지도 아이콘 배율 단계, 순위 보고서 자료, 연구대학.

build_layers5e.py 다음, build_sources.py 앞에 돌린다. 같은 입력으로 다시 돌려도 결과가 같다.

1. 렌즈 (B1): 렌즈 막대의 렌즈를 6묶음으로 줄인다. 뺀 렌즈의 값은 지우지 않고 시군구 값(world.counties 순서)으로
   lenses.json 의 retired_values 에 남긴다(칸 배열은 싣지 않는다). 칸 값 렌즈(밭·침엽수림)는 값이 있는 육지 칸의 시군구 평균,
   인구 렌즈(유소년·평균연령·청년 성비)는 시군구 주민등록 값(data/build/sgg_stats.json)이다.
   건강 지수 = 100 − 10 × (흡연율 z + 비만율 z + 우울감 z − 주관적 건강 양호 z) ÷ 4, z 는 네 값이 모두 있는 시군구끼리 낸다.
   처음 볼 때 5e 결과를 data/build/lenses_pre6.json 에 남기고, 그 뒤로는 그 사본에서 시작한다.
2. 배율 단계 (B3): 층 항목마다 tier(0 전국, 1 중간, 2 가까이)를 붙이고 규칙 문장을 wonders.json 의 zoom 에 넣는다.
3. 순위 보고서 (A1): 상단 막대 수치 8개의 정의·구성·시도 순위·도시 순위를 nation.json 의 reports 에 넣는다.
4. 연구대학 (A6): data/build/layers/universities.csv 가 있으면 연구비 상위 20개 대학을 지식 불가사의로 놓는다. 없으면 건너뛴다.
"""
import collections
import csv
import math
import os
import re
import shutil
import sys

import numpy as np

from lib import profile as PRF
from lib.common import build, load_json, rnd, save_json, site

PHASE = "6"
SNAP_LENSES = build("lenses_pre6.json")
UNIV_CSV = os.environ.get("KOREACIV_UNIV_CSV") or build("layers", "universities.csv")
UNIV_N = 20
PER_CAPITA_MIN_POP = 100000
Z_MID, Z_NEAR = 2.0, 3.2

GROUPS = [("people", "사람"), ("living", "살림"), ("industry", "산업"), ("daily", "일상"), ("learn", "배움·신앙"), ("land", "땅")]
KEEP = {
    "people": ["density", "growth", "fertility", "over65", "extinction", "foreign", "veterans"],
    "living": ["gdp_pc", "wage", "home", "jeonse", "employment", "fiscal", "assistance"],
    "industry": ["top_industry", "manufacturing_share", "export_pc"],
    "daily": ["single", "owner", "long_commute", "doctors", "pm25", "health"],
    "learn": ["degree", "academies", "religion", "religion_top"],
    "land": ["forest", "cropland", "paddy_share", "built", "heritage", "disaster"],
}
# 렌즈 막대에서 뺀 렌즈 -> 가장 가까운 남은 렌즈 (옛 공유 링크와 툴팁 묶음에 쓴다)
RETIRED = {"under15": "over65", "age": "over65", "sex_ratio": "extinction", "migration": "growth", "farm_share": "top_industry",
           "smoking": "health", "obesity": "health", "depression": "health", "health_good": "health",
           "paddy": "paddy_share", "field_share": "cropland", "conifer": "forest"}
# 공개판에서 빼는 렌즈 (lib/profile.py EXCLUDE): id -> (묶음 id, 옛 링크가 갈 남은 렌즈 또는 None)
PUBLIC_REMOVED = {"home": ("housing", None), "jeonse": ("housing", None)}
if PRF.PUBLIC:
    KEEP = {g: [i for i in ids if i not in PUBLIC_REMOVED] for g, ids in KEEP.items()}
    RETIRED = {k: v for k, v in RETIRED.items() if k not in PUBLIC_REMOVED}
HEALTH_PARTS = [("smoking", 1), ("obesity", 1), ("depression", 1), ("health_good", -1)]


def log(*a):
    print("[phase6]", *a, flush=True)


# =====================================================================
# 1. 렌즈
# =====================================================================
def build_lenses(world):
    cur = load_json(site("lenses.json"))
    if cur.get("phase") == PHASE:
        if not os.path.exists(SNAP_LENSES):
            raise RuntimeError("lenses.json 이 이미 6단계 결과인데 사본이 없음 — build_lenses.py 부터 다시 돌린다")
        L = load_json(SNAP_LENSES)
    else:
        shutil.copyfile(site("lenses.json"), SNAP_LENSES)
        L = cur
    by = {l_["id"]: l_ for l_ in L["lenses"]}
    want = [i for g, _ in GROUPS for i in KEEP[g] if i != "health"]
    missing = [i for i in want + list(RETIRED) if i not in by]
    if missing:
        raise ValueError(f"5e 렌즈에 없는 id: {missing}")
    extra = [i for i in by if i not in want and i not in RETIRED]
    if extra:
        raise ValueError(f"6단계 표에 없는 렌즈: {extra} — KEEP 또는 RETIRED 에 넣는다")
    counties = world["counties"]
    K = len(counties)
    owner = np.array(world["owner"])
    county = np.array(world["county"])
    stats = load_json(build("sgg_stats.json"))["sgg"]

    # ---- 건강 지수 ----
    cols = []
    for lid, sign in HEALTH_PARTS:
        v = by[lid]["by_county"]
        if len(v) != K:
            raise ValueError(f"{lid}.by_county 길이 {len(v)} != {K}")
        cols.append((lid, sign, v))
    full = [k for k in range(K) if all(v[k] is not None for _, _, v in cols)]
    z = {}
    for lid, sign, v in cols:
        a = np.array([v[k] for k in full], float)
        mu, sd = float(a.mean()), float(a.std())
        z[lid] = {k: sign * (v[k] - mu) / sd for k in full}
    hv = [None] * K
    for k in full:
        hv[k] = rnd(100 - 10 * sum(z[lid][k] for lid, _, _ in cols) / len(cols), 1)
    arr = np.array([x for x in hv if x is not None])
    lo, hi = float(np.percentile(arr, 2)), float(np.percentile(arr, 98))
    span = max(abs(100 - lo), abs(hi - 100))
    definition = ("건강 지수 = 100 − 10 × (흡연율 z점수 + 비만율 z점수 + 우울감 경험률 z점수 − 주관적 건강 양호율 z점수) ÷ 4. "
                  "z점수는 네 값이 모두 있는 시군구끼리의 평균과 표준편차(가중치 없음)로 낸다. 100 이 그 시군구들의 평균이고 높을수록 건강 쪽이다. "
                  "네 값 가운데 하나라도 없는 시군구는 자료 없음. 네 구성 값은 질병관리청 지역사회건강조사 2025 연령표준화율이며 패널과 툴팁에 그대로 보인다.")
    health = {"id": "health", "group": "daily", "name": "건강 지수", "emoji": "❤️", "unit": "지수", "format": "f1",
              "scale": "diverging", "center": 100, "ramp": ["#8e2a35", "#d4704f", "#f2c69c", "#f3f0e8", "#b7dcc0", "#5aa577", "#1d6b45"],
              "higher_is": "good", "basis": "거주지 (표본조사)", "vintage": "2025",
              "source": "질병관리청 지역사회건강조사 (2025) — 흡연율·비만율·우울감 경험률·주관적 건강 양호율로 계산",
              "description": definition, "definition": definition, "components": [p for p, _ in HEALTH_PARTS],
              "by_county": hv, "coverage": {"counties_with_value": len(full), "counties": K},
              "domain": [rnd(100 - span, 1), rnd(100 + span, 1)], "phase": "6"}
    # 감사 01: 네 구성 값이 모두 같은 공표 단위(시 전체·개편 전 구)의 값이면 건강 지수도 그 단위의 값이다
    comp_units = [{tuple(u["counties"]): u for u in by[lid].get("units", [])} for lid, _ in HEALTH_PARTS]
    common = [comp_units[0][k] for k in comp_units[0] if all(k in cu for cu in comp_units[1:]) and hv[k[0]] is not None]
    if common:
        health["units"] = [dict(u, label=u["label"] + "으로 계산") for u in common]
        health["units_note"] = ("네 구성 값이 시 전체·개편 전 단위로만 공표된 곳은 건강 지수도 그 단위의 값으로 계산해 구마다 같은 값을 칠했다: "
                                + ", ".join(u["label"] for u in common) + ".")

    # ---- 뺀 렌즈의 시군구 값 ----
    land_cells = world["cover_share"]["land_cells"]
    ret_items = []
    for lid, near in RETIRED.items():
        l_ = by[lid]
        if l_.get("by_county") is not None:
            vals, level = list(l_["by_county"]), "시군구 값 (렌즈와 같음)"
        elif lid in ("under15", "age", "sex_ratio"):
            key = {"under15": "under15", "age": "mean_est", "sex_ratio": "sex_ratio_20_39"}[lid]
            vals = [rnd(stats[c["code"]][key], 1) if c["code"] in stats and stats[c["code"]].get(key) is not None else None for c in counties]
            level = "시군구 주민등록 값 (칸 렌즈는 읍면동 값을 칸에 내린 것이라 시군구 값과 조금 다르다)"
        elif l_.get("land_values") is not None:
            s_ = collections.defaultdict(float)
            n_ = collections.Counter()
            for t, v in enumerate(l_["land_values"]):
                if v is None:
                    continue
                k = int(county[land_cells[t]])
                s_[k] += v
                n_[k] += 1
            vals = [rnd(s_[k] / n_[k], 1) if n_[k] else None for k in range(K)]
            level = "값이 있는 육지 칸의 시군구 평균 (칸 넓이가 같아 넓이 가중 평균과 같다)"
        else:
            raise ValueError(f"{lid}: 시군구 값을 만들 수 없음")
        desc = l_["description"].replace("네 지표를 하나의 종합 지수로 합치지 않는다. ", "6단계부터 네 지표로 낸 '건강 지수' 렌즈가 따로 있다. ")
        ret_items.append({"id": lid, "near": near, "name": l_["name"], "emoji": l_["emoji"], "unit": l_["unit"], "format": l_["format"],
                          "scale": l_["scale"], "basis": l_.get("basis"), "vintage": l_.get("vintage") or L.get("vintage"),
                          "source": l_["source"], "description": desc, "level": level, "categories": l_.get("categories"),
                          "values": vals, "counties_with_value": sum(1 for v in vals if v is not None)})
        if l_.get("by_county") is not None and l_.get("units"):
            ret_items[-1]["units"] = l_["units"]
            ret_items[-1]["units_note"] = l_["units_note"]
    for it in ret_items:
        if it["categories"] is None:
            it.pop("categories")

    # ---- 새 렌즈 목록 ----
    by["health"] = health
    by["paddy_share"] = dict(by["paddy_share"], name="논")
    new = []
    for g, _ in GROUPS:
        for i in KEEP[g]:
            l_ = dict(by[i])
            l_["group"] = g
            new.append(l_)
    # 감사 18: 칸 배열 렌즈(values, 칸 수 길이)는 육지 칸 값만(land_values, world.cover_share.land_cells 순서) 싣는다.
    # 육지 밖 칸에 값이 있으면 잃는 값이 생기므로 빌드 오류. 육지 안의 실제 결측(null)은 그대로 남는다.
    land_cells = world["cover_share"]["land_cells"]
    lset = set(land_cells)
    for l_ in new:
        if "values" in l_:
            vals = l_.pop("values")
            off = [i for i, v in enumerate(vals) if v is not None and i not in lset]
            if off:
                raise ValueError(f"{l_['id']}: 육지 밖 칸 {len(off)}개에 값이 있어 land_values 로 줄일 수 없음")
            l_["land_values"] = [vals[i] for i in land_cells]
    out = {k: v for k, v in L.items() if k not in ("lenses", "groups")}
    out["phase"] = PHASE
    out["groups"] = [{"id": g, "name": n} for g, n in GROUPS]
    out["lenses"] = new
    out["retired"] = RETIRED
    if PRF.PUBLIC:
        # 공개판에서 뺀 렌즈: 옛 공유 링크가 이 id 로 들어오면 까닭을 알리고 near(있으면)로, 없으면 지형으로 보낸다
        why = {e["id"]: e for e in PRF.EXCLUDE}
        NAMES = {"home": "아파트 매매가", "jeonse": "아파트 전세가"}
        out["removed"] = {k: {"name": NAMES[k], "near": near, "excluded": eid, "reason": why[eid]["what"] + " — " + why[eid]["why"]}
                          for k, (eid, near) in PUBLIC_REMOVED.items()}
        out["removed_rule"] = ("공개판(profile public)에서 뺀 렌즈다. 값을 다른 값으로 메우지 않는다. 뺀 렌즈의 id 로 들어온 공유 링크는 까닭을 알리고 "
                               "near 가 있으면 그 렌즈로, 없으면 지형으로 보여 준다.")
    out["retired_values"] = {"order": "world.counties 순서 (시군구 256)", "items": ret_items,
                             "rule": (f"렌즈 막대를 6묶음으로 줄이며 뺀 렌즈 {len(ret_items)}개의 값은 지우지 않고 시군구 값으로 남긴다. 도시 패널(정리한 지표)과 "
                                      "관련 렌즈를 켰을 때의 툴팁에 나온다. 뺀 렌즈의 id 로 들어온 공유 링크는 가장 가까운 남은 렌즈(near)로 보낸다.")}
    out["notes"] = [n for n in L.get("notes", []) if not n.startswith("6단계")] + [
        ("6단계: 렌즈 막대는 6묶음 33종(사람 7 · 살림 7 · 산업 3 · 일상 6 · 배움·신앙 4 · 땅 6)이다. 뺀 렌즈 12개(유소년 비율·평균연령·청년 성비·순이동률·"
         "농림어업 비중·흡연·비만·우울·주관적 건강·논 비율(시군구 통계)·밭·침엽수림)의 값은 시군구 값으로 남아 도시 패널과 툴팁에 나온다.") if not PRF.PUBLIC else
        (f"6단계 (공개판): 렌즈 막대는 6묶음 {len(new)}종(" + " · ".join(f"{n} {len(KEEP[g])}" for g, n in GROUPS) + ")이다. "
         f"정리하며 렌즈 막대에서 뺀 렌즈 {len(ret_items)}개의 값은 시군구 값으로 남아 도시 패널과 툴팁에 나온다. "
         "공개판은 아파트 매매가·아파트 전세가 렌즈를 싣지 않는다(lenses.json removed)."),
        "6단계 건강 지수: " + definition]
    size = save_json(site("lenses.json"), out)
    log(f"렌즈 {len(L['lenses'])} -> {len(new)} (묶음 {len(GROUPS)}), 뺀 렌즈 {len(ret_items)}개 시군구 값, "
        f"건강 지수 시군구 {len(full)}/{K}, 평균 {float(arr.mean()):.3f}, lenses.json {size / 1e6:.2f} MB")
    return out


# =====================================================================
# 4. 연구대학 (A6) — 파일이 있을 때만
# =====================================================================
def add_universities(wonders, world, cities):
    """universities.csv -> 지식 불가사의 항목. (새 항목 수, 합친 항목 이름, 상태 문장)"""
    wonders["items"] = [i for i in wonders["items"] if not str(i.get("id", "")).startswith("w6u-")]
    for it in wonders["items"]:
        if it.get("university_merge"):
            it.pop("value_label", None)
            it["detail"] = [d for d in it.get("detail", []) if not d.startswith(("연구비 ", "주소: "))]
        for k in ("funding_won", "funding_rank", "funding_year", "university_merge"):
            it.pop(k, None)
    kk = wonders["kinds"]["knowledge"]
    kk["rule"] = re.sub(r" 6단계 연구대학:.*$", "", kk["rule"])
    if not os.path.exists(UNIV_CSV):
        st = ("연구대학 자료(data/build/layers/universities.csv)가 빌드 시점에 없어 연구비 상위 20개 대학을 지식 불가사의로 놓지 못했다. "
              "기존 지식 불가사의(과학기술원·연구기관·대학 주소 8곳)만 있다.")
        wonders["universities"] = {"status": "missing", "note": st}
        log("연구대학: 파일 없음 — 건너뜀")
        return 0, [], st
    from build_layers import World
    from lib import popstats
    from lib.address import AddressResolver, nospace
    W = World()
    resolver = AddressResolver(world, cities)
    with open(UNIV_CSV, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    need = {"rank", "name", "campus", "value_thousand_krw", "year", "address", "sido", "sigungu", "lon", "lat", "address_source_url",
            "funding_source_id", "note"}
    if rows and not need <= set(rows[0]):
        raise ValueError(f"universities.csv 열이 다름: 없는 열 {sorted(need - set(rows[0]))}")

    def fnum(s):
        s = (s or "").replace(",", "").strip()
        return None if s == "" else float(s)

    recs = []
    for r in rows:
        v = fnum(r["value_thousand_krw"])
        recs.append({**r, "won": None if v is None else int(round(v * 1000)), "rank_i": int(fnum(r["rank"])) if fnum(r["rank"]) is not None else None})
    recs = [r for r in recs if r["won"] is not None]
    recs.sort(key=lambda r: (-r["won"], r["rank_i"] or 0))
    top = recs[:UNIV_N]
    city_of_code = {s: c["id"] for c in cities for s in c["sgg"]}
    sido_name = {s["code"]: s["name"] for s in world["states"]}
    dongs = load_json(build("dongs.json"))
    _, _, f_emd, _ = popstats.latest_files()
    rec, _ = popstats.dong_population(f_emd, dongs)
    dpop = {d["code"]: rec[d["code"]]["total"] for d in dongs}

    def unit_center(codes):
        items = [(d["rx"], d["ry"], dpop.get(d["code"], 0)) for d in dongs if d["sgg"] in codes]
        own = np.nonzero(np.isin(W.code_of, list(codes)) & W.land)[0]
        tw = sum(i[2] for i in items)
        px, py = (sum(i[0] * i[2] for i in items) / tw, sum(i[1] * i[2] for i in items) / tw) if tw > 0 else W.centers[own].mean(0)
        return int(own[np.argmin(((W.centers[own] - [px, py]) ** 2).sum(1))])

    existing = {nospace(i["name"]): i for i in wonders["items"] if i["kind"] == "knowledge"}
    new, merged, fail = [], [], []
    for k, r in enumerate(top):
        rank = k + 1
        is_main = r["campus"].strip() in ("", "본교")
        nm = r["name"].strip() + ("" if is_main or r["campus"].strip() in r["name"] else f" ({r['campus'].strip()})")
        detail = [f"연구비 {r['won'] / 1e8:,.0f}억원 ({r['year']}, 원표 천원 × 1,000) · 연구비 순위 {rank}위",
                  f"주소: {r['address'] or '없음'}" + (f" — {r['address_source_url']}" if r["address_source_url"] else "")]
        if r["note"]:
            detail.append(r["note"])
        ex = existing.get(nospace(r["name"]))
        if ex is not None and is_main:
            ex.update({"funding_won": r["won"], "funding_rank": rank, "funding_year": r["year"], "university_merge": True,
                       "value_label": f"연구비 {r['won'] / 1e8:,.0f}억원 · {rank}위"})
            ex["detail"] = list(ex.get("detail", [])) + detail
            merged.append(ex["name"])
            continue
        cell, prec, codes, pf = None, None, None, None
        lon, lat = fnum(r["lon"]), fnum(r["lat"])
        res = resolver.resolve(r["address"]) if r["address"] else None
        if res is None and r["sido"]:
            res = resolver.resolve(r["sigungu"] or "", sido_hint=r["sido"])
        if lon is not None and lat is not None:
            ux, uy = W.lonlat2u(lon, lat)
            c, why = W.snap(float(ux), float(uy))
            if c is not None:
                cell, prec, codes, pf = c, "point", [W.code_of[c]], "point"
        if cell is None and res is not None:
            codes = sorted(res["codes"])
            cell, prec, pf = unit_center(codes), "county", "address"
        if cell is None:
            fail.append({"name": nm, "reason": "좌표도 주소의 시군구도 읽지 못함"})
            continue
        sd = W.sido_of_code[codes[0]]
        cid = city_of_code.get(codes[0])
        new.append({"id": f"w6u-{len(new)}", "kind": "knowledge", "name": nm, "cell": int(cell), "precision": prec, "sgg": codes, "sido": sd,
                    "city": cid, "place": f"{sido_name[sd]} {W.cname[codes[0]]}", "value": r["won"], "unit": "원", "year": r["year"],
                    "inst_kind": "대학 (연구비 상위)", "value_label": f"연구비 {r['won'] / 1e8:,.0f}억원 · {rank}위", "funding_won": r["won"], "funding_rank": rank, "funding_year": r["year"],
                    "place_from": pf, "source": r["funding_source_id"], "detail": detail})
    wonders["items"] = [i for i in wonders["items"]] + new
    st = (f"6단계 연구대학: data/build/layers/universities.csv 의 연구비(원표 천원 × 1,000) 상위 {UNIV_N}개 대학(같은 금액이면 원표 순위)을 지식 불가사의로 놓는다. "
          f"좌표가 있으면 그 칸(point), 없으면 주소의 시군구 인구 가중 중심 칸(county). 기존 지식 불가사의와 이름이 같은 대학은 하나로 합친다"
          f"({', '.join(merged) or '없음'}). 새로 놓은 대학 {len(new)}곳, 놓지 못한 대학 {len(fail)}곳. 기준 연도 "
          f"{', '.join(sorted({r['year'] for r in top}))}. 좌표로 놓은 대학 {sum(1 for i in new if i['precision'] == 'point')}곳 — "
          f"나머지는 캠퍼스 자리가 아니라 자치구·시군구 중심 칸을 가리킨다. 전국 배율에는 연구비 상위 {UNIV_NATIONAL}개 대학만 그리고 나머지 대학은 중간 배율부터 그린다. "
          f"같은 도시의 같은 칸·이웃 칸 대학은 '대학 N' 표지 하나로 묶는다(배율에 따른 표시 규칙).")
    kk["rule"] = kk["rule"] + " " + st
    kk["placed"] = sum(1 for i in wonders["items"] if i["kind"] == "knowledge")
    kk["count"] = kk.get("count", 0)
    kk["missing"] = [m for m in kk.get("missing", []) if not m.get("phase6")] + [dict(m, phase6=True) for m in fail]
    srcs = sorted({r["funding_source_id"] for r in top if r["funding_source_id"]})
    kk["source"] = [s for s in kk.get("source", []) if not s.get("phase6")] + [
        {"key": s, "title": "대학 연구비 (universities.csv)", "publisher": "대학알리미", "file": "layers/universities.csv", "phase6": True} for s in srcs]
    wonders["universities"] = {"status": "ok", "note": st, "top": [{"rank": k + 1, "name": r["name"], "campus": r["campus"], "won": r["won"],
                                                                     "year": r["year"]} for k, r in enumerate(top)],
                               "merged": merged, "failed": fail, "source_ids": srcs}
    log(f"연구대학: 상위 {len(top)} — 새 항목 {len(new)}, 합침 {merged}, 실패 {fail}")
    return len(new), merged, st


# =====================================================================
# 2. 배율 단계
# =====================================================================
NATIONAL_TOP = {"power_coal": 5, "power_gas": 5, "power_oil": 5, "power_hydro": 5, "power_solar": 5, "power_wind": 5,
                "industrial_national": 10, "trade_port": 8, "airport": 6}
NATIONAL_ALL = {"nuclear", "national_park"}
NEAR_ONLY = {"gi", "port"}
UNIV_NATIONAL = 5          # 전국 배율에 그리는 대학: 연구비 상위 5
# 그리기 우선순위: 이 종류를 먼저 놓고(깃발·다른 아이콘에 밀려 숨지 않게), 나머지는 기존 종류 순서(layers.js KINDS.pri)
DRAW_FIRST = ["nuclear"]
# 7b (site_r3 #1): 원전 다음 우선군 — 전국 단계(tier 0) 공항·무역항. 깃발은 밀지 않고 아이콘만 가까운 빈 칸으로 옮긴다
DRAW_SECOND = ["airport", "trade_port"]
# 한 화면 배치 예산 (전국 배율 z < z_max 에서만). second_* 는 우선군 아이콘을 옮길 수 있는 화면 거리 (아이콘 반지름의 배수, 최소 px)
# 명세(site_r3)는 데스크톱 아이콘 52개였으나, 전국 첫 화면의 깃발+아이콘 수가 고치기 전(1280×800 깃발 15 + 아이콘 24)보다 늘지 않게 24개로 둔다
PLACE_BUDGET = {"z_max": 2.0, "flags_desktop": 24, "flags_mobile": 12, "icons_desktop": 24, "icons_mobile": 24, "mobile_vw": 700,
                "second_ring": 2.4, "second_px": 22, "second_ring_mobile": 2.0, "second_px_mobile": 18}


def is_univ(it):
    """지식 불가사의 가운데 대학(과학기술원·정부출연연구기관이 아닌 것)"""
    return it["kind"] == "knowledge" and str(it.get("inst_kind", "")).startswith("대학")


def knowledge_groups(items, world):
    """같은 도시의 같은 칸·이웃 칸에 놓인 대학을 표지 하나로 묶는다. 보기 단계(0 전국, 1 중간·가까이)마다 따로 낸다.
    연구비가 큰 대학부터 씨앗으로 삼아, 아직 묶이지 않은 같은 도시 대학 가운데 씨앗 칸과 같은 칸이거나 이웃 칸인 것을 모은다(사슬로 잇지 않음)."""
    from lib.hexgrid import Grid
    g = world["grid"]
    G = Grid(g["cols"], g["rows"], g["radius"])
    univ = [it for it in items if is_univ(it)]
    for it in univ:
        it.pop("grouped", None)
    city_name = {}
    groups = []
    for view, tiers in ((0, [0]), (1, [1, 2])):
        pool = sorted([u for u in univ if u["tier"] <= view], key=lambda u: (-(u.get("funding_won") or 0), u["id"]))
        taken = set()
        for seed in pool:
            if seed["id"] in taken:
                continue
            near = {seed["cell"], *G.neighbors(seed["cell"])}
            mem = [u for u in pool if u["id"] not in taken and u.get("city") == seed.get("city") and u["cell"] in near]
            taken.add(seed["id"])
            if len(mem) < 2:
                continue
            gid = f"w6g-{view}-{len(groups)}"
            for u in mem:
                taken.add(u["id"])
                u.setdefault("grouped", {}).update({str(t): gid for t in tiers})
            places = sorted({u["place"] for u in mem})
            groups.append({"id": gid, "kind": "knowledge", "group": True, "view_tiers": tiers, "tier": tiers[0], "name": f"대학 {len(mem)}",
                           "members": [u["id"] for u in mem], "cell": seed["cell"], "city": seed.get("city"), "sido": seed["sido"],
                           "sgg": sorted({c for u in mem for c in u["sgg"]}), "precision": "county",
                           "place": " · ".join(places), "funding_won_sum": sum(u.get("funding_won") or 0 for u in mem),
                           "funding_year": seed.get("funding_year")})
    return groups


def assign_tiers(objs, world):
    items = [it for o in objs for it in o["items"]]
    by_kind = collections.defaultdict(list)
    for it in items:
        by_kind[it["kind"]].append(it)
    for kind, lst in by_kind.items():
        if any(it.get("rank") is not None for it in lst) and kind != "world_heritage":
            order = sorted(lst, key=lambda it: (it.get("rank") if it.get("rank") is not None else 1e9))
        else:
            order = sorted(lst, key=lambda it: -(it["value"] if isinstance(it.get("value"), (int, float)) else -1))
        half = math.ceil(len(order) / 2)
        univ_top = {u["id"] for u in sorted((u for u in lst if is_univ(u)), key=lambda u: (-(u.get("funding_won") or 0), u["id"]))[:UNIV_NATIONAL]}
        for r, it in enumerate(order):
            if kind in NATIONAL_ALL:
                t = 0
            elif kind == "knowledge":
                # 과학기술원·정부출연연구기관은 전국부터, 대학은 연구비 상위 5만 전국, 나머지 대학은 중간부터
                t = 0 if not is_univ(it) or it["id"] in univ_top else 1
            elif kind == "world_heritage":
                t = 0 if it.get("rank") == 1 else 2
            elif kind == "station":
                t = 1 if it.get("hsr") else 2
            elif kind in NEAR_ONLY:
                t = 2
            elif kind in NATIONAL_TOP and r < NATIONAL_TOP[kind]:
                t = 0
            elif r < half:
                t = 1
            else:
                t = 2
            it["tier"] = t
    groups = knowledge_groups(items, world)

    def drawn(t):
        c = collections.Counter(it["kind"] for it in items if it["tier"] <= t and str(t) not in it.get("grouped", {}))
        c.update(g_["kind"] for g_ in groups if t in g_["view_tiers"])
        return c
    counts = {t: drawn(t) for t in (0, 1, 2)}
    n_inst = sum(1 for it in items if it["kind"] == "knowledge" and not is_univ(it))
    n_univ = sum(1 for it in items if is_univ(it))
    g0 = [g_ for g_ in groups if 0 in g_["view_tiers"]]
    g1 = [g_ for g_ in groups if 1 in g_["view_tiers"]]
    group_rule = (f"대학 묶음: 대학은 좌표가 없어 주소의 자치구·시군구 인구 가중 중심 칸에 놓였다(캠퍼스 자리가 아니다). 같은 도시에서 같은 칸이나 이웃 칸에 놓인 대학은 "
                  f"연구비가 큰 대학부터 씨앗으로 삼아 씨앗 칸과 그 이웃 칸의 대학을 '대학 N' 표지 하나로 묶고(사슬로 잇지 않음), 표지를 누르면 묶인 대학과 연구비가 나온다. "
                  f"표지는 연구비가 가장 큰 대학의 칸에 둔다. 중간 배율부터 묶음 표지가 깃발에 가리면 원전처럼 가까운 빈 칸으로 옮겨 선을 잇고(깃발은 밀지 않음), 빈 칸이 없으면 그 배율에서 숨긴다. "
                  f"전국 배율 묶음 {len(g0)}개(대학 {sum(len(g_['members']) for g_ in g0)}곳), 중간·가까이 배율 묶음 {len(g1)}개(대학 {sum(len(g_['members']) for g_ in g1)}곳).")
    b = PLACE_BUDGET
    SECOND_N = {k: sum(1 for it in items if it["kind"] == k and it["tier"] == 0) for k in DRAW_SECOND}
    prio_rule = ("그리기 우선순위 (한 가지 배치 규칙): ① 원전 — 먼저 놓고 숨기지 않는다. 원전 자리가 도시 깃발과 겹치면 깃발이 좌우로 비켜 선다(깃대가 깃발 안에 남는 만큼만, 위아래로는 옮기지 않음). "
                 "그래도 깃발 글씨·도시 점·먼저 놓인 아이콘·같은 칸의 대표 아이콘과 겹치면 이웃 칸을 겹겹이 넓혀 가며 가장 가까운 빈 칸으로 옮기고(다른 깃발 가까이나 선이 깃발 글씨를 지나는 칸은 덜 고름) 원래 칸까지 가는 선과 점을 그린다. "
                 f"② 전국 단계(tier 0) 공항 {SECOND_N['airport']}곳·무역항 {SECOND_N['trade_port']}곳 — 원전 다음에 놓고 숨기지 않는다. 깃발은 밀지 않는다. 제자리가 깃발 글씨·도시 점·먼저 놓인 아이콘과 겹치면 "
                 f"화면 거리로 아이콘 반지름의 {b['second_ring']}배(최소 {b['second_px']}px, 좁은 화면 {b['second_ring_mobile']}배·{b['second_px_mobile']}px) 안에서 가장 가까운 빈 칸으로 옮기고(무역항은 바다 칸을 먼저 고름) 원래 칸까지 선과 점을 그린다. "
                 "그 안에 빈 칸이 없으면 원전과 같은 넓이까지 찾고, 그래도 없으면 제자리에 그린다. "
                 "③ 그 밖의 아이콘 — 종류 순서(세계유산 → 지식·국립공원 → 국가유산 밀집지·수출 거점 → 국가산단·석탄·가스·유류·수력·주력 업종 → 어항·댐·태양광·풍력·쌀·한우·돼지 → 광산·지리적표시 → 철도역, "
                 f"같은 순서 안에서는 값이 큰 것부터)로 놓되 깃발과 겹치면 그 배율에서 숨기고, 전국 배율(z < {b['z_max']})에서는 화면에 아이콘이 데스크톱 {b['icons_desktop']}개·좁은 화면(폭 {b['mobile_vw']}px 이하) {b['icons_mobile']}개가 차면 더 그리지 않는다. "
                 f"도시 깃발은 선택한 도시 → 수도·도청 소재지(인구 순) → 인구 50만 이상 → 그 밖(배율에 따른 최소 인구 이상) 순으로 놓고 앞선 깃발과 겹치면 숨긴다. 전국 배율에서는 데스크톱 {b['flags_desktop']}개·좁은 화면 {b['flags_mobile']}개까지(선택한 도시는 늘 그림). "
                 "원전·우선 아이콘 자리에 비켜 설 곳이 없으면 수도·도청 소재지·인구 50만 이상이 아닌 도시의 깃발은 그 배율에서 숨는다. "
                 "시도 이름은 지형·경계 위, 아이콘·깃발 아래 층에 반투명 명조로 새긴다. 깃발·원전·우선 아이콘과 덜 겹치는 가까운 자리로 옮기되, 시도 이름 때문에 깃발이나 아이콘을 숨기지 않는다. "
                 "광역시·특별시·세종처럼 같은 이름의 도시 깃발이 있는 시도는 이름을 따로 새기지 않는다. 강·호수 이름표는 깃발·아이콘과 겹치는 자리에는 그리지 않는다(강은 세 지점 가운데 빈 곳). "
                 "원전·공항·무역항 위치는 원래도 항목마다 적힌 위치 정밀도(대개 소재 시군구의 대표 위치)이며, 옮겨 그린 아이콘은 툴팁에 '깃발과 겹쳐 옆 칸에 표시'라고 적는다.")
    def unlisted(t):
        # 공개판: 빼는 층(한우·광산, lib/profile.py EXCLUDE)의 이름을 규칙 문장에서 뺀다 — 화면에 없는 종류를 적지 않는다
        if not PRF.PUBLIC:
            return t
        for a_, b_ in (("쌀·한우·돼지", "쌀·돼지"), ("·광산·", "·"), ("댐·광산·", "댐·"), ("광산·지리적표시", "지리적표시")):
            t = t.replace(a_, b_)
        return t
    prio_rule = unlisted(prio_rule)
    rules = [
        f"배율 z = 지금 화면 배율 ÷ 전국 화면 배율. 전국(z < {Z_MID}), 중간({Z_MID} ≤ z < {Z_NEAR}), 가까이(z ≥ {Z_NEAR}) 세 단계로 아이콘을 늘린다. 검색과 패널 목록은 배율과 관계없이 전부 찾는다.",
        "전국: 원전 전부, 그 밖의 발전소는 종류별(석탄·가스·유류·수력·태양광·풍력) 설비 순위 상위 5, 국가산업단지 지정면적 상위 10, 무역항 물동량 상위 8, 공항 여객 상위 6, "
        f"국립공원 전부, 세계유산은 등재 건마다 대표 구성 유산 1곳, 지식 불가사의는 과학기술원·정부출연연구기관 {n_inst}곳과 연구비 상위 {UNIV_NATIONAL}개 대학. "
        "지리적표시·국가어항·철도역·국가유산 밀집지·주력 업종·쌀·한우·돼지·댐·광산·수출 거점은 전국 배율에서 그리지 않는다.",
        f"중간: 종류마다 값 순위 상위 절반(올림)을 더한다 — 국가유산 밀집지(국보·사적 수), 주력 업종(종사자), 쌀·한우·돼지, 댐·광산·수출 거점이 여기서 나온다. 고속철도 정차역도 여기서 나온다. "
        f"연구비 상위 대학의 나머지 {n_univ - UNIV_NATIONAL}곳도 여기서 나온다.",
        "가까이: 나머지 전부(세계유산의 다른 구성 유산, 지리적표시, 모든 철도역, 국가어항 포함).",
        "전국·중간 배율에서는 도시 깃발과 겹치는 아이콘을 그리지 않고(깃발이 아이콘에 가리지 않게), 모든 배율에서 이미 놓인 아이콘과 크게 겹치는 아이콘은 숨긴다(같은 칸의 항목은 툴팁·패널 목록에). "
        "선택한 항목은 늘 그린다. 단 아래 그리기 우선순위의 종류(원전, 전국 단계 공항·무역항)는 숨기지 않는다.",
        prio_rule,
        group_rule,
    ]
    rules = [unlisted(r) for r in rules]
    zoom = {"levels": [{"tier": 0, "name": "전국", "z_min": 0}, {"tier": 1, "name": "중간", "z_min": Z_MID}, {"tier": 2, "name": "가까이", "z_min": Z_NEAR}],
            "rules": rules, "counts": {str(t): dict(sorted(c.items())) for t, c in counts.items()},
            "national_total": sum(counts[0].values()),
            "draw_priority": {"first": DRAW_FIRST, "second": DRAW_SECOND, "rule": prio_rule},
            "budget": {k: v for k, v in PLACE_BUDGET.items()},
            "knowledge_groups": {"rule": group_rule, "groups": groups, "univ_national": UNIV_NATIONAL}}
    log(f"배율 단계: 전국 {zoom['national_total']} {dict(counts[0])}; 중간까지 {sum(counts[1].values())}; 전부 {sum(counts[2].values())}; "
        f"대학 묶음 전국 {[(g_['name'], g_['members']) for g_ in g0]} 중간 {[(g_['name'], g_['members']) for g_ in g1]}")
    return zoom


# =====================================================================
# 3. 순위 보고서
# =====================================================================
def build_reports(nation, states, cities, lenses):
    n = nation["nation"]
    E = nation["econ"]
    vint = nation["vintage"]
    OG = n["official"]["gdp"]
    ko = E["industry_ko"]
    ymeta = {y["id"]: y for y in E["yields"]}
    pyr = n["pyramid"]
    tot_age = lambda ks: sum(pyr["male"][k] + pyr["female"][k] for k in ks)  # noqa: E731
    lens_ids = {l_["id"] for l_ in lenses["lenses"]}

    def city_rows(val, partial=None, pop_min=None):
        rows, excluded, small = [], [], 0
        for c in cities:
            if pop_min and c["population"] < pop_min:
                small += 1
                continue
            v = val(c)
            if v is None:
                excluded.append(c["name"])
                continue
            rows.append({"id": c["id"], "value": v, **({"partial": True} if partial and partial(c) else {})})
        rows.sort(key=lambda r: -r["value"])
        for k, r in enumerate(rows):
            r["rank"] = k + 1
        return {"n": len(rows), "top": rows[:8], "bottom": rows[-3:] if len(rows) > 11 else rows[8:], "excluded": len(excluded),
                "excluded_names": excluded, "filtered_small": small}

    def sido_rows(val, partial=None, note=None):
        rows = []
        for s in states:
            v = val(s)
            rows.append({"code": s["code"], "value": v, **({"partial": True} if partial and partial(s) else {}),
                         **({"note": note(s)} if note and note(s) else {})})
        rows.sort(key=lambda r: -(r["value"] if r["value"] is not None else -1e30))
        for k, r in enumerate(rows):
            r["rank"] = k + 1 if r["value"] is not None else None
        return rows

    pc_rule = (f"1인당·증가율 순위는 인구 {PER_CAPITA_MIN_POP:,}명 이상 도시만 매긴다(작은 군은 분모가 작아 값이 크게 흔들린다). "
               "인구는 주민등록 최신 값으로 거른다.")
    reports = []
    # ---- 인구 ----
    reports.append({
        "id": "population", "name": "인구", "emoji": "👥", "unit": "명", "format": "int",
        "definition": f"주민등록 인구(행정안전부 주민등록 인구통계, {vint} 말 기준). 읍면동 인구를 더한 시군구 값이며, 시도·전국은 시군구 합이다. 외국인은 들어 있지 않다.",
        "year": vint, "source": "행정안전부 주민등록 인구통계", "national": n["population"], "lens": "density",
        "composition": {"title": "연령 3구분 (5세 계급 합)", "rows": [
            {"label": "0–14세", "value": tot_age(range(0, 3))}, {"label": "15–64세", "value": tot_age(range(3, 13))},
            {"label": "65세 이상", "value": tot_age(range(13, 21))}], "unit": "명", "parts_of_whole": True},
        "additive": True,
        "modes": [
            {"id": "total", "label": "총량", "unit": "명", "format": "int", "sido": sido_rows(lambda s: s["population"]),
             "cities": city_rows(lambda c: c["population"]), "rule": "주민등록 인구 순."},
            {"id": "growth", "label": "5년 증가율", "unit": "%", "format": "pct1", "sido": sido_rows(lambda s: s["growth_5y"]),
             "cities": city_rows(lambda c: c["growth_5y"], pop_min=PER_CAPITA_MIN_POP),
             "rule": "2020-12 → 2025-12 주민등록 인구 변화율. " + pc_rule}]})
    # ---- 고령 비율 ----
    reports.append({
        "id": "over65", "name": "고령 비율", "emoji": "🧓", "unit": "%", "format": "pct1",
        "definition": f"65세 이상 인구 ÷ 주민등록 인구 × 100 (행정안전부 주민등록 인구통계, {vint}). 비율이라 시도 값을 더하지 않는다.",
        "year": vint, "source": "행정안전부 주민등록 인구통계", "national": n["age"]["over65"], "lens": "over65",
        "composition": {"title": "65세 이상의 연령 구성", "rows": [
            {"label": "65–74세", "value": tot_age(range(13, 15))}, {"label": "75–84세", "value": tot_age(range(15, 17))},
            {"label": "85세 이상", "value": tot_age(range(17, 21))}], "unit": "명", "parts_of_whole": True},
        "additive": False,
        "modes": [{"id": "total", "label": "비율", "unit": "%", "format": "pct1", "sido": sido_rows(lambda s: s["age"]["over65"]),
                   "cities": city_rows(lambda c: c["age"]["over65"]), "rule": "비율이 높은 순."}]})
    # ---- 소멸위험지수 ----
    reports.append({
        "id": "extinction", "name": "소멸위험지수", "emoji": "⏳", "unit": "지수", "format": "f2",
        "definition": f"20–39세 여성 인구 ÷ 65세 이상 인구 (행정안전부 주민등록 인구통계, {vint}). 0.5 미만이면 소멸위험, 0.2 미만이면 소멸 고위험으로 본다. 비율이라 더하지 않는다.",
        "year": vint, "source": "행정안전부 주민등록 인구통계", "national": n["extinction_index"], "lens": "extinction",
        # 감사 23: 두 행은 부분과 전체가 아니라 분자와 분모다 — 구성비를 붙이지 않고 나눗셈을 적는다
        "composition": {"title": "지수의 분자와 분모", "rows": [
            {"label": "20–39세 여성 (분자)", "value": sum(pyr["female"][k] for k in range(4, 8))}, {"label": "65세 이상 (분모)", "value": tot_age(range(13, 21))}], "unit": "명",
            "parts_of_whole": False,
            "formula": f"{sum(pyr['female'][k] for k in range(4, 8)):,} ÷ {tot_age(range(13, 21)):,} = {sum(pyr['female'][k] for k in range(4, 8)) / tot_age(range(13, 21)):.2f}"},
        "additive": False,
        "modes": [{"id": "total", "label": "지수", "unit": "지수", "format": "f2", "sido": sido_rows(lambda s: s["extinction_index"]),
                   "cities": city_rows(lambda c: c["extinction_index"]), "rule": "지수가 높은 순(아래쪽이 소멸위험이 큰 곳)."}]})
    # ---- 다섯 산출 ----
    parts = {"food": ["agriculture"], "production": ["manufacturing", "construction", "mining"], "gold": E["industry_keys"] + ["net_taxes"],
             "science": ["information", "business_services"], "culture": ["culture_other"]}
    lens_of = {"gold": "gdp_pc", "production": "manufacturing_share"}
    for k, (nm, em) in {"food": ("식량", "🌾"), "production": ("생산", "⚙️"), "gold": ("금", "💰"), "science": ("과학", "🔬"), "culture": ("문화", "🎭")}.items():
        yr = OG["year"]

        def s_val(s, k=k):
            G = s.get("official", {}).get("gdp")
            return G["yields"][k] if G else None

        def s_pc(s, k=k):
            G = s.get("official", {}).get("gdp")
            p = s["pop_series"].get(str(G["year"])) if G else None
            return rnd(G["yields"][k] / p, 0) if G and G["yields"][k] is not None and p else None

        def c_val(c, k=k):
            return c["yields"][k] if c.get("yields") else None

        def c_pc(c, k=k):
            v = c_val(c)
            p = c["pop_series"].get(str(c.get("gdp_pop_ref"))) if c.get("gdp_pop_ref") else None
            return rnd(v / p, 0) if v is not None and p else None

        partial = lambda o, k=k: bool(o.get("yields_partial") and o["yields_partial"].get(k))  # noqa: E731
        comb = lambda s: s.get("official", {}).get("gdp", {}).get("combined")  # noqa: E731
        comp_rows = [{"label": ko[i], "value": OG["by"][i]} for i in parts[k]]
        comp_rows.sort(key=lambda r: -(r["value"] if r["value"] is not None else -1))
        yrs = sorted({c.get("gdp_year") for c in cities if c.get("gdp_year")})
        reports.append({
            "id": k, "name": nm, "emoji": em, "unit": "원", "format": "won",
            "definition": (f"{nm} = {ymeta[k]['rule']} (명목, 생산지 기준). 전국·시도는 국가데이터처 지역소득 {yr} 공식값(광업 포함), "
                           f"도시는 시군구 GRDP 의 합({'·'.join(map(str, yrs))}; 도시마다 가장 최근 연도)이다. "
                           f"{OG['latest']['label']} 전국값은 {OG['latest']['yields'][k] / 1e12:,.1f}조 원."),
            "year": str(yr), "source": "국가데이터처 지역소득(KOSIS), 시도별 시군구 GRDP", "national": OG["yields"][k],
            "lens": lens_of.get(k) if lens_of.get(k) in lens_ids else None,
            "composition": {"title": f"구성 산업 부가가치 (공식 {yr})" + (" · GRDP 의 " + f"{100 * OG['yields'][k] / OG['grdp']:.1f}%" if k != "gold" else ""),
                            "rows": comp_rows, "unit": "원", "parts_of_whole": True},
            "additive": True,
            "modes": [
                {"id": "total", "label": "총량", "unit": "원", "format": "won",
                 "sido": sido_rows(s_val, note=comb), "cities": city_rows(c_val, partial=partial),
                 "rule": "시도는 공식값, 도시는 시군구 GRDP 합으로 매긴다(두 기준이 달라 도시 합이 시도 값과 같지 않다). "
                         "* = 광업이 비공개인 공표 단위의 광업 몫을 뺀 부분 합. 값이 비공개 산업에 걸린 도시는 순위에서 뺀다."},
                {"id": "per_capita", "label": "1인당", "unit": "원", "format": "won",
                 "sido": sido_rows(s_pc, note=comb), "cities": city_rows(c_pc, partial=partial, pop_min=PER_CAPITA_MIN_POP),
                 "rule": "같은 해 12월 주민등록 인구로 나눈 값(생산지 기준이라 통근 유입이 큰 곳이 높게 나온다). " + pc_rule}]})
    # ---- F4 대조: 합칠 수 있는 수치는 시도 합 = 전국 ----
    for r in reports:
        if not r["additive"]:
            continue
        m = r["modes"][0]
        s_ = sum(x["value"] for x in m["sido"] if x["value"] is not None)
        r["sido_sum_check"] = {"sido_sum": s_, "national": r["national"], "diff": s_ - r["national"]}
    log("보고서: " + ", ".join(f"{r['id']}" + (f" 시도 합 차 {r['sido_sum_check']['diff']:,.0f}" if r.get("sido_sum_check") else "") for r in reports))
    return {"items": reports, "per_capita_min_pop": PER_CAPITA_MIN_POP, "rule": pc_rule}


def main():
    world = load_json(site("world.json"))
    cities = load_json(site("cities.json"))
    states = load_json(site("states.json"))
    nation = load_json(site("nation.json"))
    lenses = build_lenses(world)
    wonders = load_json(site("wonders.json"))
    resources = load_json(site("resources.json"))
    infra = load_json(site("infrastructure.json"))
    n_new, merged, ust = add_universities(wonders, world, cities)
    resources.setdefault("knowledge", {})["universities_note"] = ust
    wonders["zoom"] = assign_tiers([wonders, resources, infra], world)
    for nm, obj in (("wonders", wonders), ("resources", resources), ("infrastructure", infra)):
        obj["precision_counts"] = dict(collections.Counter(i["precision"] for i in obj["items"]))
        save_json(site(f"{nm}.json"), obj)
    nation["reports"] = build_reports(nation, states, cities, lenses)
    save_json(site("nation.json"), nation)
    tot = sum(os.path.getsize(site(f)) for f in os.listdir(site()) if f.endswith(".json"))
    log(f"사이트 JSON 합계 {tot / 1e6:.3f} MB")


if __name__ == "__main__":
    sys.exit(main())

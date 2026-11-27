"""5d — 수출입, 교역로, 남은 위치 자료 (명세 docs/SPEC_PHASE5C.md 2부 §4–§9).

build_layers2.py(5b)가 만든 site/data/{wonders,resources,infrastructure}.json, cities/states/nation/lenses.json 에
5d 자료를 붙이고 site/data/trade.json(교역로·품목 목록)을 새로 만든다.

입력 (읽기만, 신뢰할 수 없는 입력으로 다룬다 — 필드 값은 데이터로만 쓰고 형식이 다르면 빌드 오류):
  data/build/layers/{trade_sgg,trade_sgg_hs2,flows_od,key_industries_2020,key_industries_all,dam_observations,
                     active_mines,research_campuses,university_research_funding,park_area,world_heritage_components,
                     livestock_hanwoo,livestock_pig_sido}.csv
  data/raw/layers2/manifest.json (출처 기록), 국가유산 목록 XML (5a 와 같은 파일, 세계유산 구성 유산의 좌표)

다시 돌려도 같은 결과가 나오도록, 5b 가 만든 층 JSON(version phase5b-2)을 처음 볼 때 data/build/layers5b_snapshot/ 에 복사해 두고
그 뒤로는 이 사본에서 시작한다(build_layers2.py 를 다시 돌리면 사본도 새로 쓴다).

위치 정밀도: point(원자료 좌표 또는 같은 이름 국가유산의 좌표) / county(주소의 시군구, 인구 가중 중심 칸).
place_from: 위치를 무엇으로 정했는지 (heritage_name, address, observation, office).
"""
import collections
import csv
import math
import os
import re
import shutil
import sys

import numpy as np

from build_layers import World, load_heritage
from lib import econ as E
from lib import popstats
from lib import profile as PRF
from lib.address import AddressResolver, nospace
from lib.common import build, load_json, raw, rnd, save_json, site
from lib.terrain import layer_path

VERSION = "phase5d"
SNAP = build("layers5b_snapshot")
EXPORT_HUB_N = 15          # 수출 거점: 수출액 상위 도시 수 (명세 예시 15)
ROUTES_N = 40              # 교역로: 시도 쌍 상위 구간 수 (명세 예시 40)
KI_SHARE = 0.03            # 주력 업종: 전국 종사자(공개값 합) 가운데 이 비중 이상인 도시에 아이콘 (명세 예시 3%)
HANWOO_N = 15              # 한우 사육 상위
FUNDING_N = 20             # 대학 연구비 순위
MINE_MIN = 3               # 광산 아이콘: 같은 광종 가행 광산이 이 수 이상인 시군구 (분포를 보고 정함, 아래 규칙 문장)
KI_CODES = ["C19", "C20", "C24", "C26", "C30", "C31"]
KI_SHORT = {"C19": "석유정제", "C20": "화학", "C24": "1차 금속", "C26": "전자부품", "C30": "자동차", "C31": "기타 운송장비(조선 등)"}


def log(*a):
    print("[layers5d]", *a, flush=True)


def read_rows(name):
    with open(layer_path(name), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fnum(s):
    s = (s or "").replace(",", "").strip()
    if s == "":
        return None
    return float(s)


def as_int(v):
    return None if v is None else int(round(v))


def usd_ko(v):
    """달러 -> '127.7억 달러' (문장용)"""
    if v is None:
        return "자료 없음"
    a = abs(v)
    if a >= 1e8:
        return f"{v / 1e8:,.1f}억 달러"
    if a >= 1e4:
        return f"{v / 1e4:,.0f}만 달러"
    return f"{v:,.0f} 달러"


class LayerEcon(E.Econ):
    """data/build/layers 의 시군구 표를 경제 정리표와 같은 규칙(lib/econ.py)으로 단위에 붙인다.
    strip_sido: 원표 이름이 '경기도 수원시'처럼 시도 이름으로 시작하면 시도 이름을 떼고 맞춘다(관세청 표)."""

    def __init__(self, world, cities, resolver):
        super().__init__(world, cities)
        self.res = resolver

    def table(self, name, strip_sido=False):
        key = (name, strip_sido)
        if key in self.tables:
            return self.tables[key]
        rows = read_rows(name + ".csv")
        need = {"sgg_code_raw", "sgg_name_raw", "sgg_code_now", "sido_now", "year", "indicator", "industry", "value"}
        if rows and not need <= set(rows[0]):
            raise ValueError(f"{name}.csv 열이 다름: {sorted(need - set(rows[0]))}")
        out = []
        for r in rows:
            rr = dict(r)
            if strip_sido:
                sd, rest = self.res.sido_of(r["sgg_name_raw"])
                if sd is not None and rest:
                    rr["sgg_name_raw"] = rest
            res = self.resolve(rr)
            if res is None:
                self.ignored[(name, r["sido_now"], r["sgg_name_raw"])] += 1
                out.append({"kind": None, "key": None, "codes": None, "sido_now": r["sido_now"], "name_raw": r["sgg_name_raw"],
                            "year": r["year"], "indicator": r["indicator"], "industry": r["industry"], "value": E.num(r["value"]),
                            "raw_empty": (r["value"] or "").strip() == "", "source": r.get("source_id", ""), "raw": ""})
                continue
            kind, k, codes = res
            out.append({"kind": kind, "key": k, "codes": codes, "sido_now": r["sido_now"], "name_raw": r["sgg_name_raw"], "year": r["year"],
                        "raw": (r.get("sgg_code_raw") or "").strip(), "indicator": r["indicator"], "industry": r["industry"],
                        "value": E.num(r["value"]), "raw_empty": (r["value"] or "").strip() == "", "unit": r.get("unit", ""),
                        "basis": r.get("basis", ""), "source": r.get("source_id", "")})
        self.tables[key] = out
        return out


def snapshot_inputs():
    """5b 층 JSON 을 처음 보면 사본을 남기고, 이미 5d 가 고친 것이면 사본에서 읽는다."""
    os.makedirs(SNAP, exist_ok=True)
    out = {}
    for nm in ("wonders", "resources", "infrastructure"):
        cur = load_json(site(f"{nm}.json"))
        snap = os.path.join(SNAP, f"{nm}.json")
        if cur.get("version") == "phase5b-2":
            shutil.copyfile(site(f"{nm}.json"), snap)
            out[nm] = cur
        elif os.path.exists(snap):
            out[nm] = load_json(snap)
        else:
            raise RuntimeError(f"{nm}.json 이 5b 결과가 아니고 사본도 없음 — build_layers.py, build_layers2.py 를 먼저 돌린다")
    return out


def main():
    W = World()
    w = W.w
    cities = load_json(site("cities.json"))
    states = load_json(site("states.json"))
    nation = load_json(site("nation.json"))
    lenses = load_json(site("lenses.json"))
    L = snapshot_inputs()
    wonders, resources, infra = L["wonders"], L["resources"], L["infrastructure"]
    m2 = load_json(raw("layers2", "manifest.json"))
    dongs = load_json(build("dongs.json"))
    resolver = AddressResolver(w, cities)
    ec = LayerEcon(w, cities, resolver)
    sido_name = {s["code"]: s["name"] for s in w["states"]}
    sido_short = {s["code"]: s["short"] for s in w["states"]}
    city_of_code = {s: c["id"] for c in cities for s in c["sgg"]}
    city_by_id = {c["id"]: c for c in cities}
    state_by = {s["code"]: s for s in states}

    def src(prefix, file=None, note=None, title=None):
        """data/raw/layers2/manifest.json 에서 key 가 prefix 로 시작하는 기록 (시도별로 나뉜 파일은 하나로 묶어 수를 적는다)."""
        ks = sorted(k for k in m2 if k == prefix or k.startswith(prefix))
        if not ks:
            raise ValueError(f"layers2 manifest 에 {prefix} 가 없음")
        e = m2[ks[0]]
        return {"key": prefix, "title": (title or e.get("title")) + (f" (파일 {len(ks)}개)" if len(ks) > 1 else ""),
                "publisher": e.get("publisher") if len({m2[k].get("publisher") for k in ks}) == 1 else "기관별 (원 매니페스트 참조)",
                "retrieved": max((m2[k].get("retrieved") or "")[:10] for k in ks), "file": "layers/" + (file or ""),
                "license": e.get("license") or e.get("license_note"), "url": e.get("catalog_url") or e.get("url"), "note": note}

    # ---------- 시군구 단위 인구 가중 중심 칸 (5a·5b 와 같은 규칙) ----------
    _, _, f_emd, _ = popstats.latest_files()
    rec, _ = popstats.dong_population(f_emd, dongs)
    dpop = {d["code"]: rec[d["code"]]["total"] for d in dongs}
    center_cache = {}

    def unit_center(codes):
        codes = frozenset(codes)
        if codes in center_cache:
            return center_cache[codes]
        items = [(d["rx"], d["ry"], dpop.get(d["code"], 0)) for d in dongs if d["sgg"] in codes]
        own = np.nonzero(np.isin(W.code_of, list(codes)) & W.land)[0]
        if not len(own):
            raise ValueError(f"칸이 없는 단위 {sorted(codes)}")
        tw = sum(i[2] for i in items)
        if tw > 0:
            px, py = sum(i[0] * i[2] for i in items) / tw, sum(i[1] * i[2] for i in items) / tw
        else:
            px, py = W.centers[own].mean(0)
        k = int(own[np.argmin(((W.centers[own] - [px, py]) ** 2).sum(1))])
        center_cache[codes] = k
        return k

    def cnames(codes):
        return " · ".join(W.cname[c] for c in sorted(codes))

    def place_of(codes):
        codes = sorted(codes)
        sd = W.sido_of_code[codes[0]]
        cid = city_of_code.get(codes[0])
        cty = city_by_id.get(cid)
        if cty and set(cty["sgg"]) == set(codes) and len(codes) > 1:
            return f"{sido_name[sd]} {cty['name']}"
        return f"{sido_name[sd]} {cnames(codes)}"

    def item(kind, name, cell, precision, codes, **kw):
        codes = sorted(codes)
        sd = W.sido_of_code[codes[0]]
        same_city = all(city_of_code.get(c) == city_of_code.get(codes[0]) for c in codes)
        it = {"id": None, "kind": kind, "name": name, "cell": int(cell), "precision": precision, "sgg": codes, "sido": sd,
              "city": city_of_code.get(codes[0]) if same_city else None, "place": place_of(codes)}
        it.update(kw)
        return it

    def rank_items(items, key=lambda it: it.get("value")):
        order = sorted(range(len(items)), key=lambda k: -(key(items[k]) if key(items[k]) is not None else -1))
        for r, k in enumerate(order):
            items[k]["rank"] = r + 1
        return items

    # 현재 시·군 이름(구 제외)과 '시'·'군'을 뗀 이름 -> 단위 (일반구를 둔 시는 시 전체). 전국에 하나뿐일 때만 쓴다.
    sigun = collections.defaultdict(list)
    for c in w["counties"]:
        if c["name"].endswith(("시", "군")) and " " not in c["name"]:
            sigun[c["name"]].append(frozenset([c["code"]]))
    for c in cities:
        if len(c["sgg"]) > 1 and c["name"].endswith("시"):
            sigun[c["name"]].append(frozenset(c["sgg"]))
    stem = collections.defaultdict(list)
    for nm, lst in sigun.items():
        for codes in lst:
            stem[nm].append(codes)
            stem[nm[:-1]].append(codes)

    def city_units(codes_set):
        """코드 집합(단위)이 통째로 든 도시 id, 없으면 None"""
        cids = {city_of_code[c] for c in codes_set}
        return next(iter(cids)) if len(cids) == 1 else None

    # =====================================================================
    # §4 수출입 (관세청 2025, 시군구 공표 단위)
    # =====================================================================
    tr_rows = ec.table("trade_sgg", strip_sido=True)
    IND = {"trade_export": "export", "trade_import": "import", "trade_balance": "balance"}
    for r in tr_rows:
        if r["indicator"] not in IND:
            raise ValueError(f"trade_sgg.csv 지표를 모름: {r['indicator']}")
        if r["year"] != "2025":
            raise ValueError(f"trade_sgg.csv 연도가 2025 가 아님: {r['year']}")
        if r["value"] is None:
            raise ValueError(f"trade_sgg.csv 값 빈칸: {r['name_raw']}")
    n_units_raw = len({(r["sido_now"], r["name_raw"]) for r in tr_rows})
    unmatched_tr = sorted({(r["sido_now"], r["name_raw"]) for r in tr_rows if r["codes"] is None})
    tmaps = {}
    for ind, k in IND.items():
        tmaps[k] = ec.unit_map([r for r in tr_rows if r["indicator"] == ind and r["codes"] is not None], True)
    sido_code_of_name = {s["name"]: s["code"] for s in w["states"]}
    # 시도·전국 합: 원표 시군구 공표값의 합 (현재 코드에 붙지 않은 공표 단위도 그 시도 합에는 든다)
    sido_tr = collections.defaultdict(lambda: {"export": 0, "import": 0, "balance": 0, "units": 0, "unmatched": []})
    for r in tr_rows:
        sd = sido_code_of_name[r["sido_now"]]
        k = IND[r["indicator"]]
        sido_tr[sd][k] += r["value"]
        if k == "export":
            sido_tr[sd]["units"] += 1
            if r["codes"] is None:
                sido_tr[sd]["unmatched"].append({"name": r["name_raw"], "export": as_int(r["value"])})
    unm_val = {k: sum(r["value"] for r in tr_rows if r["codes"] is None and IND[r["indicator"]] == k) for k in ("export", "import", "balance")}
    nat_tr = {k: sum(v[k] for v in sido_tr.values()) for k in ("export", "import", "balance")}
    # 단위 -> 도시
    unit_key = lambda codes: "+".join(sorted(codes))
    city_tr = {}
    for c in cities:
        vals = {k: E.agg(tmaps[k], c["sgg"]) for k in ("export", "import", "balance")}
        units = [u for u in tmaps["export"] if u <= set(c["sgg"])]
        if vals["export"] is None and not units:
            city_tr[c["id"]] = None
            continue
        city_tr[c["id"]] = {**{k: as_int(v) for k, v in vals.items()}, "year": "2025", "units": sorted(unit_key(u) for u in units)}
    s_city = sum(v["export"] for v in city_tr.values() if v and v["export"] is not None)
    log(f"수출입: 공표 단위 {n_units_raw}, 현재 코드 대응 못 함 {len(unmatched_tr)} {unmatched_tr} (수출 {usd_ko(unm_val['export'])}); "
        f"도시 수출 합 {s_city:,.0f} + 대응 못 함 {unm_val['export']:,.0f} = 전국(시군구 공표값 합) {nat_tr['export']:,.0f}")
    # 품목 (HS 2단위, 시군구별 상위 5)
    hs_rows = ec.table("trade_sgg_hs2", strip_sido=True)
    hs_names = {}
    hs_units = collections.defaultdict(lambda: {"e": [], "i": []})   # [HS 코드, 천 달러(원표 단위)]
    hs_unmatched = collections.Counter()
    for r in hs_rows:
        m = re.match(r"^HS(\d{2})\s+(.+)$", r["industry"].strip())
        if not m or r["indicator"] not in ("trade_export", "trade_import") or r["value"] is None:
            raise ValueError(f"trade_sgg_hs2.csv 행 형식이 다름: {r['industry']!r} {r['indicator']} {r['value']}")
        code, nm = m.group(1), m.group(2).strip()
        if hs_names.setdefault(code, nm) != nm:
            raise ValueError(f"HS{code} 이름이 둘: {hs_names[code]} / {nm}")
        if r["codes"] is None:
            hs_unmatched[(r["sido_now"], r["name_raw"])] += 1
            continue
        hs_units[unit_key(r["codes"])][IND[r["indicator"]][0]].append([int(code), as_int(r["value"] / 1000)])
    for u, d in hs_units.items():
        for k in ("e", "i"):
            if len(d[k]) > 5:
                raise ValueError(f"품목이 5개를 넘는 단위: {u} {k}")
            d[k].sort(key=lambda t: -t[1])
    # 공표 단위 -> {e: 수출 품목, i: 수입 품목, v: [수출, 수입, 무역수지] 달러}. 이름은 화면에서 코드로 찾는다
    trade_units = {u: dict(d) for u, d in sorted(hs_units.items())}
    for u in tmaps["export"]:
        k = unit_key(u)
        trade_units.setdefault(k, {"e": [], "i": []})
        trade_units[k]["v"] = [as_int(tmaps[x][u]) for x in ("export", "import", "balance")]
    # 순위
    ranked = sorted([c for c in cities if city_tr[c["id"]] and city_tr[c["id"]]["export"] is not None], key=lambda c: -city_tr[c["id"]]["export"])
    for k, c in enumerate(ranked):
        c.setdefault("ranks", {})["export"] = k + 1
    for c in cities:
        c["trade"] = city_tr[c["id"]]
        if c["trade"] is None:
            c.setdefault("ranks", {})["export"] = None
    top5 = [(c["name"], city_tr[c["id"]]["export"]) for c in ranked[:5]]
    log(f"수출 상위 5 도시: {[(n, usd_ko(v)) for n, v in top5]}")
    imp_top = sorted(((u, v) for u, v in tmaps["import"].items()), key=lambda t: -t[1])[:5]
    log(f"수입 상위 5 공표 단위: {[(place_of(u), usd_ko(v)) for u, v in imp_top]}")
    TRADE_BASIS = ("관세청 수출입무역통계 '지역별 총괄 → 시군구' 2025년 연간, 신고 수리일 기준. 수출은 제조장소 우편번호, 수입은 납세의무자 주소지 "
                   "우편번호 기준이다(수출입 신고인의 소재지가 아님). 원표 천 달러 × 1,000 = 달러. 무역수지는 원표의 무역수지를 그대로 쓴다(수출 − 수입과 천 달러 "
                   "차이가 나는 곳이 있다).")
    hq = sorted(tmaps["import"].items(), key=lambda t: -t[1])[0]
    hq_place = place_of(hq[0])
    TRADE_HQ = (f"수입은 납세의무자(대개 본사) 주소지 기준이라 본사가 몰린 곳에 수입이 몰린다: {hq_place} 수입 {usd_ko(hq[1])} "
                f"(수출 {usd_ko(tmaps['export'].get(hq[0]))}). 수출도 제조장소 기준이지만 제조장소를 본사 주소로 신고하면 본사 소재지로 잡힐 수 있다.")
    TRADE_UNMATCHED = (f"현재 시군구 코드에 대응하지 못한 공표 단위 {len(unmatched_tr)}곳(" + ", ".join(f"{a} {b}" for a, b in unmatched_tr)
                       + f", 원표의 옛 지명으로 현재 코드가 공란)은 도시에 붙이지 않았다(수출 {usd_ko(unm_val['export'])}). 시도·전국 합에는 든다.")
    for s in states:
        v = sido_tr.get(s["code"])
        s["trade"] = None if v is None else {"export": as_int(v["export"]), "import": as_int(v["import"]), "balance": as_int(v["balance"]),
                                             "year": "2025", "units": v["units"], "unmatched": v["unmatched"], "basis": "시군구 공표값의 합"}
    nation["nation"]["trade"] = {**{k: as_int(v) for k, v in nat_tr.items()}, "year": "2025", "units": n_units_raw, "basis": "시군구 공표값의 합",
                                 "unmatched": [{"sido": a, "name": b} for a, b in unmatched_tr], "unmatched_export": as_int(unm_val["export"]),
                                 "note": "전국 공식 수출입 총액은 이 자료에 없어 싣지 않는다. 전국 값은 229개 시군구 공표 단위 값의 합이다."}

    # 수출 거점 (수출액 상위 도시)
    EH = []
    for k, c in enumerate(ranked[:EXPORT_HUB_N]):
        t = city_tr[c["id"]]
        cell = unit_center(c["sgg"])
        det = [f"2025년 수출 {usd_ko(t['export'])} · 수입 {usd_ko(t['import'])} · 무역수지 {usd_ko(t['balance'])}",
               f"도시 {len(ranked)}곳 중 수출 {k + 1}위 · 소속 시군구 공표 단위 {len(t['units'])}곳의 합", "수출은 제조장소 우편번호 기준 (관세청)"]
        EH.append(item("export_hub", f"수출 거점 · {c['name']}", cell, "county", c["sgg"], value=t["export"], unit="달러 (2025 수출)",
                       value_label=f"{usd_ko(t['export'])} (2025 수출)", year="2025", place_from="city", source="customs-trade-sgg-2025",
                       detail=det, rank=k + 1))
    trade_kind = {
        "name": "수출 거점", "group": "trade", "count": len(EH), "placed": len(EH),
        "rule": (f"{TRADE_BASIS} 도시 = 소속 시군구 공표 단위의 합(일반구를 둔 시는 시 전체 공표값, 인천의 개편 전 중구·동구·서구는 인천 안이라 인천에 더함). "
                 f"수출액 상위 {EXPORT_HUB_N}개 도시에 아이콘을 두며 위치는 그 도시 시군구의 인구 가중 중심 칸(도시 합계라 county). {TRADE_HQ} {TRADE_UNMATCHED}"),
        "source": [src("customs-trade-sgg-2025", "trade_sgg.csv", title="관세청 수출입무역통계 지역별 총괄 시군구 2025 (시도별)")], "year": "2025", "missing": [{"name": f"{a} {b}", "reason": "현재 시군구 코드 없음 (원표 옛 지명)"} for a, b in unmatched_tr],
        "precision_note": "county (도시 합계)"}

    # 렌즈: 1인당 수출 (달러/명, 주민등록 인구 2025-12)
    pop = E.Population(set(W.codes))
    epc = {}
    for u, v in tmaps["export"].items():
        p_, _ = pop.get(u, "2025")
        epc[u] = None if not p_ else v / p_
    cval = {}
    for u, v in epc.items():
        for code in u:
            cval[code] = v
    by_county = [rnd(cval.get(code), 0) if cval.get(code) is not None else None for code in W.codes]
    N, land = W.N, W.land
    nl = int(land.sum())
    cov = sum(1 for i in range(N) if land[i] and by_county[W.county[i]] is not None) / nl
    vals = [by_county[W.county[i]] for i in range(N) if land[i] and by_county[W.county[i]] is not None]
    lens_made = cov >= 0.5
    if lens_made:
        lo, hi = float(np.percentile(vals, 2)), float(np.percentile(vals, 98))
        lz = {"id": "export_pc", "group": "industry", "name": "1인당 수출", "emoji": "🚢", "unit": "달러/명", "format": "int", "scale": "log",
              "ramp": ["#eef4f7", "#c7dde8", "#8fbcd3", "#5094b8", "#2a6a93", "#123f62"], "higher_is": "neutral", "basis": "제조장소 (수출 신고)",
              "vintage": "2025", "source": "관세청 수출입무역통계 시군구 2025, 주민등록 인구 2025-12",
              "description": (f"2025년 수출액(달러) ÷ 2025년 12월 주민등록 인구. {TRADE_BASIS} 시 전체로만 공표된 값(수원시 등)은 소속 일반구 칸에 같은 값을, "
                              "인천의 개편 전 중구·동구 합과 서구는 개편 후 구 묶음 칸에 같은 값을 칠한다. 공단·항만이 있는 곳은 인구가 적어 아주 높게 나온다. "
                              f"{TRADE_UNMATCHED}"),
              "by_county": by_county, "coverage": round(cov, 4), "phase": "5d", "domain": [rnd(max(lo, 1), 0), rnd(hi, 0)]}
        from lib import units as U  # 감사 01: 시 전체·개편 전 구 단위 값은 공표 단위를 적는다
        U.annotate(lz, [(u, "2025") for u, v in epc.items() if v is not None], U.Namer(W.w, cities))
        lenses["lenses"] = [l_ for l_ in lenses["lenses"] if l_["id"] != "export_pc"] + [lz]
    log(f"렌즈 export_pc: 값이 있는 육지 칸 {100 * cov:.1f}% → {'만듦' if lens_made else '만들지 않음 (50% 미만)'}")

    # =====================================================================
    # §5 교역로 (국가물류통합정보센터 2024 도로 화물 O/D, 시도 17×17)
    # =====================================================================
    od = read_rows("flows_od.csv")
    if len(od) != 289:
        raise ValueError(f"flows_od.csv 행 수 {len(od)} != 289")
    names17 = sorted({r["origin"] for r in od})
    if len(names17) != 17 or sorted({r["destination"] for r in od}) != names17:
        raise ValueError("flows_od.csv 시도가 17개가 아님")
    sido_of17 = {}
    for nm in names17:
        sd, rest = resolver.sido_of(nm)
        if sd is None or rest:
            raise ValueError(f"flows_od.csv 시도 이름을 모름: {nm}")
        sido_of17[nm] = sd
    if len(set(sido_of17.values())) != 16:
        raise ValueError("flows_od.csv 시도 17개가 지도 시도 16개로 묶이지 않음")
    flow = collections.Counter()
    raw_total, intra_raw17 = 0.0, 0.0
    for r in od:
        if r["unit"] != "톤/년" or r["mode"] != "road" or r["year"] != "2024":
            raise ValueError(f"flows_od.csv 행 형식이 다름: {r}")
        v = fnum(r["value"])
        if v is None:
            raise ValueError(f"flows_od.csv 값 빈칸: {r['origin']}→{r['destination']}")
        raw_total += v
        if r["origin"] == r["destination"]:
            intra_raw17 += v
        flow[(sido_of17[r["origin"]], sido_of17[r["destination"]])] += v
    codes16 = sorted(set(sido_of17.values()))
    intra = {s: flow[(s, s)] for s in codes16}
    gj_jn = sum(fnum(r["value"]) for r in od if {r["origin"], r["destination"]} == {"광주", "전남"})
    pairs = []
    for i, a in enumerate(codes16):
        for b in codes16[i + 1:]:
            pairs.append({"a": a, "b": b, "ab": as_int(flow[(a, b)]), "ba": as_int(flow[(b, a)]), "total": as_int(flow[(a, b)] + flow[(b, a)])})
    pairs.sort(key=lambda p: -p["total"])
    inter_total = sum(p["total"] for p in pairs)
    for k, p in enumerate(pairs):
        p["rank"] = k + 1
        p["share"] = round(100 * p["total"] / inter_total, 2)
    intra_total = sum(intra.values())
    log(f"교역로: 원자료 {len(od)}행 {raw_total:,.0f}톤, 시도 안 {intra_total:,.0f}톤(17개 시도 대각 {intra_raw17:,.0f} + 광주↔전남 {gj_jn:,.0f}), "
        f"시도 간 {inter_total:,.0f}톤 = {raw_total - intra_total:,.0f}, 쌍 {len(pairs)}개 중 상위 {ROUTES_N}")
    # 청사 칸 (선의 끝점)
    anchors = {}
    for s in states:
        if s["code"] == "12":
            o = next(e for e in s["special_offices"] if e["name"] == "광주청사")
            anchors[s["code"]] = {"office": f"전남광주통합특별시 {o['name']}", "sgg": o["sgg"], "cell": unit_center(o["sgg"]),
                                  "rule": "전남광주통합특별시는 특별법의 청사 3곳 가운데 광주청사(종전 광주광역시청 주소의 시군구)"}
        else:
            o = next(e for e in s["offices"] if e["role"] == "시도청")
            anchors[s["code"]] = {"office": f"{o['name']}청 ({o['address']})", "sgg": o["sgg"], "cell": unit_center(o["sgg"]),
                                  "rule": "행정안전부 공표본 시도청 주소의 시군구(원표에 시도청이 둘이면 첫 행)"}
    # 시도 패널: 상대 시도 상위 5, 시도 안 흐름 비중
    for s in states:
        sc = s["code"]
        out_t = sum(v for (a, b), v in flow.items() if a == sc)
        in_t = sum(v for (a, b), v in flow.items() if b == sc)
        partners = sorted(({"sido": (p["b"] if p["a"] == sc else p["a"]), "out": p["ab"] if p["a"] == sc else p["ba"],
                            "in": p["ba"] if p["a"] == sc else p["ab"], "total": p["total"], "rank": p["rank"]}
                           for p in pairs if sc in (p["a"], p["b"])), key=lambda x: -x["total"])[:5]
        s["freight"] = {"year": "2024", "intra_t": as_int(intra[sc]), "out_t": as_int(out_t), "in_t": as_int(in_t),
                        "intra_share_out": round(100 * intra[sc] / out_t, 1) if out_t else None, "partners": partners,
                        "note": ("전남광주 안 흐름에는 광주↔전남, 광주 안, 전남 안 흐름이 모두 든다." if sc == "12" else None)}
    ROUTE_RULE = (f"국가물류통합정보센터 내륙화물통계 '도로 O·D별 수송실적' 2024년(출처 국가교통DB), 시도 17×17 방향별 289행(톤/년). 시도 쌍마다 두 방향 톤을 더하고 "
                  f"시도 안 흐름을 뺀 {len(pairs)}쌍 가운데 상위 {ROUTES_N}구간을 그린다. 원자료의 광주와 전남은 따로지만 지도는 16개 시도라 광주–전남 흐름은 "
                  "'전남광주 안 흐름'으로 보고 구간에서 뺐고, 다른 시도와의 흐름은 광주와 전남을 더했다. 선은 두 시도 청사 소재 칸(행정안전부 공표본 시도청 주소의 "
                  "시군구, 인구 가중 중심 칸 — 전남광주는 광주청사)을 잇는 완만한 곡선이며 굵기는 두 방향 합 톤에 비례한다. "
                  "시군구 간이 아니라 시도 간 자료이고 도로 화물만이다. 철도·해운·항공은 없다. 시군구 간 자료는 신청·로그인이 필요해 받지 않았다.")
    trade_json = {
        "version": VERSION,
        "routes": {"year": "2024", "unit": "톤/년", "mode": "도로 화물", "rule": ROUTE_RULE, "top_n": ROUTES_N, "pairs_total": len(pairs),
                   "segments": pairs[:ROUTES_N], "anchors": anchors,
                   "totals": {"raw_t": as_int(raw_total), "intra_t": as_int(intra_total), "intra_17_diag_t": as_int(intra_raw17),
                              "gwangju_jeonnam_t": as_int(gj_jn), "inter_t": inter_total, "shown_t": sum(p["total"] for p in pairs[:ROUTES_N])},
                   "source": [src("nlic-road-od-2024", "flows_od.csv")]},
        "hs_names": hs_names, "units": trade_units,
        "units_note": "공표 단위(현재 시군구 코드를 '+'로 이은 것) -> e: 수출 상위 품목, i: 수입 상위 품목 [HS 2단위 코드, 천 달러(원표 단위)], v: [수출, 수입, 무역수지] 달러",
        "trade": {"basis": TRADE_BASIS, "hq_note": TRADE_HQ, "unmatched_note": TRADE_UNMATCHED, "year": "2025",
                  "source": [src("customs-trade-sgg-2025", "trade_sgg.csv", title="관세청 수출입무역통계 지역별 총괄 시군구 2025 (시도별)"), src("customs-trade-hs2-2025", "trade_sgg_hs2.csv", title="관세청 수출입무역통계 지역별 품목별 HS 2단위 2025 (시도별)")],
                  "hs_rule": ("품목은 관세청 '지역별 실적 → 품목별 → HS 2단위'에서 시군구마다 수출·수입 각각 양수인 상위 5개만 받았다(동률은 HS 코드 순). "
                              "그래서 여러 시군구로 된 도시의 품목 순위는 합쳐서 다시 매기지 않고 공표 단위별 목록을 그대로 보인다."),
                  "unmatched": [{"sido": a, "name": b} for a, b in unmatched_tr], "hs_unmatched_rows": sum(hs_unmatched.values())},
    }

    # =====================================================================
    # §6 주력 업종 (2020 경제총조사 = 지도 아이콘, 최신 = 패널 병기)
    # =====================================================================
    def ki_code(s):
        m = re.match(r"^(C\d{2})\s", s.strip())
        if not m or m.group(1) not in KI_CODES:
            raise ValueError(f"주력 업종 분류를 모름: {s!r}")
        return m.group(1)

    def city_agg(rows, c):
        """도시 값: 도시 전체(일반구를 둔 시의 시 전체 행)가 공개면 그 값, 아니면 소속 단위의 공개값 합. -> (값, 비공개·누락 포함 여부) 또는 None"""
        cs = frozenset(c["sgg"])
        inside = [r for r in rows if r["codes"] is not None and r["codes"] <= cs]
        if not inside:
            return None
        full = [r for r in inside if r["codes"] == cs and r["value"] is not None]
        if full:
            return full[0]["value"], False
        fine = [r for r in inside if r["codes"] != cs or len(cs) == 1]
        cover = set().union(*[r["codes"] for r in fine]) if fine else set()
        disclosed = [r["value"] for r in fine if r["value"] is not None]
        partial = cover != cs or len(disclosed) < len(fine)
        if not disclosed:
            return None, True
        return sum(disclosed), partial

    k20 = ec.table("key_industries_2020")
    kall = ec.table("key_industries_all")
    ki_names = {}
    for r in k20:
        cd = ki_code(r["industry"])
        ki_names.setdefault(cd, re.sub(r"^C\d{2}\s+", "", r["industry"]).strip())
    k20_unmatched = sorted({(r["sido_now"], r["name_raw"]) for r in k20 if r["codes"] is None})
    kall_unmatched = sorted({(r["sido_now"], r["name_raw"]) for r in kall if r["codes"] is None})
    ki_by_city, KI_items, ki_nat, ki_blank = {}, [], {}, {}
    for cd in KI_CODES:
        r20 = [r for r in k20 if ki_code(r["industry"]) == cd]
        rall = [r for r in kall if ki_code(r["industry"]) == cd]
        ki_blank[cd] = sum(1 for r in r20 if r["raw_empty"])
        per = {}
        for c in cities:
            v = city_agg(r20, c)
            if v is not None:
                per[c["id"]] = v
        nat = sum(v[0] for v in per.values() if v[0] is not None)
        ki_nat[cd] = as_int(nat)
        for c in cities:
            a = per.get(c["id"])
            # 최신 값: 출처마다 연도가 다르다 (2024, 인천 2022)
            rl = [r for r in rall if r["codes"] is not None and r["codes"] <= set(c["sgg"])]
            b = city_agg(rl, c) if rl else None
            yrs = sorted({r["year"] for r in rl})
            if a is None and b is None:
                continue
            ki_by_city.setdefault(str(c["id"]), {})[cd] = [as_int(a[0]) if a else None, int(bool(a and a[1])),
                                                          as_int(b[0]) if b else None, int(bool(b and b[1])), "/".join(yrs) or None]
        hits = sorted(((c, per[c["id"]]) for c in cities if c["id"] in per and per[c["id"]][0] is not None and per[c["id"]][0] >= KI_SHARE * nat),
                      key=lambda t: -t[1][0])
        kind = f"ind_{cd.lower()}"
        its = []
        for c, (v, part) in hits:
            det = [f"2020년 경제총조사 {cd} {ki_names[cd]} 종사자 {int(v):,}명 = 전국(공개값 합 {int(nat):,}명)의 {100 * v / nat:.1f}%",
                   "사업장 소재지 기준. 일반구를 둔 시는 시 전체 행, 그 밖의 도시는 소속 시군구 행의 합"]
            if part:
                det.append("소속 시군구 가운데 비공개(빈 값)가 있어 공개값만 더한 값 (실제보다 작을 수 있음)")
            its.append(item(kind, f"{KI_SHORT[cd]} · {c['name']}", unit_center(c["sgg"]), "county", c["sgg"], value=as_int(v),
                            unit=f"명 (2020 {KI_SHORT[cd]} 종사자)", share=round(100 * v / nat, 2), partial=bool(part), year="2020",
                            industry=cd, place_from="city", source="kosis-101-DT_2KI2010_11", detail=det))
        rank_items(its)
        KI_items += its
    ki_counts = collections.Counter(i["kind"] for i in KI_items)
    log(f"주력 업종 2020: 전국 공개값 합 {ki_nat}, 비공개 행 {ki_blank}, 아이콘 {dict(ki_counts)}, 2020 대응 못 함 {k20_unmatched}, 최신 대응 못 함 {kall_unmatched}")
    ki_src = [src("kosis-101-DT_2KI2010_11", "key_industries_2020.csv")]
    KI_RULE = (f"전국을 한 기준으로 덮는 2020년 경제총조사(KOSIS DT_2KI2010_11, 사업장 소재지 종사자 수) 시군구 표 {len(k20)}행. 도시 값은 일반구를 둔 시면 시 전체 행, "
               "그 밖에는 소속 시군구 행의 합(비공개 빈 값은 0 이 아니라 빼고 '공개값 합'으로 표시). 업종별 전국 합은 도시 값(공개값)의 합이다: "
               + ", ".join(f"{cd} {ki_nat[cd]:,}명(비공개 행 {ki_blank[cd]})" for cd in KI_CODES)
               + f". 전국 합의 {KI_SHARE * 100:.0f}% 이상인 도시에 업종 아이콘을 둔다(위치는 도시 시군구의 인구 가중 중심 칸). 도시 패널에는 2020년 값과, "
               "있으면 최신 값(시도별 사업체조사 2024년, 인천 2022년)을 연도와 함께 나란히 싣는다. 최신 값은 11개 시도(경기·충북·충남·전북·종전 전남·경북·경남·"
               "대구·서울·세종·제주)와 인천(2022)만 있다; 부산·광주·대전·울산·강원은 최신 값 미확보.")
    KI_KINDS = {f"ind_{cd.lower()}": {"name": f"주력 업종 · {KI_SHORT[cd]} ({cd})", "group": "industry", "count": ki_counts[f"ind_{cd.lower()}"],
                                       "placed": ki_counts[f"ind_{cd.lower()}"], "rule": f"{cd} {ki_names[cd]}. " + KI_RULE, "source": ki_src,
                                       "year": "2020", "missing": [], "precision_note": "county (도시 합계)", "national_disclosed": ki_nat[cd],
                                       "blank_rows": ki_blank[cd]} for cd in KI_CODES}
    key_ind = {"by_city": ki_by_city, "codes": KI_CODES, "names": ki_names, "short": KI_SHORT, "national_2020": ki_nat, "blank_rows_2020": ki_blank,
               "fields": ["2020 값", "2020 비공개 포함(1)", "최신 값", "최신 비공개 포함(1)", "최신 연도"], "threshold_share": KI_SHARE,
               "unmatched_2020": [f"{a} {b}" for a, b in k20_unmatched], "unmatched_latest": [f"{a} {b}" for a, b in kall_unmatched],
               "rule": KI_RULE}

    # =====================================================================
    # §7 댐 (WAMIS 댐 관측소 좌표, 이름이 정확히 같은 것만)
    # =====================================================================
    obs = read_rows("dam_observations.csv")

    def dam_key(s):
        return nospace(s).removesuffix("댐")

    obs_by = collections.defaultdict(list)
    for r in obs:
        obs_by[dam_key(r["name"])].append(r)
    dams_5a = [u for u in resources["unplaced"] if u["kind"] == "dam"]
    D_items, dam_left, dam_fail = [], [], []
    used_obs = set()
    for u in dams_5a:
        k = dam_key(u["name"])
        hit = obs_by.get(k, [])
        if len(hit) != 1:
            dam_left.append(u)
            if len(hit) > 1:
                dam_fail.append({"name": u["name"], "reason": f"같은 이름의 관측소가 {len(hit)}곳"})
            continue
        r = hit[0]
        lon, lat = fnum(r["lon"]), fnum(r["lat"])
        used_obs.add(r["name"])
        if lon is None or lat is None:
            dam_left.append(u)
            dam_fail.append({"name": u["name"], "reason": "같은 이름의 관측소에 좌표가 없음"})
            continue
        ux, uy = W.lonlat2u(lon, lat)
        c, why = W.snap(ux, uy)
        if c is None:
            dam_left.append(u)
            dam_fail.append({"name": u["name"], "reason": f"관측소 좌표가 {why}"})
            continue
        det = [f"총저수용량 {u['value']:,} 백만㎥" if u.get("value") is not None else "총저수용량 자료 없음",
               f"종류 {u.get('type') or '–'} · 높이 {u.get('height_m') if u.get('height_m') is not None else '–'} m · 준공 {u.get('completed') or '–'}",
               f"위치: WAMIS 댐 관측소 '{r['name']}' 좌표 {lon:.5f}, {lat:.5f} (댐 구조물 중심점이 아니라 관측소 위치)"]
        D_items.append(item("dam", u["name"], c, "point", [W.code_of[c]], value=u.get("value"), unit="백만㎥ (총저수용량)", year=None,
                            ref=u["id"], dam_type=u.get("type"), height_m=u.get("height_m"), completed=u.get("completed"),
                            lon=lon, lat=lat, place_from="observation", source="wamis-dam-observations", detail=det))
    rank_items(D_items)
    obs_only = sorted(r["name"] for r in obs if r["name"] not in used_obs)
    for u in dam_left:
        u["reason"] = ("원자료에 좌표·주소가 없고, WAMIS 댐 관측소 가운데 이름이 정확히 같은 것(공백·'댐' 접미만 무시)이 없음"
                       + next((f" ({f['reason']})" for f in dam_fail if f["name"] == u["name"]), ""))
    log(f"댐: 5a {len(dams_5a)}곳 중 관측소 이름 대응·좌표 {len(D_items)}곳, 못 놓음 {[u['name'] for u in dam_left]}; 관측소에만 있는 것 {len(obs_only)}")
    dk = resources["kinds"]["dam"]
    dk.update({"count": len(dams_5a), "placed": len(D_items),
               "rule": ("한국수자원공사 '댐별 제원 정보'의 댐 전부. 값은 총저수용량(백만㎥). 제원 파일에는 좌표가 없어, WAMIS 공개 WFS 의 댐 관측소(mbrf:dm_obsvtr, 50곳 중 "
                        "좌표 49곳) 가운데 이름이 정확히 같은 것(공백을 지우고 끝의 '댐'만 뗀 뒤 같음)의 좌표 칸에 놓는다(point, 바다 칸이면 두 칸 안의 가장 가까운 육지 칸). "
                        "관측소 좌표는 댐 구조물 중심점이 아니다. 대응되지 않은 댐은 목록에만 둔다. 관측소에만 있고 제원 파일에 없는 댐"
                        f"({len(obs_only)}곳: 조정지댐·한국수력원자력 댐 등)은 값이 없어 놓지 않는다. 5b 의 수면 이름('○○호')은 쓰지 않는다. "
                        f"결과: {len(dams_5a)}곳 중 {len(D_items)}곳 point, {len(dam_left)}곳 목록만."),
               "source": dk["source"] + [src("wamis-dam-observations", "dam_observations.csv")],
               "missing": [{"name": u["name"], "reason": u["reason"]} for u in dam_left], "precision_note": "point (관측소 좌표)",
               "obs_only": obs_only})
    resources["unplaced"] = [u for u in resources["unplaced"] if u["kind"] != "dam"] + dam_left

    # =====================================================================
    # §7 가행 광산 (한국광해광업공단 국내광산검색, 주소 -> 시군구)
    # =====================================================================
    mines = read_rows("active_mines.csv")

    def mine_unit(addr):
        toks = addr.split()
        if len(toks) < 2 and not (toks and toks[0] == "세종"):
            return None, "주소가 '시도 시군' 꼴이 아님"
        sd, rest = resolver.sido_of(toks[0])
        if sd is None or rest:
            return None, f"시도 '{toks[0]}' 를 모름"
        cand = [c for c in w["counties"] if c["sido"] == sd]
        if len(cand) == 1:
            return frozenset([cand[0]["code"]]), None
        t = toks[1]
        opts = [(nospace(c["name"]), frozenset([c["code"]])) for c in cand if " " not in c["name"]]
        opts += [(cc["name"], frozenset(cc["sgg"])) for cc in cities if cc["sido"] == sd and len(cc["sgg"]) > 1 and cc["name"].endswith("시")]
        hit = [codes for nm, codes in opts if t == nm or (nm[-1] in "시군구" and t == nm[:-1])]
        if len(hit) == 1:
            return hit[0], None
        return None, (f"시군 '{t}' 가 {sido_short[sd]}에 {len(hit)}곳" if hit else f"시군 '{t}' 가 {sido_short[sd]}에 없음")

    mine_cnt = collections.defaultdict(collections.Counter)
    mine_names = collections.defaultdict(list)
    mine_fail = []
    n_mine = 0
    for r in mines:
        n_mine += 1
        m = re.match(r"^가행광산·(.+)$", r["kind"].strip())
        if not m:
            raise ValueError(f"active_mines.csv 종류 형식이 다름: {r['kind']!r}")
        mins = [x.strip() for x in m.group(1).split(",") if x.strip()]
        codes, why = mine_unit(r["address"])
        if codes is None:
            mine_fail.append({"name": r["name"], "reason": f"소재지 '{r['address'].strip()}' — {why}", "minerals": mins})
            continue
        for mn in mins:
            mine_cnt[codes][mn] += 1
            mine_names[(codes, mn)].append(r["name"])
    n_placed = n_mine - len(mine_fail)
    by_min = collections.Counter()
    for codes, cn in mine_cnt.items():
        for mn, v in cn.items():
            by_min[mn] += v
    dist = collections.Counter(v for cn in mine_cnt.values() for v in cn.values())
    M_items = []
    for codes, cn in mine_cnt.items():
        for mn, v in cn.items():
            if v < MINE_MIN:
                continue
            nm = mine_names[(codes, mn)]
            M_items.append(item("mine", f"{mn} 광산 · {place_of(codes).split(' ', 1)[1]}", unit_center(codes), "county", codes, value=v,
                                unit=f"곳 ({mn} 가행 광산)", mineral=mn, year="2026-11", place_from="address", source="komir-mine-grid",
                                detail=[f"{mn} 가행 광산 {v}곳: " + ", ".join(nm[:15]) + (" …" if len(nm) > 15 else ""),
                                        "한국광해광업공단 국내광산검색 공개 표 (가행), 소재지 '시도 시군 읍면' → 시군구 (county). 좌표 없음"]))
    rank_items(M_items)
    mine_city, mine_sido = {}, {}
    for codes, cn in mine_cnt.items():
        cid = city_units(codes)
        if cid is not None:
            d = mine_city.setdefault(str(cid), collections.Counter())
            d.update(cn)
        sd = W.sido_of_code[sorted(codes)[0]]
        mine_sido.setdefault(sd, collections.Counter()).update(cn)
    mine_city = {k: dict(v.most_common()) for k, v in mine_city.items()}
    mine_sido = {k: dict(v.most_common()) for k, v in mine_sido.items()}
    log(f"광산: {n_mine}곳 = 시군구 대응 {n_placed} + 실패 {len(mine_fail)} {[f['reason'] for f in mine_fail]}; 광종별 {dict(by_min.most_common())}; "
        f"(시군구×광종) 수 분포 {dict(sorted(dist.items()))}; 아이콘 {len(M_items)} (≥{MINE_MIN})")
    mines_kind = {
        "name": "가행 광산 (광종별)", "group": "resources", "count": n_mine, "placed": len(M_items),
        "rule": (f"한국광해광업공단 국내광산검색 공개 표의 가행 광산 {n_mine}곳(명칭·광종·소재지; 좌표·기준일 없음, 수집 2026-11). 소재지 '시도 시군 읍면'의 시도(짧은 이름)와 "
                 "시군(이름 끝의 '시·군·구'를 뗀 이름, 그 시도 안에서 하나뿐일 때)을 현재 시군구로 읽는다(county, 일반구를 둔 시는 시 전체). "
                 f"광종이 둘 적힌 광산은 두 광종에 하나씩 센다. 시군구 × 광종 광산 수의 분포({', '.join(f'{k}곳 {v}' for k, v in sorted(dist.items()))})를 보고, "
                 f"같은 광종 가행 광산이 {MINE_MIN}곳 이상인 시군구에만 '광산' 아이콘(광종 표시)을 둔다. 모든 시군구의 광종별 수는 도시·시도 패널에. "
                 f"결과: {n_mine}곳 = 시군구 대응 {n_placed} + 소재지 대응 실패 {len(mine_fail)}. 5a 의 시도 집계 표(전국광산 통계, 연말 기준)는 그대로 두며, "
                 "이 표(수집 시점의 가행 목록)와 기준 시점이 다르다."),
        "source": [src("komir-mine-grid", "active_mines.csv", "공개 표 30쪽", title="한국광해광업공단 국내광산검색 공개 표 (가행)")], "year": "수집 2026-11 (표에 기준일 없음)",
        "missing": [{"name": f["name"], "reason": f["reason"]} for f in mine_fail], "precision_note": "county", "threshold": MINE_MIN,
        "distribution": {str(k): v for k, v in sorted(dist.items())}}
    if not PRF.is_off("mines"):
      resources["kinds"]["mines"]["rule"] += " 5d: 광산별 소재지(국내광산검색 가행 293곳)는 '가행 광산 (광종별)'에 따로 있다 — 이 시도 집계와 기준 시점이 다르다."

    # =====================================================================
    # §7 지식 불가사의 (과학기술원·출연연·대학 주소 8곳, 대학 연구비는 시도까지만)
    # =====================================================================
    camp = read_rows("research_campuses.csv")
    K_items, k_fail = [], []
    for r in camp:
        res = resolver.resolve(r["address"])
        if res is None:
            k_fail.append({"name": r["name"], "reason": f"주소 '{r['address']}' 를 시군구로 읽지 못함"})
            continue
        codes = sorted(res["codes"])
        K_items.append(item("knowledge", r["name"], unit_center(codes), "county", codes, value=None, unit=None, year=None, inst_kind=r["kind"],
                            place_from="address", source=r["source_id"],
                            detail=[f"{r['kind']} · 주소(기관 누리집 하단 연락처): {r['address']}", "주소 → 시군구 (county). 좌표 없음"]))
    fund = read_rows("university_research_funding.csv")
    frows = []
    for r in fund:
        v = fnum(r["value"])
        if r["unit"] != "천원":
            raise ValueError(f"대학 연구비 단위가 천원이 아님: {r['unit']}")
        sd, rest = resolver.sido_of(r["address"])
        frows.append({"name": r["name"], "won": None if v is None else int(round(v * 1000)), "sido": sd if sd and not rest else None,
                      "sido_raw": r["address"], "year": r["year"]})
    frows.sort(key=lambda x: -(x["won"] if x["won"] is not None else -1))
    for k, x in enumerate(frows):
        x["rank"] = k + 1
    f_by_sido = {}
    for x in frows:
        if x["sido"] is None or x["won"] is None:
            continue
        d = f_by_sido.setdefault(x["sido"], {"count": 0, "won": 0, "top": []})
        d["count"] += 1
        d["won"] += x["won"]
        if len(d["top"]) < 5:
            d["top"].append({"name": x["name"], "won": x["won"], "rank": x["rank"]})
    f_bad = [x["name"] for x in frows if x["sido"] is None]
    log(f"지식: 주소 {len(camp)}곳 중 county {len(K_items)}, 실패 {k_fail}; 대학 연구비 {len(frows)}행, 시도 못 읽음 {f_bad}, 1위 {frows[0]['name']}")
    know_kind = {"name": "지식 (과학기술원·연구기관·대학)", "group": "wonders", "count": len(camp), "placed": len(K_items),
                 "rule": ("기관 누리집 하단 연락처에서 읽은 주소 8곳(과학기술원 4 · 정부출연연구기관 2 · 대학 2)을 시군구로 읽어 그 시군구의 인구 가중 중심 칸(county)에 "
                          "'지식' 아이콘을 둔다. 출연연·대학은 일부만 확보했다(전국 목록이 아님). 대학별 연구비(대학알리미 2026 공시, 2025년 실적)는 소재지가 시도까지만 "
                          f"있어 지도에 놓지 않고 상위 {FUNDING_N}곳을 시도 패널과 연감에 순위로 싣는다."),
                 "source": [src("institution-", "research_campuses.csv", "기관 8곳 누리집", title="과학기술원·출연연·대학 누리집 하단 연락처 주소")], "year": "수집 2026-11",
                 "missing": k_fail, "precision_note": "county"}

    # =====================================================================
    # §7 국립공원 공식 면적
    # =====================================================================
    pa = read_rows("park_area.csv")
    pam = {}
    for r in pa:
        if r["unit"] != "km²":
            raise ValueError(f"park_area.csv 단위가 km² 가 아님: {r['unit']}")
        pam[nospace(r["name"])] = r
    park_un = []
    for p in wonders["parks"]:
        r = pam.get(nospace(p["short"]))
        if r is None:
            park_un.append(p["name"])
            continue
        p["boundary_km2"] = p.get("boundary_km2", p["area_km2"])
        p["area_km2"] = fnum(r["value"])
        p["land_km2"], p["sea_km2"] = fnum(r["land_km2"]), fnum(r["sea_km2"])
        p["designated"] = r["designated"]
        p["area_basis"] = "국립공원공단 2026 국립공원기본통계(수정 공표) 지정면적, 2025년 기준"
    area_sum = sum(p["area_km2"] for p in wonders["parks"] if p.get("designated"))
    for it in wonders["items"]:
        if it["kind"] != "national_park":
            continue
        p = next(x for x in wonders["parks"] if x["id"] == it["ref"])
        if not p.get("designated"):
            continue
        it["area_km2"] = p["area_km2"]
        line = f"공식 지정면적 {p['area_km2']:,.3f} km²" + (f" (육상 {p['land_km2']:,.3f} · 해상 {p['sea_km2']:,.3f})" if p["land_km2"] is not None else "") \
            + f" · 지정 {p['designated']} (국립공원공단 기본통계, 2025년 기준)"
        it["detail"] = [d for d in it["detail"] if not d.startswith("경계 파일 기준") and not d.startswith("경계 폴리곤 넓이")]
        it["detail"].insert(1, line)
    pk = wonders["kinds"]["national_park"]
    pk["rule"] = (f"국립공원공단 공원경계 파일의 공원 {len(wonders['parks'])}곳 전부. 넓이는 국립공원공단 2026 국립공원기본통계(수정 공표)의 지정면적(2025년 기준)을 "
                  f"공원 이름(띄어쓰기 무시)으로 붙였다: {len(wonders['parks']) - len(park_un)}/{len(wonders['parks'])}곳, 합 {area_sum:,.3f} km² (공표 합계 6,888.394 km²와 "
                  "0.001 km² 차이는 원표 그대로). 한려해상·태안해안·다도해해상·변산반도는 원표의 육상·해상 면적을 함께 적는다. 경계 파일('공원경계버퍼', 완충 띠 포함) "
                  "은 공원이 덮는 칸을 정하는 데만 쓴다: 칸의 표본점 37개 중 19개 이상이 폴리곤 안인 대한민국 육지 칸. 아이콘은 폴리곤 대표점이 든 칸(그 칸이 공원 칸이 "
                  "아니면 가장 가까운 공원 칸). 탐방객은 같은 기본통계의 2025년 값으로 아이콘 크기와 전국 화면의 순위에 반영한다. 금정산은 이 공표본 이후 지정돼 없다.")
    pk["source"] = [x for x in pk["source"] if x.get("key") != "knps-area-2025"] + [src("knps-area-2025", "park_area.csv")]
    pk["area_total_km2"] = round(area_sum, 3)
    pk["area_unmatched"] = park_un
    log(f"국립공원 면적: {len(wonders['parks']) - len(park_un)}/{len(wonders['parks'])} 대응, 합 {area_sum:,.3f} km², 못 붙임 {park_un}")

    # =====================================================================
    # §7 세계유산 (구성 유산 97행)
    # =====================================================================
    her, _, _ = load_heritage(W, resolver)
    her_by = collections.defaultdict(list)
    for h in her:
        her_by[nospace(h["name"])].append(h)
    comp_rows = read_rows("world_heritage_components.csv")
    order, groups = [], collections.defaultdict(list)
    for r in comp_rows:
        if r["kind"] not in groups:
            order.append(r["kind"])
        groups[r["kind"]].append(r)
    old = {e["name"]: e for e in wonders["world_heritage"]}

    def wkey(s):
        return re.sub(r"[^가-힣]", "", s).replace("과", "").replace("와", "")

    def old_match(name):
        k = wkey(name)
        eq = [e for n, e in old.items() if wkey(n) == k]
        if len(eq) == 1:
            return eq[0], "같은 이름"
        sub = [e for n, e in old.items() if len(wkey(n)) >= 2 and (wkey(n) in k or k in wkey(n))]
        return (sub[0], "이름이 다른 쪽에 포함") if len(sub) == 1 else (None, None)

    def addr_units(addr):
        """소재지 문자열 -> [(코드 집합, 읽은 낱말)] 또는 ([], 이유). '보성-순천'처럼 '-'로 이은 것은 여럿."""
        out = []
        for part in [p.strip() for p in re.split(r"-", addr) if p.strip()]:
            res = resolver.resolve(part)
            if res is not None:
                out.append((frozenset(res["codes"]), res.get("matched") or part))
                continue
            t = part.split()[0]
            uniq = sorted(set(stem.get(t, [])), key=lambda s: sorted(s))
            if len(uniq) == 1:
                out.append((uniq[0], t))
                continue
            if len(uniq) > 1:
                return [], f"소재지 '{addr}' 의 '{t}' 가 전국에 {len(uniq)}곳 (" + ", ".join(place_of(u) for u in uniq) + ")"
            sd, _ = resolver.sido_of(part)
            if sd is not None:
                return [], f"소재지 '{addr}' 가 시도({sido_short[sd]})까지만 있음"
            return [], f"소재지 '{addr}' 에서 시군구를 읽지 못함"
        return out, None

    whs, WH_items = [], []
    prec_cnt = collections.Counter()
    old_used = set()
    for kind_nm in order:
        rows = groups[kind_nm]
        sid = rows[0]["source_id"]
        wid = "wh-" + sid.removeprefix("khs-")
        prev, how = old_match(kind_nm)
        if prev:
            old_used.add(prev["name"])
        comps = []
        for r in rows:
            nm = r["name"].strip()
            hs = her_by.get(nospace(nm), [])
            cells = {h["cell"] for h in hs}
            if hs and len(cells) == 1:
                h = hs[0]
                codes = h["codes"] or [W.code_of[h["cell"]]]
                comps.append({"name": nm, "precision": "point", "cell": int(h["cell"]), "sgg": sorted(codes), "place_from": "heritage_name",
                              "matched": f"{h['kind']} {h['name']}", "address": r["address"]})
                continue
            units, why = addr_units(r["address"])
            note = f"같은 이름의 국가유산이 {len(hs)}건이고 좌표 칸이 달라 쓰지 않음; " if len(cells) > 1 else ""
            if units:
                codes = units[0][0]
                comps.append({"name": nm, "precision": "county", "cell": unit_center(codes), "sgg": sorted(codes), "place_from": "address",
                              "matched": note + f"소재지 '{r['address']}' → {place_of(codes)}", "address": r["address"],
                              "spans": sorted(set().union(*[u for u, _ in units])) if len(units) > 1 else None})
            else:
                comps.append({"name": nm, "precision": None, "cell": None, "sgg": None, "place_from": None, "address": r["address"],
                              "matched": note + why})
        for cp in comps:
            prec_cnt[cp["precision"] or "list"] += 1
        vis = prev["visitors"] if prev else None
        entry = {"id": wid, "name": kind_nm, "year": rows[0]["year"] or None, "components": comps, "visitors": vis,
                 "visitor_series": prev["visitor_series"] if prev else None, "visitor_match": (f"5a '{prev['name']}' ({how})" if prev else None),
                 "link": prev.get("link") if prev else None, "source": sid,
                 "counts": dict(collections.Counter(c["precision"] or "list" for c in comps))}
        whs.append(entry)
        # 아이콘: (칸, 정밀도)가 같은 구성 유산은 하나로
        bykey = collections.OrderedDict()
        for cp in comps:
            if cp["cell"] is None:
                continue
            bykey.setdefault((cp["cell"], cp["precision"]), []).append(cp)
        # 등재 건 안의 순위: 구성 유산이 많은 아이콘부터 (전국 화면에서는 등재 건마다 1위 아이콘만 그린다)
        for rk, ((cell, prc), cps) in enumerate(sorted(bykey.items(), key=lambda kv: (-len(kv[1]), kv[1][0]["name"]))):
            codes = sorted(set().union(*[set(c["sgg"]) for c in cps]))
            names = " · ".join(c["name"] for c in cps)
            det = [f"구성 유산 {len(cps)}건: {names}"]
            for c in cps[:6]:
                det.append(f"{c['name']} — " + (f"국가유산 '{c['matched']}' 의 좌표 (point)" if prc == "point" else f"{c['matched']} (county)"))
            det.append(f"관람객 {vis['value']:,}명 ({vis['year']}, 국가유산청 관람객 현황 '{vis['matched']}')" if vis else "관람객 자료 없음")
            WH_items.append(item("world_heritage", kind_nm, cell, prc, codes, ref=wid, value=vis["value"] if vis else None,
                                 unit="명" if vis else None, year=vis["year"] if vis else None, source=sid, component=names,
                                 place_from=cps[0]["place_from"], rank=rk + 1, n_comp=len(cps), detail=det))
    n_comp = sum(len(e["components"]) for e in whs)
    log(f"세계유산 {len(whs)}건, 구성 유산 {n_comp} = {dict(prec_cnt)}; 5a 관람객 대응 {[(e['name'], e['visitor_match']) for e in whs]}; 5a 에서 안 쓴 {set(old) - old_used}")
    for e in whs:
        log(f"   {e['name']}: {e['counts']} " + "; ".join(f"{c['name']}={c['precision'] or '목록'}" for c in e["components"] if c["precision"] != "county")[:300])
    wk = wonders["kinds"]["world_heritage"]
    wk.update({"count": len(whs), "placed": sum(1 for e in whs if any(c["cell"] is not None for c in e["components"])),
               "components": n_comp, "precision_counts": dict(prec_cnt),
               "rule": (f"국가유산포털이 열거한 세계유산 {len(whs)}건의 구성 유산 {n_comp}행(조선왕릉 40기는 궁능유적본부 일람표). 구성 유산마다: (1) 이름이 국가유산 목록"
                        "(국보·사적·명승·천연기념물, 좌표 있음)의 이름과 정확히 같으면(띄어쓰기만 무시) 그 좌표 칸(point, place_from 'heritage_name'). 같은 이름이 둘 이상이고 "
                        "좌표 칸이 다르면 쓰지 않는다. (2) 아니면 정리표의 소재지 문자열을 시군구로 읽는다(county, place_from 'address'): '시도 시군구' 표기, 또는 첫 낱말이 "
                        "현재 시·군 이름(끝의 '시·군'을 뗀 것 포함)이고 그 이름이 전국에 하나뿐일 때. '보성-순천'은 첫 곳에 놓고 나머지는 걸친 곳으로 적는다. (3) 소재지가 "
                        "시도까지만('서울', '제주도')이거나 이름이 전국에 둘 이상('고성')이면 지도에 놓지 않고 목록만. 같은 칸·같은 정밀도의 구성 유산은 아이콘 하나로 그린다. "
                        "5a 의 느슨한 이름 규칙(지역 낱말 뗀 이름이 낱말로 시작, 내용 문장의 사적 이름)은 쓰지 않는다. 관람객은 5a 에서 붙인 국가유산청 관람객 현황 값을 "
                        "등재 이름(한글만, '과·와' 무시)이 같거나 한쪽이 다른 쪽에 포함되고 그 대응이 하나뿐일 때 옮긴다. "
                        f"결과: 구성 유산 {n_comp} = point {prec_cnt['point']} + county {prec_cnt['county']} + 목록만 {prec_cnt['list']}."),
               "source": [s_ for s_ in wk["source"] if s_.get("key") != "khs-world-heritage"] + [src("khs-", "world_heritage_components.csv", "국가유산포털·궁능유적본부", title="국가유산포털 세계유산 해설·궁능유적본부 왕릉 일람표 (구성 유산)")],
               "year": wk.get("year", "") + " · 구성 유산 수집 2026-11",
               "missing": [{"name": f"{e['name']} · {c['name']}", "reason": c["matched"]} for e in whs for c in e["components"] if c["precision"] is None],
               "precision_note": "point (같은 이름 국가유산 좌표) · county (소재지 문자열)"})
    wonders["world_heritage"] = whs

    # =====================================================================
    # §7 한우 2026-10 (상위 15) · 돼지 시도 2026 3분기
    # =====================================================================
    hw = ec.table("livestock_hanwoo")
    for r in hw:
        if r["indicator"] != "hanwoo_stock" or r["year"] != "2026":
            raise ValueError(f"livestock_hanwoo.csv 행 형식이 다름: {r['indicator']} {r['year']}")
    hw_un = sorted({(r["sido_now"], r["name_raw"]) for r in hw if r["codes"] is None})
    hmap = ec.unit_map([r for r in hw if r["codes"] is not None], True)
    hv = sorted(((k, v) for k, v in hmap.items() if v is not None), key=lambda kv: -kv[1])
    hw_blank = sum(1 for r in hw if r["raw_empty"])
    CA = []
    for k, v in hv[:HANWOO_N]:
        CA.append(item("cattle", f"한우 · {place_of(k).split(' ', 1)[1]}", unit_center(k), "county", k, value=as_int(v), unit="마리 (2026-10 한우)",
                       year="2026-10", source="mtrace-hanwoo-202610",
                       detail=[f"2026년 10월 한우 사육 {int(v):,}마리 (암수 전체, 농장 소재지 기준)", "축산유통 통계누리 농장지역(시군구)별 소의 품종별 성별 사육두수"]))
    rank_items(CA)

    def per_city(umap):
        out = {}
        for c in cities:
            v = E.agg(umap, c["sgg"])
            if v is not None:
                out[str(c["id"])] = as_int(v)
            elif any(k & set(c["sgg"]) for k in umap):
                out[str(c["id"])] = None
        return out

    def per_sido(umap):
        out = {}
        for s in w["states"]:
            codes = [c["code"] for c in w["counties"] if c["sido"] == s["code"]]
            parts = [v for k, v in umap.items() if k <= set(codes)]
            out[s["code"]] = {"sum": as_int(sum(v for v in parts if v is not None)), "units": len(parts), "blank": sum(1 for v in parts if v is None)}
        return out

    farm = resources["farm"]
    NO_HANWOO = PRF.is_off("hanwoo")   # 공개판: 축산물이력제 한우 값을 싣지 않는다 (lib/profile.py EXCLUDE hanwoo)
    if NO_HANWOO:
        farm.pop("cattle", None)   # 5b 의 2019년 한우·육우 값도 화면에서 쓰지 않던 것이라 되살리지 않는다
        CA = []
    else:
        farm["cattle"] = {"by_city": per_city(hmap), "by_sido": per_sido(hmap), "year": "2026-10", "unit": "마리", "label": "한우"}
    pig = read_rows("livestock_pig_sido.csv")
    pig_sido, pig_nat = {}, None
    for r in pig:
        if r["indicator"] != "pig_stock" or r["unit"] != "두":
            raise ValueError(f"livestock_pig_sido.csv 행 형식이 다름: {r['indicator']} {r['unit']}")
        v = fnum(r["value"])
        if r["sido_now"] == "전국":
            pig_nat = as_int(v)
            continue
        sd = sido_code_of_name.get(r["sido_now"])
        if sd is None:
            raise ValueError(f"livestock_pig_sido.csv 시도를 모름: {r['sido_now']}")
        pig_sido[sd] = as_int(v)
    farm["pigs_sido_2026"] = {"by_sido": {s["code"]: pig_sido.get(s["code"]) for s in w["states"]}, "national": pig_nat, "period": "2026년 3분기",
                              "label": "돼지 (가축동향조사, 사육규모 합계)",
                              "missing": [sido_short[s["code"]] for s in w["states"] if s["code"] not in pig_sido],
                              "sum_sido": sum(v for v in pig_sido.values() if v is not None)}
    farm["livestock_blank"] = farm.get("livestock_blank", [])
    resources["kinds"]["cattle"] = None if NO_HANWOO else {
        "name": "한우 (사육 상위)", "group": "farm", "count": len(CA), "placed": len(CA),
        "rule": (f"축산유통 통계누리 '농장지역(시군구)별 소의 품종별 성별 사육두수' 2026년 10월 한우(암수 전체) 시군구 {len(hw)}행 가운데 상위 {HANWOO_N}곳에 아이콘. "
                 "농장 소재지 기준. 원표에 행이 없는 시군구는 자료 없음(0 이 아님). 5b 의 2019년 '한우·육우'(전국오염원조사) 아이콘을 대신한다. "
                 f"돼지는 시군구 값이 2019년(전국오염원조사)뿐이라 그대로 두고, 시도 패널에 2026년 3분기 시도별 돼지(가축동향조사)를 싣는다."),
        "source": [src("mtrace-hanwoo-202610", "livestock_hanwoo.csv")], "year": "2026-10", "missing": [], "precision_note": "county",
        "blank_rows": hw_blank, "unmatched": [f"{a} {b}" for a, b in hw_un]}
    resources["kinds"]["pigs"]["rule"] += f" 시도 패널에는 2026년 3분기 시도별 돼지(축산유통 통계누리 가축동향조사, 원표에 행이 있는 15개 시도 — {', '.join(farm['pigs_sido_2026']['missing'])} 없음)를 따로 싣는다."
    resources["kinds"]["pigs"]["source"] = resources["kinds"]["pigs"]["source"] + [src("mtrace-pig-sido-2026q3", "livestock_pig_sido.csv")]
    log(f"한우 상위 {HANWOO_N}: {[(i['name'], i['value']) for i in CA]}; 원표 {len(hw)}행, 빈 값 {hw_blank}, 대응 못 함 {hw_un}; "
        f"돼지 시도 {len(pig_sido)}곳 합 {farm['pigs_sido_2026']['sum_sido']:,} / 전국 행 {pig_nat:,}")

    # =====================================================================
    # 받지 못한 자료, 바뀐 문구
    # =====================================================================
    resources["knowledge"] = {
        "note": ("지식 불가사의: 과학기술원 4곳·정부출연연구기관 2곳·대학 2곳의 주소(기관 누리집)를 시군구로 읽어 지도에 놓았다(전국 목록이 아니다). "
                 f"대학별 연구비(대학알리미 2026 공시, 2025년 실적, {len(frows)}개 학교·캠퍼스)는 소재지가 시도까지만 있어 지도에 놓지 않고 상위 {FUNDING_N}곳을 순위로 싣는다. "
                 f"국가과학기술연구회 소관 출연연 {len(resources.get('knowledge', {}).get('research_institutes', []))}곳은 이름만 있어 목록으로만 둔다."),
        "research_institutes": resources.get("knowledge", {}).get("research_institutes", []),
        "funding_top": frows[:FUNDING_N], "funding_by_sido": f_by_sido, "funding_rows": len(frows), "funding_year": "2025 (2026 공시)",
        "funding_unit": "원 (원표 천원 × 1,000, 연구비 지원 계 남녀 합)",
        "source": resources.get("knowledge", {}).get("source", []) + [src("academyinfo-research-funding-2026", "university_research_funding.csv")]}
    resources["trade_routes"] = {"note": ROUTE_RULE}
    resources["unavailable"] = [
        {"name": "철도 중심선 (국가기본도·연속수치지형도)", "reason": "브이월드의 개별·선택 다운로드가 비로그인 상태에서 '로그인 후 이용해주세요'로 중단된다. 고속선·일반선 구분 필드도 미확인. 철도 선은 Natural Earth 1:10m 초안 그대로."},
        {"name": "군사시설보호구역 면적 (시군구·시도)", "reason": "KOSIS 2025 용도구역(시군구)의 분류와 LX 도시계획현황 PDF 에서 찾지 못했고, 국방부 게시물은 변경분만 다룬다."},
        {"name": "시군구 간 화물 기종점 (KTDB)", "reason": "자료 신청서·승인이 필요해 받지 않았다. 교역로는 시도 간 도로 화물만 그린다."},
        {"name": "주력 업종 2024년 값 (부산·광주·대전·울산·강원)", "reason": "지역 KOSIS 에서 시군구 축과 대상 중분류 6개를 함께 고를 수 없었고, 대전·울산 공표 PDF 는 표가 그림이라 숫자를 뽑지 못했다. 2020년 경제총조사 값만 있다."},
        {"name": "대학 전체 목록·소재 시군구", "reason": "대학 및 전문대학 표준데이터의 공개 CSV 요청이 HTTP 404 를 돌려줬다. 대학 연구비는 시도까지만 안다."},
        {"name": "돼지 시군구별 최신 사육 마릿수", "reason": "가축동향조사는 시도 단위만 확인했다. 시군구 돼지는 2019년 전국오염원조사 값 그대로."},
        {"name": "전국 공식 수출입 총액", "reason": "받은 시군구 표에 없다(원표의 시도 총계 17행은 정리표에 남기지 않았다). 전국 값은 시군구 공표값의 합."},
    ]

    # =====================================================================
    # 층 JSON 정리
    # =====================================================================
    wonders["items"] = [i for i in wonders["items"] if i["kind"] not in ("world_heritage", "knowledge")]
    nw = WH_items + K_items
    for k, it in enumerate(nw):
        it["id"] = f"w5d-{k}"
    wonders["items"] = nw + wonders["items"]
    wonders["kinds"] = {"world_heritage": wk, **{k: v for k, v in wonders["kinds"].items() if k != "world_heritage"}, "knowledge": know_kind}
    resources["items"] = [i for i in resources["items"] if i["kind"] not in ("cattle", "dam", "mine", "export_hub") and not i["kind"].startswith("ind_")]
    NO_MINES = PRF.is_off("mines")   # 공개판: 국내광산검색 가행 광산을 싣지 않는다 (lib/profile.py EXCLUDE mines)
    if NO_MINES:
        M_items = []
    nr = CA + D_items + M_items + KI_items + EH
    for k, it in enumerate(nr):
        it["id"] = f"r5d-{k}"
    resources["items"] += nr
    resources["kinds"].pop("key_industries", None)
    resources["kinds"] = {**resources["kinds"], "mine": mines_kind, **KI_KINDS, "export_hub": trade_kind}
    resources["key_industries"] = key_ind
    resources["mines_5d"] = {"by_city": mine_city, "by_sido": mine_sido, "by_mineral": dict(by_min.most_common()), "count": n_mine,
                             "placed": n_placed, "failed": mine_fail, "threshold": MINE_MIN}
    if NO_MINES:
        resources["kinds"].pop("mine")
        resources.pop("mines_5d")
    if NO_HANWOO:
        resources["kinds"].pop("cattle")
    for obj in (wonders, resources, infra):
        obj["version"] = VERSION
        obj["precision_counts"] = dict(collections.Counter(i["precision"] for i in obj["items"]))
        for it in obj["items"]:
            v = it.get("value")
            if isinstance(v, float) and v.is_integer():
                it["value"] = int(v)
    for nm, obj in (("wonders", wonders), ("resources", resources), ("infrastructure", infra)):
        size = save_json(site(f"{nm}.json"), obj)
        log(f"{nm}.json {size / 1e3:.0f} KB, 아이콘 {len(obj['items'])}개, 정밀도 {obj['precision_counts']}")
    size = save_json(site("trade.json"), trade_json)
    log(f"trade.json {size / 1e3:.0f} KB")
    save_json(site("cities.json"), cities)
    save_json(site("states.json"), states)
    cv = nation.get("econ", {}).get("coverage", {}).get("lens_land_coverage_pct")
    if cv is not None and lens_made:
        cv["export_pc"] = round(100 * cov, 1)
    save_json(site("nation.json"), nation)
    if not any("1인당 수출" in n for n in lenses.get("notes", [])):
        lenses.setdefault("notes", []).append("5d 렌즈: 1인당 수출은 관세청 시군구 수출(제조장소 기준) ÷ 주민등록 인구, 시군구 값을 칸에 펼친다.")
    save_json(site("lenses.json"), lenses)
    save_json(build("layers5d_audit.json"), {
        "trade_unmatched": unmatched_tr, "trade_unmatched_value": unm_val, "trade_top5": top5, "ki_national": ki_nat, "ki_blank": ki_blank,
        "dams_left": [u["name"] for u in dam_left], "dam_obs_only": obs_only, "mines_failed": mine_fail,
        "wh": [{"name": e["name"], "counts": e["counts"], "components": e["components"]} for e in whs],
        "parks_unmatched": park_un, "hanwoo_unmatched": hw_un, "lens_export_cov": cov}, compact=False)


if __name__ == "__main__":
    sys.exit(main())

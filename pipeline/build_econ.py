"""경제 산출과 살림·산업·일상·배움·신앙·땅 렌즈 (명세 3단계).

입력: data/build/econ/*.csv (읽기만), site/data/{world,cities,states,nation,lenses}.json (1단계 산출)
출력: site/data/{cities,states,nation,lenses}.json 에 필드·렌즈를 더해 다시 쓴다. data/build/econ_audit.json.
"""
import collections
import math
import re
import statistics
import sys

import numpy as np

from lib import econ as E
from lib import housing as HS
from lib import profile as PRF
from lib import official as OF_
from lib import units as U
from lib.address import AddressResolver
from lib.common import build, load_json, rnd, save_json, site

YIELDS = {
    "food": ["agriculture"],
    "production": ["manufacturing", "construction", "mining"],
    "gold": ["grdp"],
    "science": ["information", "business_services"],
    "culture": ["culture_other"],
}
WON = 1_000_000  # 정리표 GRDP 단위 백만원 -> 원


def log(*a):
    print("[econ]", *a, flush=True)


def is_total(name):
    return E.nospace(name) in ("합계", "전산업", "계")


def is_manuf(name):
    n = re.sub(r"^[A-Z]", "", E.nospace(name))
    n = re.sub(r"\(.*\)$", "", n)
    return n == "제조업"


def median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def main():
    world = load_json(site("world.json"))
    cities = load_json(site("cities.json"))
    states = load_json(site("states.json"))
    nation = load_json(site("nation.json"))
    lenses = load_json(site("lenses.json"))
    dongs = load_json(build("dongs.json"))
    ec = E.Econ(world, cities)
    pop = E.Population(ec.cur)
    all_codes = frozenset(ec.cur)
    sido_codes = {s["code"]: frozenset(c for c in ec.cur if ec.sgg_sido[c] == s["code"]) for s in states}
    area = collections.Counter()
    for d in dongs:
        area[d["sgg"]] += d["area_km2"]

    # ---------------- GRDP ----------------
    grows = ec.table("grdp")
    gkey = {id(r): E.grdp_key(r["industry"]) for r in grows}  # 대응표에 없는 이름이면 여기서 오류
    G = collections.defaultdict(dict)  # 연도 -> 키 -> unit_map
    by = collections.defaultdict(list)
    for r in grows:
        if r["indicator"] != "grdp_current":
            continue
        by[(r["year"], gkey[id(r)])].append(r)
    for (y, k), rs in by.items():
        G[y][k] = ec.unit_map(rs, additive=True)
    years = sorted(G)
    log(f"GRDP 연도 {years}, 산업 이름 {len({r['industry'] for r in grows})}가지 -> 표준 키 {len({gkey[id(r)] for r in grows})}개")

    # ---------- 5b: 시군구 GRDP 과거 연도 (2020년 기준 개편표) ----------
    # 지금 쓰는 최신 표와 같은 통계표 계열(source_id 의 기관·표 번호가 같고, 과거표 basis 가 '2020년 기준 개편')일 때만 이어서 증가율을 낸다.
    # 2015년 기준표(grdp_history_2015.csv)는 기준년이 달라 이어 붙이지 않는다. 증가율에만 쓰고 산출·렌즈에는 쓰지 않는다.
    def table_id(s):
        return re.sub(r"^layers-", "", s or "")

    cur_src = collections.defaultdict(set)   # (연도, 단위) -> 최신 표 source
    for r in grows:
        if r["indicator"] == "grdp_current" and gkey[id(r)] == "grdp":
            cur_src[(r["year"], r["codes"])].add(r["source"])
    hrows = [r for r in ec.table("grdp_history") if r["indicator"] == "grdp_current"]
    h2015 = [r for r in ec.table("grdp_history_2015") if r["indicator"] == "grdp_current"]
    hkey = {id(r): E.grdp_key(r["industry"]) for r in hrows}
    GH = collections.defaultdict(lambda: collections.defaultdict(dict))   # 표 번호 -> 연도 -> 단위 지도 (GRDP 만)
    hb = collections.defaultdict(list)
    h_basis = collections.Counter()
    for r in hrows:
        if hkey[id(r)] != "grdp":
            continue
        h_basis[r["basis"]] += 1
        if "2020년 기준" not in r["basis"]:
            raise ValueError(f"grdp_history.csv 에 2020년 기준이 아닌 행: {r['basis']}")
        hb[(table_id(r["source"]), r["year"])].append(r)
    for (tid, y), rs in hb.items():
        GH[tid][y] = ec.unit_map(rs, additive=True)
    log(f"GRDP 과거표 {len(GH)}개 표 ({', '.join(sorted(GH))}), 2015년 기준표 {len({table_id(r['source']) for r in h2015})}개 표는 이어 붙이지 않음")
    splice_audit = {"rejected": [], "overlap_checked": 0, "no_overlap": 0}

    def growth_for(T, y, use_history=True):
        """명목 증가율: 5년 전이 있으면 그 해, 없으면 가장 이른 연도 -> y. 과거표는 같은 표 번호일 때만 잇는다."""
        a_now = E.agg(G[y].get("grdp", {}), T)
        if a_now is None:
            return None
        cand = {yy: (E.agg(G[yy]["grdp"], T), "same") for yy in years if yy < y and E.agg(G[yy].get("grdp", {}), T) is not None}
        T_ = frozenset(T)
        srcs = {table_id(s) for (yy, k), ss in cur_src.items() if yy == y and k <= T_ for s in ss}
        spliced = None
        if use_history and len(srcs) == 1:
            tid = next(iter(srcs))
            if tid in GH:
                # 겹치는 연도에서 최신 표와 과거표가 0.5% 넘게 다르면 잇지 않는다
                overlap = [yy for yy in GH[tid] if yy in G and E.agg(G[yy].get("grdp", {}), T) is not None
                           and E.agg(GH[tid][yy], T) is not None]
                bad = [(yy, E.agg(GH[tid][yy], T), E.agg(G[yy]["grdp"], T)) for yy in overlap
                       if abs(E.agg(GH[tid][yy], T) / E.agg(G[yy]["grdp"], T) - 1) > 0.005]
                if bad:
                    spliced = {"table": tid, "ok": False, "reason": f"겹치는 연도 값이 0.5% 넘게 다름: {bad}"}
                else:
                    for yy in GH[tid]:
                        v = E.agg(GH[tid][yy], T)
                        if yy < y and yy not in cand and v is not None:
                            cand[yy] = (v, "history")
                    spliced = {"table": tid, "ok": True, "overlap_years": overlap}
        if not cand:
            return {"_splice": spliced}
        target = str(int(y) - 5)
        frm = target if target in cand else min(cand)
        v, origin = cand[frm]
        return {"from": int(frm), "to": int(y), "rate": rnd(100 * (a_now / v - 1), 2),
                "series": "같은 표" if origin == "same" else f"과거표 이어 붙임 ({spliced['table']}, 2020년 기준 개편)",
                "_splice": spliced}

    def grdp_year(T):
        for y in reversed(years):
            if E.agg(G[y].get("grdp", {}), T) is not None:
                return y
        return None

    def gdp_block(T):
        y = grdp_year(T)
        if y is None:
            return None
        byi = {}
        for k in E.INDUSTRY_KEYS + ["net_taxes", "gva", "grdp"]:
            v = E.agg(G[y].get(k, {}), T)
            byi[k] = None if v is None else v * WON
        und = [k for k in E.INDUSTRY_KEYS + ["net_taxes"] if byi[k] is None]
        ylds = {}
        for name, ks in YIELDS.items():
            vals = [byi[k] for k in ks]
            ylds[name] = None if any(v is None for v in vals) else sum(vals)
        # 생산 예외: 광업만 비공개인 공표 단위는 그 광업 몫을 빼고 제조업 + 건설업 + 공개된 광업을 더한다 (광업을 추정해 넣지 않음).
        # 제조업이나 건설업이 하나라도 비공개면 그대로 null.
        partial, mining_excluded = {}, 0
        if ylds["production"] is None:
            T_ = frozenset(T)
            units = [k for k in G[y].get("grdp", {}) if k <= T_]
            tot, ok = 0.0, True
            for k in units:
                m = G[y].get("manufacturing", {}).get(k)
                c_ = G[y].get("construction", {}).get(k)
                mi = G[y].get("mining", {}).get(k)
                if m is None or c_ is None:
                    ok = False
                    break
                tot += m + c_ + (mi if mi is not None else 0)
                mining_excluded += mi is None
            if ok and mining_excluded:
                ylds["production"] = tot * WON
                partial["production"] = ["mining"]
            else:
                mining_excluded = 0
        # 명목 증가율: 5년 전, 없으면 가장 이른 연도 (5b: 같은 표 계열의 과거표를 이어서)
        gr = growth_for(T, y)
        gr0 = growth_for(T, y, use_history=False)
        growth = {k: v for k, v in gr.items() if not k.startswith("_")} if gr and "rate" in gr else None
        p, py = pop.get(T, y)
        return {"year": y, "by": byi, "undisclosed": und, "yields": ylds, "growth": growth,
                "growth_before": bool(gr0 and "rate" in gr0), "splice": (gr or {}).get("_splice"),
                "partial": partial, "mining_excluded": mining_excluded,
                "pop": p, "pop_ref": py, "per_capita": (byi["grdp"] / p) if p else None}

    # ---------------- 그 밖의 지표 ----------------
    def latest_map(series):
        return series[max(series)] if series else {}, (max(series) if series else None)

    wage_w = ec.series("income", "taxable_gross_wages")
    wage_f = ec.series("income", "wage_tax_filers")
    wy = max(set(wage_w) & set(wage_f))
    W_w, W_f = wage_w[wy], wage_f[wy]

    # 실거래가: 건별 원자료(data/raw/econ/housing)에서 12개월 전체 거래의 중위값을 직접 계산한다 (명세 5a §3.2).
    resolver = AddressResolver(world, cities)
    NO_HOUSING = PRF.is_off("housing")   # 공개판: 실거래 원자료를 읽지 않는다 (lib/profile.py EXCLUDE housing)
    HT = None if NO_HOUSING else HS.load(resolver)
    hmonth_range = [] if NO_HOUSING else HT["months"]
    hc = None if NO_HOUSING else HT["counts"]
    if NO_HOUSING:
        log("실거래: 공개판 — 아파트 매매·전세 원자료를 읽지 않고 값·렌즈·순위를 만들지 않는다")
    else:
      log(f"실거래 원자료 {len(hmonth_range)}개월 ({hmonth_range[0]}~{hmonth_range[-1]}): 매매 {hc['sale']['rows']:,}행 "
        f"(포함 {hc['sale']['included']:,}, 해제 {hc['sale']['cancelled']:,}, 주소 대응 실패 {hc['sale']['unmapped']:,}, "
        f"값 오류 {hc['sale']['bad_value']:,}), 전월세 {hc['lease']['rows']:,}행 (전세 {hc['lease']['jeonse']:,}, "
        f"월세 {hc['lease']['monthly']:,}, 주소 대응 실패 {hc['lease']['unmapped']:,}, 값 오류 {hc['lease']['bad_value']:,})")

    def housing_for(T):
        s = HS.summarize(HT, T) or {"sale_per_m2": None, "sale_median": None, "jeonse_median": None,
                                    "trades": None, "jeonse_trades": None}
        s["months"] = f"{hmonth_range[0]}~{hmonth_range[-1]}" if hmonth_range else None
        s["method"] = "전체 거래 중위값"
        return s

    emp, emp_y = latest_map(ec.series("employment", "employment_rate", additive=False))
    unemp, _ = latest_map(ec.series("employment", "unemployment_rate", additive=False))
    fis, fis_y = latest_map(ec.series("finance", "fiscal_independence", additive=False))

    work_t = ec.series("business", "establishment_workers", industry=is_total)
    work_m = ec.series("business", "establishment_workers", industry=is_manuf)

    def workers_for(T):
        out = {"total": None, "manufacturing": None, "year": None, "manufacturing_year": None}
        for y in sorted(work_t, reverse=True):
            v = E.agg(work_t[y], T)
            if v is not None:
                out["total"], out["year"] = int(v), int(y)
                break
        for y in sorted(work_m, reverse=True):
            v = E.agg(work_m[y], T)
            if v is not None:
                out["manufacturing"], out["manufacturing_year"] = int(v), int(y)
                break
        return out

    farm_h, fy = latest_map(ec.series("agriculture", "farm_households", years={"2020"}))
    farm_p, _ = latest_map(ec.series("agriculture", "farm_population", years={"2020"}))
    paddy, ly = latest_map(ec.series("land", "paddy_area"))
    upland, _ = latest_map(ec.series("land", "upland_area"))

    def farm_for(T):
        f = lambda m: (None if (v := E.agg(m, T)) is None else rnd(v, 0))  # noqa: E731
        return {"households": f(farm_h), "population": f(farm_p), "paddy_ha": f(paddy), "field_ha": f(upland),
                "year": int(fy) if fy else None, "land_year": int(ly) if ly else None}

    # 특별·광역시처럼 도시(시도) 값이 없고 소속 구마다 값이 있는 비율 지표: 합치거나 평균하지 않고 범위만 보인다 (명세 5a §3.1)
    def member_range(umap, T, label):
        if not umap or len(T) < 2 or E.single(umap, T) is not None:
            return None
        vals = [(c, umap.get(frozenset([c]))) for c in sorted(T)]
        got = [v for _, v in vals if v is not None]
        if not got:
            return None
        lo = min(vals, key=lambda t: t[1] if t[1] is not None else 1e18)
        hi = max(vals, key=lambda t: t[1] if t[1] is not None else -1e18)
        return {"min": rnd(lo[1], 1), "max": rnd(hi[1], 1), "n": len(got), "of": len(T), "unit_label": label,
                "min_sgg": lo[0], "max_sgg": hi[0]}

    def ranges_for(T, label):
        return {"employment": member_range(emp, T, label), "unemployment": member_range(unemp, T, label),
                "fiscal": member_range(fis, T, label)}

    # ---------------- 도시·시도·전국 ----------------
    def econ_fields(T, single_unit_ok=True):
        g = gdp_block(T)
        w_ = E.agg(W_w, T)
        f_ = E.agg(W_f, T)
        out = {
            "yields": g["yields"] if g else None, "gdp": g["by"]["grdp"] if g else None,
            "yields_partial": g["partial"] if g else {},
            "production_mining_excluded": g["mining_excluded"] if g else 0,
            "gdp_year": int(g["year"]) if g else None,
            "gdp_by_industry": g["by"] if g else None, "gdp_undisclosed": g["undisclosed"] if g else None,
            "gdp_per_capita": rnd(g["per_capita"], 0) if g and g["per_capita"] else None,
            "gdp_pop_ref": g["pop_ref"] if g else None,
            "gdp_growth": g["growth"] if g else None,
            "_growth_before": g["growth_before"] if g else False, "_splice": g["splice"] if g else None,
            "wage": {"per_filer": rnd(w_ * WON / f_, 0) if w_ is not None and f_ else None, "year": int(wy)},
            **({} if NO_HOUSING else {"housing": housing_for(T)}),
            "employment": {"rate": E.single(emp, T), "unemployment": E.single(unemp, T),
                           "period": f"{emp_y} 상반기" if emp_y else None},
            "fiscal_independence": E.single(fis, T), "fiscal_year": int(fis_y) if fis_y else None,
            "workers": workers_for(T), "farm": farm_for(T),
        }
        return out

    # ---------------- 산업 대분류별 종사자 (사업장 소재지 기준) ----------------
    brows = [r for r in ec.table("business") if r["indicator"] == "establishment_workers"]
    for r in brows:
        r["L"] = E.ksic_letter(r["industry"])  # 문자 없는 이름이면 여기서 빌드 오류
    by_sy = collections.defaultdict(list)
    for r in brows:
        by_sy[(r["source"], r["year"])].append(r)
    JB = []  # [(연도, 출처, {문자: unit_map})] 대분류 19개를 다 가진 출처만
    for (src_, y), rs in sorted(by_sy.items(), key=lambda kv: (-int(kv[0][1]), kv[0][0])):
        letters = {r["L"] for r in rs}
        if not set(E.KSIC) <= letters:
            continue  # 합계·제조업만 있는 표 (e-지방지표) 는 대분류 막대에 쓰지 않는다
        JB.append((y, src_, {L: ec.unit_map([r for r in rs if r["L"] == L], True) for L in list(E.KSIC) + ["total"]}))
    log(f"대분류 종사자 출처·연도 {len(JB)}개: " + ", ".join(sorted({f'{y}' for y, _, _ in JB})))

    def jobs_for(T):
        """대분류가 있는 가장 최근 연도의 한 출처가 T 를 빈틈없이 덮을 때만. 비공개는 None."""
        T = frozenset(T)
        for y, src_, um in JB:
            if not all(E.covered(um[L], T) for L in E.KSIC):
                continue
            jobs = {}
            for L in E.KSIC:
                vals = [v for k, v in um[L].items() if k <= T]
                jobs[L] = None if any(v is None for v in vals) else int(sum(vals))
            tot = None
            if um["total"] and E.covered(um["total"], T):
                tv = [v for k, v in um["total"].items() if k <= T]
                tot = None if any(v is None for v in tv) else int(sum(tv))
            return {"jobs": jobs, "jobs_year": int(y), "jobs_total": tot, "jobs_source": src_}
        return {"jobs": None, "jobs_year": None, "jobs_total": None, "jobs_source": None}

    empty_cities = []
    for c in cities:
        c.update(econ_fields(c["sgg"]))
        c.update(jobs_for(c["sgg"]))
        c["member_ranges"] = ranges_for(c["sgg"], "자치구") if c["kind"] in ("특별시", "광역시") else None
        if c["gdp"] is None:
            empty_cities.append(c["name"])
    log(f"도시 {len(cities)}곳 중 GRDP 있음 {sum(1 for c in cities if c['gdp'] is not None)}, "
        f"다섯 산출 모두 있음 {sum(1 for c in cities if c['yields'] and all(v is not None for v in c['yields'].values()))}")

    def mixed_year(blocks):
        ys = collections.Counter(b[0] for b in blocks)
        main_y = ys.most_common(1)[0][0]
        other = [f"{b[1]} {b[0]}" for b in blocks if b[0] != main_y]
        return f"{main_y}" + (f" ({', '.join(other)})" if other else "")

    sido_blocks = []
    for s in states:
        T = sido_codes[s["code"]]
        s.update(econ_fields(T))
        s["member_ranges"] = ranges_for(T, "구·군") if s["name"].endswith(("특별시", "광역시")) else None
        if s["gdp_year"]:
            sido_blocks.append((s["gdp_year"], s["short"], s))
        s["gdp_year_label"] = str(s["gdp_year"]) if s["gdp_year"] else None
    # 전국: 시도(=소속 시군구) 합. 연도가 섞이면 표기
    nat = econ_fields(all_codes)
    if all(s["gdp"] is not None for s in states):
        nat["gdp_by_industry"] = {k: (None if any(s["gdp_by_industry"][k] is None for s in states)
                                      else sum(s["gdp_by_industry"][k] for s in states)) for k in states[0]["gdp_by_industry"]}
        nat["gdp"] = nat["gdp_by_industry"]["grdp"]
        nat["yields"] = {k: (None if any(s["yields"][k] is None for s in states) else sum(s["yields"][k] for s in states))
                         for k in YIELDS}
        nat["production_mining_excluded"] = sum(s["production_mining_excluded"] for s in states)
        nat["yields_partial"] = {"production": ["mining"]} if nat["production_mining_excluded"] else {}
        nat["gdp_undisclosed"] = [k for k in E.INDUSTRY_KEYS + ["net_taxes"] if nat["gdp_by_industry"][k] is None]
        ptot = sum(pop.get(sido_codes[s["code"]], s["gdp_year"])[0] or 0 for s in states)
        nat["gdp_per_capita"] = rnd(nat["gdp"] / ptot, 0) if ptot else None
        nat["gdp_year"] = None
        nat["gdp_growth"] = None
    nat["gdp_year_label"] = mixed_year(sido_blocks)

    # 시도·전국 종사자: 소속 도시(= 소속 시군구) 합. 도시 하나라도 없으면 null, 연도가 섞이면 표기
    def sum_jobs(members, label_of):
        if not members or any(m["jobs"] is None for m in members):
            return {"jobs": None, "jobs_year": None, "jobs_year_label": None, "jobs_total": None}
        jobs = {L: (None if any(m["jobs"][L] is None for m in members) else sum(m["jobs"][L] for m in members)) for L in E.KSIC}
        tot = None if any(m["jobs_total"] is None for m in members) else sum(m["jobs_total"] for m in members)
        ys = collections.Counter(m["jobs_year"] for m in members)
        main_y = ys.most_common(1)[0][0]
        other = sorted({f"{label_of(m)} {m['jobs_year']}" for m in members if m["jobs_year"] != main_y})
        return {"jobs": jobs, "jobs_year": main_y, "jobs_total": tot,
                "jobs_year_label": f"{main_y}" + (f" ({', '.join(other)})" if other else "")}

    for s in states:
        s.update(sum_jobs([c for c in cities if c["sido"] == s["code"]], lambda m: m["name"]))
    nation["nation"].update(sum_jobs(states, lambda m: m["short"]))
    for c in cities:
        c["jobs_year_label"] = str(c["jobs_year"]) if c["jobs_year"] else None
    jy = collections.Counter(c["jobs_year"] for c in cities)
    log(f"종사자 대분류가 붙은 도시 {sum(1 for c in cities if c['jobs'])}/{len(cities)}, 연도 분포 {dict(jy)}, "
        f"없음: {[c['name'] for c in cities if not c['jobs']]}")
    nation["nation"].update(nat)

    # ---------------- 5b: 전국·시도 공식값 (official) ----------------
    OF = OF_.Official(world, resolver)
    if OF.unknown:
        raise ValueError(f"공식값 표의 지역 이름을 시도에 대응하지 못함: {dict(OF.unknown)}")
    og, og_check = OF.grdp()
    if og_check["bad"]:
        raise ValueError(f"지역소득 분류 합 점검 실패: {og_check['bad'][:5]}")
    ojobs = OF.jobs()
    oemp, surveys = OF.employment()
    ofis = OF.fiscal()
    ofarm = OF.farm()
    main_gdp_year = collections.Counter(str(s["gdp_year"]) for s in states if s["gdp_year"]).most_common(1)[0][0]
    o_years = sorted({y for d in og.values() for y in d})
    o_latest = o_years[-1]
    o_first = o_years[0]
    COMB = "광주 + 전남 합"
    PROV = "2024 잠정"  # 지역소득 표의 마지막 연도는 잠정치 (수집 보고서 B4)

    def parts_of(store, code):
        return {p: v for (c, p), v in store.items() if c == code and p}

    def add_maps(ds):
        keys = set().union(*[d.keys() for d in ds])
        return {k: (None if any(d.get(k) is None for d in ds) else sum(d[k] for d in ds)) for k in keys}

    def region_value(store, code, additive):
        """(값, 묶음 표시). 원표의 그 시도 행이 있으면 그것, 없고 부분만 있으면 더할 수 있는 값만 합친다."""
        if (code, None) in store:
            return store[(code, None)], None
        ps = parts_of(store, code)
        if ps and additive:
            if isinstance(next(iter(ps.values())), dict) and all(isinstance(v, dict) for v in ps.values()):
                ys = set.intersection(*[set(v) for v in ps.values()])
                if ys and all(isinstance(ps[p][y], dict) for p in ps for y in ys):
                    return {y: add_maps([ps[p][y] for p in sorted(ps)]) for y in ys}, COMB
                return add_maps([ps[p] for p in sorted(ps)]), COMB
        return None, None

    def ylds_of(b):
        return {name: (None if any(b.get(k) is None for k in ks) else sum(b[k] for k in ks)) for name, ks in YIELDS.items()}

    def official_for(code, T):
        o = {}
        gy, comb = region_value(og, code, True)
        if gy:
            b, bl = gy.get(main_gdp_year), gy.get(o_latest)
            p, _ = pop.get(T, main_gdp_year) if T else (None, None)
            g0 = gy.get(o_first, {}).get("grdp")
            o["gdp"] = {"year": int(main_gdp_year), "by": b, "yields": ylds_of(b), "grdp": b["grdp"],
                        "per_capita": rnd(b["grdp"] / p, 0) if p and b.get("grdp") else None,
                        "growth": ({"from": int(o_first), "to": int(main_gdp_year), "rate": rnd(100 * (b["grdp"] / g0 - 1), 2)}
                                   if g0 and b.get("grdp") else None),
                        "latest": {"year": int(o_latest), "label": PROV, "by": bl, "yields": ylds_of(bl), "grdp": bl["grdp"]} if bl else None,
                        "combined": comb, "source": "지역소득 (국가데이터처, 시도·전국, 생산지·당해년가격)"}
        jy, comb = region_value(ojobs, code, True)
        if jy:
            y_ = max(jy)
            d = jy[y_]
            o["jobs"] = {"year": int(y_), "by": {L: d.get(L) for L in E.KSIC}, "total": d.get("total"), "combined": comb,
                         "source": "전국사업체조사 (등록기반, 사업장 소재지)"}
        months = oemp.get((code, None)) or {}
        last = max(months) if months else None
        pe = {p: (v[max(v)] | {"month": max(v)}) for p, v in parts_of(oemp, code).items()}
        if last or pe:
            o["employment"] = {"rate": months[last].get("rate") if last else None,
                               "unemployment": months[last].get("unemployment") if last else None,
                               "month": last, "survey": "경제활동인구조사",
                               "label": f"경제활동인구조사 {last}" if last else None,
                               "parts": pe or None,
                               "note": ("경제활동인구조사(월) 값이다. 시군구 값은 지역별고용조사(반기)로 다른 조사라 직접 비교하지 않는다. "
                                        "월 값을 평균해 반기 값을 만들지 않았다.")}
        fv = ofis.get((code, None))
        pf = parts_of(ofis, code)
        if fv or pf:
            o["fiscal"] = {"avg": fv.get("avg") if fv else None, "hq": fv.get("hq") if fv else None,
                           "year": (fv or next(iter(pf.values())))["year"], "parts": pf or None,
                           "basis": "지방재정365 당초예산 (세입과목 개편 후)",
                           "note": "시도 전체 평균(시도 본청 + 소속 시군구 단체별 평균)과 본청 값. 비율이라 광주·전남은 더하지 않고 나란히 둔다."
                           if pf else "시도 전체 평균(시도 본청 + 소속 시군구 단체별 평균)과 본청 값."}
        fa, comb = region_value(ofarm, code, True)
        if fa:
            o["farm"] = {"paddy_ha": fa.get("paddy_ha"), "field_ha": fa.get("field_ha"), "cultivated_ha": fa.get("cultivated_ha"),
                         "year": fa.get("year") if comb is None else ofarm[next(iter(k for k in ofarm if k[0] == code))]["year"],
                         "combined": comb, "source": "농업면적조사 (경지 소재지)"}
        return o

    for s in states:
        s["official"] = official_for(s["code"], sido_codes[s["code"]])
    nation["nation"]["official"] = official_for("00", all_codes)
    # 시도 공식 GRDP 합 = 전국 (지역소득 표 안에서), 시군구 합과의 비교
    no = nation["nation"]["official"]
    sido_sum = sum(v[main_gdp_year]["grdp"] for (c, p), v in og.items() if c != "00" and main_gdp_year in v)
    nation["nation"]["official_compare"] = {
        "year": int(main_gdp_year), "sgg_sum_label": nat["gdp_year_label"],
        "grdp": {"official": no["gdp"]["grdp"], "sgg_sum": nat["gdp"], "diff": no["gdp"]["grdp"] - nat["gdp"],
                 "ratio": round(no["gdp"]["grdp"] / nat["gdp"], 4)},
        "yields": {k: {"official": no["gdp"]["yields"][k], "sgg_sum": nat["yields"][k],
                       "diff": (no["gdp"]["yields"][k] - nat["yields"][k]) if nat["yields"][k] is not None else None}
                   for k in YIELDS},
        "by": {k: {"official": no["gdp"]["by"].get(k), "sgg_sum": nat["gdp_by_industry"].get(k)} for k in E.INDUSTRY_KEYS + ["net_taxes", "gva", "grdp"]},
        "sido_sum_check": {"sido_rows_sum": sido_sum, "nation_row": no["gdp"]["grdp"], "ratio": round(sido_sum / no["gdp"]["grdp"], 5)},
        "jobs": {L: {"official": no["jobs"]["by"][L], "sgg_sum": (nation["nation"].get("jobs") or {}).get(L)} for L in E.KSIC},
    }
    # 특별·광역시·특별자치시 도시 패널: 자치구 범위 옆에 시도 공식값 (고용률·실업률·재정자립도). 통합특별시 안의 광주는 원표의 '광주' 부분
    for c in cities:
        sd_set = sido_codes[c["sido"]]
        ref = None
        if frozenset(c["sgg"]) == sd_set and c["kind"] in ("특별시", "광역시", "특별자치시"):
            st_ = next(s for s in states if s["code"] == c["sido"])
            emp_o, fis_o = st_["official"].get("employment"), st_["official"].get("fiscal")
            ref = {"scope": "시 전체", "employment": emp_o and {k: emp_o[k] for k in ("rate", "unemployment", "month", "label")},
                   "fiscal": fis_o and {k: fis_o[k] for k in ("avg", "hq", "year")}}
        elif c["sido"] == "12" and c["kind"] == "광역시":
            st_ = next(s for s in states if s["code"] == "12")
            emp_o, fis_o = st_["official"].get("employment") or {}, st_["official"].get("fiscal") or {}
            pe, pf = (emp_o.get("parts") or {}).get(c["name"]), (fis_o.get("parts") or {}).get(c["name"])
            if pe or pf:
                ref = {"scope": f"옛 {c['name']}광역시 (원표의 '{c['name']}' 행)",
                       "employment": pe and {"rate": pe.get("rate"), "unemployment": pe.get("unemployment"), "month": pe["month"],
                                             "label": f"경제활동인구조사 {pe['month']}"},
                       "fiscal": pf and {"avg": pf.get("avg"), "hq": pf.get("hq"), "year": pf.get("year")}}
        c["official_sido"] = ref
    n_gr_after = sum(1 for c in cities if c.get("gdp_growth"))
    n_gr_before = sum(1 for c in cities if c.get("_growth_before"))
    log(f"공식값: 지역소득 {o_first}–{o_latest} ({len(og)}개 지역·부분), 분류 점검 {og_check['checked']}건 통과, "
        f"전국 공식 GRDP {main_gdp_year} {no['gdp']['grdp'] / 1e12:,.1f}조 / 시군구 합 {nat['gdp'] / 1e12:,.1f}조 "
        f"(비율 {nation['nation']['official_compare']['grdp']['ratio']}), 시도 합/전국 {nation['nation']['official_compare']['sido_sum_check']['ratio']}")
    log(f"공식값: 고용 {surveys} 최신 월 {no['employment']['month']}, 재정자립도 {no['fiscal']['year']}, 경지 {no['farm']['year']}, "
        f"종사자 {no['jobs']['year']} 합계 {no['jobs']['total']:,}")
    # 시군구 GRDP 증가율: 과거표를 이어 붙인 전·후
    growth_audit = {"before": n_gr_before, "after": n_gr_after, "spliced": [], "rejected": [], "from_years": {},
                    "history_tables": sorted(GH), "history_2015_tables": sorted({table_id(r["source"]) for r in h2015}),
                    "overlap_years": {}}
    for c in cities:
        sp = c.get("_splice")
        g_ = c.get("gdp_growth")
        if sp and not sp["ok"]:
            growth_audit["rejected"].append({"city": c["name"], "sido": c["sido"], "reason": sp["reason"]})
        if g_ and "과거표" in g_.get("series", ""):
            growth_audit["spliced"].append(c["name"])
        if sp:
            growth_audit["overlap_years"][c["name"]] = sp.get("overlap_years")
        if g_:
            growth_audit["from_years"][str(g_["from"])] = growth_audit["from_years"].get(str(g_["from"]), 0) + 1
    no_overlap = sum(1 for v in growth_audit["overlap_years"].values() if v == [])
    log(f"시군구 GRDP 증가율이 붙은 도시: 이어 붙이기 전 {n_gr_before} -> 후 {n_gr_after} (과거표 이어 붙임 {len(growth_audit['spliced'])}곳, "
        f"시작 연도 {growth_audit['from_years']}), 이어 붙이지 않은 도시 {[r['city'] for r in growth_audit['rejected']]}, "
        f"과거표와 최신 표가 겹치는 연도가 없어 0.5% 대조를 못 한 도시 {no_overlap}곳")
    for o_ in [*cities, *states, nation["nation"]]:
        o_.pop("_growth_before", None)
        o_.pop("_splice", None)
    def rank(key_fn, desc=True):
        vals = [(key_fn(c), c["id"]) for c in cities if key_fn(c) is not None]
        vals.sort(key=lambda t: (-t[0] if desc else t[0], t[1]))
        return {cid: n + 1 for n, (_, cid) in enumerate(vals)}

    rk = {
        "gdp": rank(lambda c: c["gdp"]),
        "gdp_per_capita": rank(lambda c: c["gdp_per_capita"]),
        "food": rank(lambda c: c["yields"] and c["yields"]["food"]),
        "production": rank(lambda c: c["yields"] and c["yields"]["production"]),
        "science": rank(lambda c: c["yields"] and c["yields"]["science"]),
        "culture": rank(lambda c: c["yields"] and c["yields"]["culture"]),
        "wage": rank(lambda c: c["wage"]["per_filer"]),
        **({} if NO_HOUSING else {"housing": rank(lambda c: c["housing"]["sale_per_m2"])}),
    }
    for c in cities:
        for k, m in rk.items():
            c["ranks"][k] = m.get(c["id"])
    # 닮은 도시: 인구(로그)·고령 비율 + 1인당 GRDP(로그) + 산업 구성(16분류 비중). 없는 값은 그 차원을 뺀다
    feats = []
    for c in cities:
        f = {"lp": math.log10(max(c["population"], 1)), "o65": c["age"]["over65"]}
        if c["gdp_per_capita"]:
            f["lg"] = math.log10(c["gdp_per_capita"])
        if c["gdp_by_industry"] and c["gdp_by_industry"]["gva"]:
            for k in E.INDUSTRY_KEYS:
                v = c["gdp_by_industry"][k]
                if v is not None:
                    f["s_" + k] = v / c["gdp_by_industry"]["gva"]
        feats.append(f)
    keys = sorted({k for f in feats for k in f})
    mu = {k: np.mean([f[k] for f in feats if k in f]) for k in keys}
    sd = {k: (np.std([f[k] for f in feats if k in f]) or 1) for k in keys}
    wts = {k: (1.0 if not k.startswith("s_") else 1.0 / len(E.INDUSTRY_KEYS) * 2) for k in keys}
    for i, c in enumerate(cities):
        ds = []
        for j, o in enumerate(cities):
            if i == j:
                continue
            common = [k for k in keys if k in feats[i] and k in feats[j]]
            num_ = sum(wts[k] * ((feats[i][k] - feats[j][k]) / sd[k]) ** 2 for k in common)
            den = sum(wts[k] for k in common)
            ds.append((num_ / den if den else 1e9, j))
        ds.sort()
        c["peers"] = [cities[j]["id"] for _, j in ds[:5]]
        c["peer_rule"] = "인구·고령 비율·1인당 GRDP·산업 구성" if "lg" in feats[i] else "인구·고령 비율"

    # ---------------- 렌즈 ----------------
    county = np.array(world["county"])
    owner = np.array(world["owner"])
    land = owner >= 0
    N = len(county)

    def ratio_map(num_m, den_m, scale=100.0):
        out = {}
        for k, a in num_m.items():
            b = den_m.get(k)
            out[k] = None if a is None or b is None or b == 0 else a / b * scale
        return out

    def pop_ratio(num_m, year, scale):
        out = {}
        for k, a in num_m.items():
            p, _ = pop.get(k, year)
            out[k] = None if a is None or not p else a / p * scale
        return out

    def domain(vals, lo=2, hi=98):
        v = np.array([x for x in vals if x is not None], float)
        return [float(np.percentile(v, lo)), float(np.percentile(v, hi))] if len(v) else [0, 1]

    new = []
    notes_cover = {}

    county_codes = [c_["code"] for c_ in world["counties"]]

    namer = U.Namer(world, cities)

    def add(lid, group, name, emoji, unit, fmt, scale, ramp, higher, basis, vintage, source, desc, umap, nd=1, unit_year=None, **extra):
        # 시군구 단위 렌즈라 칸 배열 대신 시군구 배열(world.counties 순서)로 싣는다. 화면에서 칸으로 펼친다.
        # 여러 시군구에 걸친 공표 단위(시 전체·개편 전 구)는 lens.units 에 이름과 함께 적는다 (감사 01). unit_year: 단위별 값의 연도
        cval = {}
        for k, v in umap.items():
            for code in k:
                cval[code] = v
        by_county = [rnd(cval.get(code), nd) if cval.get(code) is not None else None for code in county_codes]
        vals = [by_county[county[i]] if land[i] else None for i in range(N)]
        nl = int(land.sum())
        cov = sum(1 for i, v in enumerate(vals) if land[i] and v is not None) / nl
        notes_cover[lid] = round(100 * cov, 1)
        lens = {"id": lid, "group": group, "name": name, "emoji": emoji, "unit": unit, "format": fmt, "scale": scale,
                "ramp": ramp, "higher_is": higher, "basis": basis, "vintage": vintage, "source": source,
                "description": desc, "by_county": by_county, "coverage": round(cov, 4)}
        lens.update(extra)
        uy = unit_year or {}
        U.annotate(lens, [(k, uy.get(k, vintage)) for k, v in umap.items() if v is not None], namer)
        if "domain" not in lens:
            d = domain(vals)
            if scale == "diverging":
                c0 = extra.get("center", 0)
                m = max(abs(d[0] - c0), abs(d[1] - c0))
                d = [c0 - m, c0 + m]
            lens["domain"] = [rnd(d[0], 2), rnd(d[1], 2)]
        new.append(lens)

    SEQ_GOLD = ["#f6f1dc", "#e9dc9b", "#d9bf5c", "#bf9a32", "#8f6b1d", "#5a420f"]
    SEQ_TEAL = ["#eef6f4", "#c3e3dc", "#8cc8bb", "#52a596", "#287a6e", "#0f4e47"]
    SEQ_RED = ["#fbf0ec", "#f3cbbd", "#e79a83", "#d4664f", "#ad3a2f", "#741c1c"]
    SEQ_BLUE = ["#eef3f9", "#c9d9ec", "#97b8db", "#5f90c4", "#33669f", "#183f70"]
    SEQ_PURP = ["#f4f0f7", "#dccdea", "#bea4d6", "#9c79bc", "#78519f", "#4d2a78"]
    SEQ_GREEN = ["#f3f6e8", "#d5e8b4", "#a9d18a", "#73b161", "#3f8a43", "#1a5c2c"]
    SEQ_BROWN = ["#f7f1e6", "#e7d3b0", "#d0ae79", "#b2844b", "#875b2b", "#583816"]
    DIV = ["#a3242f", "#d9714f", "#f2c39c", "#f4efe6", "#b9dbe3", "#5b9fc2", "#215a91"]

    gv = nat["gdp_year_label"]  # 예: "2023 (세종 2024)"
    # 살림
    gdp_pc_map = {}
    gdp_pc_years = collections.Counter()
    gdp_pc_ky = {}
    for y in reversed(years):
        for k, v in G[y].get("grdp", {}).items():
            if any(k & kk for kk in gdp_pc_map) or v is None:
                continue
            p, _ = pop.get(k, y)
            if p:
                gdp_pc_map[k] = v * WON / p / 10000  # 만원/명
                gdp_pc_years[y] += 1
                gdp_pc_ky[k] = y
    add("gdp_pc", "living", "1인당 GRDP", "💰", "만원", "int", "log", SEQ_GOLD, "good", "생산지",
        gv, "각 시도 지역소득(GRDP), 행정안전부 주민등록 인구(같은 해 12월)",
        "지역내총생산(시장가격) ÷ 같은 해 12월 주민등록 인구. 생산지 기준 총생산을 등록 인구로 나누므로 "
        "공단·업무지구처럼 통근 유입이 많은 곳이 높게 나온다. 시 단위로만 공표된 곳은 일반구 칸에 같은 값을 칠한다.",
        gdp_pc_map, nd=0, unit_year=gdp_pc_ky)
    add("wage", "living", "1인당 총급여", "💵", "만원", "int", "linear", SEQ_GREEN, "good", "주소지", wy,
        f"국세청 국세통계 주소지별 근로소득 ({wy} 귀속)",
        "과세대상 총급여 ÷ 근로소득 신고 인원. 근로자의 주소지 기준이다.",
        ratio_map(W_w, W_f, 100.0), nd=0)
    hm, jm = {}, {}
    for u in ([] if NO_HOUSING else HT["units"]):
        k = frozenset(u.split("+"))
        a, b = HT["sale"][u]["per_m2"], HT["jeonse"][u]
        hm[k] = float(np.median(a)) if len(a) else None
        jm[k] = float(np.median(b)) if len(b) else None
    hm_txt = f"{hmonth_range[0]}~{hmonth_range[-1]}" if hmonth_range else None
    if not NO_HOUSING:
      add("home", "living", "아파트 매매가", "🏠", "만원/㎡", "int", "log", SEQ_RED, "neutral", "주소지(물건 소재지)",
        hm_txt, "국토교통부 아파트 매매 실거래가 (건별 원자료)",
        f"{hm_txt} 12개월 아파트 매매 거래 전체의 ㎡당 거래금액(거래금액 ÷ 전용면적) 중위값. 건별 원자료에서 직접 계산했고 "
        f"해제된 거래({hc['sale']['cancelled']:,}건)는 뺐다. 시군구별 포함 거래 {hc['sale']['included']:,}건.", hm, nd=0)
    if not NO_HOUSING:
      add("jeonse", "living", "아파트 전세가", "🔑", "만원", "int", "log", SEQ_PURP, "neutral", "주소지(물건 소재지)",
        hm_txt, "국토교통부 아파트 전월세 실거래가 (건별 원자료)",
        f"{hm_txt} 12개월 아파트 전세 계약(전월세구분 '전세') 전체의 보증금 중위값. 건별 원자료에서 직접 계산했다. "
        f"전세 {hc['lease']['jeonse']:,}건, 월세 {hc['lease']['monthly']:,}건은 뺐다.", jm, nd=0)
    add("employment", "living", "고용률", "👷", "%", "pct1", "linear", SEQ_TEAL, "good", "거주지", f"{emp_y} 상반기",
        "국가데이터처 지역별고용조사", "15세 이상 인구 중 취업자 비율 (반기, 시군 단위 표본조사). 세종은 이 표에 시군 값이 없다.", emp)
    add("fiscal", "living", "재정자립도", "🏛️", "%", "pct1", "linear", SEQ_BLUE, "good", "관할구역", fis_y,
        "행정안전부·국가데이터처 e-지방지표", "지방세와 세외수입이 일반회계 예산에서 차지하는 비율 (시군구 자치단체 기준). "
        "제주 행정시는 따로 공표되지 않는다.", fis)
    ast_y = "2025"
    ast, _ = latest_map(ec.series("assistance", "livelihood_general_recipients", years={ast_y}))
    add("assistance", "living", "기초생활 수급", "🤝", "%", "pct2", "linear", SEQ_RED, "bad", "거주지", ast_y,
        "보건복지부 국민기초생활보장 수급자 현황, 주민등록 인구", "일반수급자 ÷ 같은 해 12월 주민등록 인구.",
        pop_ratio(ast, ast_y, 100.0), nd=2)

    # 산업
    share_year = {}

    def share_map(key):
        out = {}
        for y in reversed(years):
            for k, g in G[y].get("grdp", {}).items():
                if any(k & kk for kk in out):
                    continue
                a = G[y].get(key, {}).get(k)
                out[k] = None if a is None or not g else a / g * 100
                share_year[k] = y
        return out

    add("manufacturing_share", "industry", "제조업 비중", "🏭", "%", "pct1", "linear", SEQ_BROWN, "neutral", "생산지",
        gv,
        "각 시도 지역소득(GRDP)", "지역내총생산 중 제조업 부가가치 비중 (명목). 비공개면 자료 없음.", share_map("manufacturing"), unit_year=share_year)
    add("farm_share", "industry", "농림어업 비중", "🌾", "%", "pct1", "linear", SEQ_GREEN, "neutral", "생산지",
        gv, "각 시도 지역소득(GRDP)", "지역내총생산 중 농업·임업·어업 부가가치 비중 (명목).", share_map("agriculture"), unit_year=share_year)
    cats = E.INDUSTRY_KEYS
    top, top_year = {}, {}
    for y in reversed(years):
        for k, gva in G[y].get("gva", {}).items():
            if any(k & kk for kk in top):
                continue
            top_year[k] = y
            vals = {c_: G[y].get(c_, {}).get(k) for c_ in cats}
            known = {c_: v for c_, v in vals.items() if v is not None}
            if not known or gva is None:
                top[k] = None
                continue
            best = max(known, key=known.get)
            rest = gva - sum(known.values())  # 비공개 산업이 가질 수 있는 최대 값
            top[k] = cats.index(best) if (len(known) == len(cats) or known[best] >= rest) else None
    cat_colors = ["#7cb342", "#8d6e63", "#5d4037", "#ffb300", "#a1887f", "#ef6c00", "#546e7a", "#f06292",
                  "#1e88e5", "#3949ab", "#8e24aa", "#00897b", "#c62828", "#26a69a", "#ec407a", "#fdd835"]
    add("top_industry", "industry", "최대 산업", "🏆", "", "cat", "category", cat_colors, "neutral", "생산지",
        gv, "각 시도 지역소득(GRDP)",
        "부가가치가 가장 큰 산업 (공공행정·부동산 포함 16분류). 비공개 산업이 1위일 가능성이 남으면 자료 없음.",
        top, nd=0, unit_year=top_year, categories=[E.INDUSTRY_KO[c_] for c_ in cats], domain=[0, len(cats) - 1])

    # 사람
    tfr, tfr_y = latest_map(ec.series("fertility", "total_fertility_rate", additive=False))
    add("fertility", "people", "합계출산율", "👶", "명", "f2", "linear", SEQ_TEAL, "good", "거주지", tfr_y,
        "국가데이터처 인구동향조사", "여성 1명이 평생 낳을 것으로 예상되는 출생아 수.", tfr, nd=3)
    mig, mig_y = latest_map(ec.series("migration", "net_migration"))
    add("migration", "people", "순이동률", "🚚", "‰", "f1", "diverging", DIV, "neutral", "거주지", mig_y,
        "국가데이터처 국내인구이동통계, 주민등록 인구", "연간 순이동(전입 − 전출) ÷ 같은 해 12월 주민등록 인구 × 1,000.",
        pop_ratio(mig, mig_y, 1000.0), nd=1, center=0)

    # 일상
    def lt(table, ind, **kw):
        return latest_map(ec.series(table, ind, **kw))

    one, hh_y = lt("households", "one_person_households")
    gen, _ = lt("households", "general_households")
    add("single", "daily", "1인 가구", "🧍", "%", "pct1", "linear", SEQ_PURP, "neutral", "거주지", hh_y,
        "국가데이터처 e-지방지표 (인구총조사 기반)", "일반가구 중 1인 가구 비율.", ratio_map(one, gen))
    own, tn_y = lt("tenure", "owner_occupied_households")
    gen2, _ = lt("tenure", "general_households")
    add("owner", "daily", "자가 점유", "🏡", "%", "pct1", "linear", SEQ_GREEN, "neutral", "거주지", tn_y,
        "국가데이터처 인구총조사", "일반가구 중 자기 집에 사는 가구 비율.", ratio_map(own, gen2))
    crow = [r for r in ec.table("commute") if r["indicator"] == "commuter_population"]
    cy_ = max(r["year"] for r in crow)
    bins = {}
    for b in sorted({r["industry"] for r in crow}):
        bins[b] = ec.unit_map([r for r in crow if r["industry"] == b and r["year"] == cy_], True)
    long_bins = [b for b in bins if re.match(r"^(60|90|120)분", E.nospace(b))]
    tot_bin = next(b for b in bins if E.nospace(b) == "계")
    lc = {}
    for k, t in bins[tot_bin].items():
        parts = [bins[b].get(k) for b in long_bins]
        lc[k] = None if t in (None, 0) or any(p_ is None for p_ in parts) else sum(parts) / t * 100
    add("long_commute", "daily", "긴 통근", "⏱️", "%", "pct1", "linear", SEQ_RED, "bad", "거주지", cy_,
        "국가데이터처 인구총조사 (통근·통학 소요시간)",
        f"12세 이상 통근·통학자 중 편도 60분 이상 비율. 공표 구간({', '.join(long_bins)})의 인원을 직접 더했다 (평균 추정 없음).", lc)
    doc, doc_y = lt("doctors", "medical_doctors_per_1000", additive=False)
    add("doctors", "daily", "의사 수", "🩺", "명/천명", "f1", "linear", SEQ_BLUE, "good", "의료기관 소재지 (분모는 같은 지역 주민등록인구)", doc_y,
        "국가데이터처 e-지방지표", "의료기관 소재지별 종사 의사 수 ÷ 같은 지역 주민등록인구 × 1,000 (원표 값). 그 지역에 사는 의사의 비율이 아니다 — "
        "병원이 몰린 도심(예: 종로구)은 다른 지역 주민도 진료하므로 높게 나온다.", doc, nd=2)

    # 배움
    erows = [r for r in ec.table("education")]
    ey = max(r["year"] for r in erows)
    grad = ec.unit_map([r for r in erows if r["indicator"] == "college_graduates_15_plus" and r["year"] == ey], True)
    den = ec.unit_map([r for r in erows if r["indicator"] == "education_population" and r["year"] == ey and
                       E.nospace(r["industry"]) == E.nospace("계 / 내국인(15세 이상)-계")], True)
    g25 = ec.unit_map([r for r in erows if r["indicator"] == "college_graduates_25_plus" and r["year"] == ey], True)
    p25 = ec.unit_map([r for r in erows if r["indicator"] == "population_25_plus" and r["year"] == ey], True)

    def degree_for(T):
        a_, b_ = E.agg(grad, T), E.agg(den, T)
        c_, d_ = E.agg(g25, T), E.agg(p25, T)
        return {"share_15": rnd(100 * a_ / b_, 1) if a_ is not None and b_ else None,
                "share_25": rnd(100 * c_ / d_, 1) if c_ is not None and d_ else None, "year": int(ey)}

    for o in cities:
        o["degree"] = degree_for(o["sgg"])
    for o in states:
        o["degree"] = degree_for(sido_codes[o["code"]])
    nation["nation"]["degree"] = degree_for(all_codes)
    log(f"25세 이상 대졸 비율이 있는 도시 {sum(1 for o in cities if o['degree']['share_25'] is not None)}/{len(cities)}")
    add("degree", "learn", "대졸 이상", "🎓", "%", "pct1", "linear", SEQ_BLUE, "good", "거주지", ey,
        "국가데이터처 인구총조사 (교육정도)",
        "15세 이상 내국인 중 대학(4년제 미만 포함) 졸업 이상 비율. 25세 이상 기준은 15–24세 하위 칸이 비공개라 계산할 수 없어 쓰지 않았다.",
        ratio_map(grad, den))

    # 신앙
    rrows = ec.table("religion")
    ry = max(r["year"] for r in rrows)
    withr = ec.unit_map([r for r in rrows if r["indicator"] == "population_with_religion"], True)
    cen = ec.unit_map([r for r in rrows if r["indicator"] == "census_population"], True)
    add("religion", "faith", "종교 인구", "🙏", "%", "pct1", "linear", SEQ_PURP, "neutral", "거주지", ry,
        "국가데이터처 인구주택총조사 (2015, 10년 주기)", "종교가 있다고 답한 인구 비율.", ratio_map(withr, cen))
    rel_names = sorted({r["industry"] for r in rrows if r["indicator"] == "religion_population"})
    relm = {n: ec.unit_map([r for r in rrows if r["indicator"] == "religion_population" and r["industry"] == n], True)
            for n in rel_names}
    rtop = {}
    for k, w_ in withr.items():
        vals = {n: relm[n].get(k) for n in rel_names}
        known = {n: v for n, v in vals.items() if v is not None}
        if not known or w_ is None:
            rtop[k] = None
            continue
        best = max(known, key=known.get)
        rest = w_ - sum(known.values())
        rtop[k] = rel_names.index(best) if known[best] >= rest else None
    rel_colors = {"불교": "#e0a030", "기독교(개신교)": "#3f6fb5", "기독교(천주교)": "#8e44ad", "유교": "#6d8b3a",
                  "원불교": "#d35454", "천도교": "#16a085", "대순진리회": "#c0392b", "대종교": "#7f8c8d", "기타": "#95a5a6"}
    add("religion_top", "faith", "최대 종교", "⛩️", "", "cat", "category", [rel_colors.get(n, "#999") for n in rel_names],
        "neutral", "거주지", ry, "국가데이터처 인구주택총조사 (2015)",
        "신자가 가장 많은 종교. 비공개 칸이 1위일 가능성이 남으면 자료 없음.", rtop, nd=0, categories=rel_names,
        domain=[0, len(rel_names) - 1])

    # 땅
    pm = {}
    for k, v in paddy.items():
        a = sum(area[c] for c in k)
        pm[k] = None if v is None or not a else v / (a * 100) * 100
    add("paddy", "land", "논 비율 (시군구 통계)", "🌾", "%", "pct1", "linear", SEQ_GREEN, "neutral", "시군구 (농업면적조사)", ly,
        "국가데이터처 농업면적조사, 행정동 경계 넓이",
        "시군구 통계 값: 농업면적조사의 시군구 논 면적(ha) ÷ 시군구 넓이(행정동 경계 2026-10-01)를 그 시군구의 모든 칸에 같은 값으로 칠한다. "
        "칸마다 센 토지피복지도의 논 비율은 '논 (칸)' 렌즈(paddy_share)다. 두 값은 조사 방법이 달라(경작 신고 기반 면적조사 vs 영상 판독 지도) 같지 않다. "
        "특·광역시의 여러 구를 합쳐 공표한 항목('OO군외')은 나눌 수 없어 자료 없음.",
        pm, nd=1)

    # 렌즈 묶음 정리: 1단계 렌즈를 그대로 두고 새 묶음을 더한다
    groups = lenses["groups"]
    for g_id, g_name in (("living", "살림"), ("industry", "산업"), ("daily", "일상"), ("learn", "배움"), ("faith", "신앙"), ("land", "땅")):
        if not any(g["id"] == g_id for g in groups):
            groups.append({"id": g_id, "name": g_name})
    keep = [l_ for l_ in lenses["lenses"] if l_["id"] not in {n["id"] for n in new}]
    # 1단계 렌즈에도 기준·어디서 센 값인지
    for l_ in keep:
        l_.setdefault("basis", "주민등록 주소지" if l_["id"] != "growth" else "주민등록 주소지")
        l_.setdefault("vintage", lenses["vintage"])
    lenses["lenses"] = keep + new
    order = ["people", "age", "future", "living", "industry", "daily", "learn", "faith", "land"]
    lenses["groups"] = sorted(groups, key=lambda g: order.index(g["id"]) if g["id"] in order else 99)

    # 연감용 산출 설명
    nation["econ"] = {
        "yields": [
            {"id": "food", "emoji": "🌾", "name": "식량", "rule": "GRDP 농업·임업 및 어업 부가가치"},
            {"id": "production", "emoji": "⚙️", "name": "생산", "rule": "제조업 + 건설업 + 광업 부가가치"},
            {"id": "gold", "emoji": "💰", "name": "금", "rule": "지역내총생산(시장가격) 전체"},
            {"id": "science", "emoji": "🔬", "name": "과학", "rule": "정보통신업 + 사업서비스업 부가가치"},
            {"id": "culture", "emoji": "🎭", "name": "문화", "rule": "문화 및 기타서비스업 부가가치"},
        ],
        "limits": [
            "GRDP 19분류는 산업 대분류보다 거칠다. '사업서비스업'에는 전문·과학·기술 서비스와 사업시설관리·임대가, "
            "'문화 및 기타서비스업'에는 예술·스포츠·여가와 협회·수리·개인서비스가 섞여 있다.",
            "시도마다 따로 작성하므로 기준연도가 다를 수 있다(대부분 2023, 세종 2024 잠정). 도시마다 gdp_year 를 둔다.",
            "금액(명목, 당해년가격)이라 물가와 산업 구조의 영향을 받는다. 종사자 수와 달리 자본집약 산업(정유·반도체)이 있는 도시가 크게 나온다.",
        ],
        "national_note": "시군구 합은 시도(소속 시군구) 합이다. 시도별 시군구 GRDP 는 작성 방식과 순생산물세 처리가 달라 국가데이터처 "
                         "지역소득의 전국·시도 공식값과 같지 않다. 전국·시도 화면은 공식값을 기본으로 보이고 시군구 합을 '시군구 합' 표시와 함께 나란히 둔다.",
        "official_note": (f"전국·시도 공식값: 지역소득(국가데이터처 KOSIS, {o_first}–{o_latest}, {o_latest}년은 잠정) 33개 분류를 표준 키 19개로 묶어 "
                          f"시군구 합과 같은 연도({main_gdp_year})를 기본으로, 최신({PROV})을 병기한다. 다섯 산출은 공식값으로 광업까지 넣어 계산한다. "
                          "33개 분류 대응: 광제조업·서비스업은 합계 분류라 쓰지 않고, 제조업 세분 7개는 제조업, 전문·과학·기술과 사업시설관리·임대는 "
                          "사업서비스업, 수도·하수·폐기물과 예술·스포츠·여가, 협회·수리·개인서비스는 문화 및 기타서비스업의 세분이다(값으로 합을 확인). "
                          f"명목 증가율은 {o_first} → {main_gdp_year}. 종사자는 전국사업체조사 2024 대분류. 고용률·실업률은 경제활동인구조사의 받은 것 중 최신 월 값이며, "
                          "시군구 값(지역별고용조사, 반기)과 다른 조사다. 재정자립도는 지방재정365 2026 당초예산의 시도 전체 평균과 본청. 논·밭 면적은 농업면적조사 2025."),
        "combined_note": ("전남광주통합특별시: 원표가 광주·전남을 따로 공표한 값은 금액·면적·인원처럼 더할 수 있는 것만 더해 '광주 + 전남 합'으로 쓰고, "
                          "비율(재정자립도)은 더하지 않고 광주와 전남 두 값을 나란히 보인다. 경제활동인구조사는 통합특별시 행을 따로 공표해 그 값을 쓴다."),
        "growth_note": (f"시군구 GRDP 명목 증가율: 최신 표와 같은 통계표 계열(기관·표 번호가 같고 과거표 basis 가 '2020년 기준 개편')의 과거 연도"
                        f"(grdp_history.csv, 표 {len(GH)}개)를 이어서, 5년 전이 있으면 그 해 → 최신, 없으면 계열에서 가장 이른 연도 → 최신으로 낸다(연도를 함께 적음). "
                        "2015년 기준 표(grdp_history_2015.csv, 대전·울산·충남·경북·제주의 2018–2019)는 기준년이 달라 이어 붙이지 않았다. "
                        "최신 표와 과거표가 겹치는 연도에서 0.5% 넘게 다르면 잇지 않는다(이번 자료는 과거표가 2022년까지, 최신 표가 2023년이라 겹치는 연도가 없어 "
                        f"이 대조가 걸린 도시는 {len(growth_audit['rejected'])}곳). 증가율이 붙은 도시 {n_gr_before} → {n_gr_after}곳."),
        "growth_audit": growth_audit,
        "undisclosed_note": "구성 산업이 하나라도 비공개면 그 산출은 '자료 없음'이다. 추정으로 메우지 않는다. "
                            "예외: 생산에서 광업만 비공개인 공표 단위가 있으면 그 단위의 광업 몫만 빼고 제조업 + 건설업 + 공개된 광업을 더한 부분 합계로 내고 "
                            "'광업 비공개 n곳 제외'로 표시한다(yields_partial). 광업은 이런 곳에서 규모가 아주 작아 통째로 비우는 쪽이 더 큰 왜곡이다. "
                            "제조업이나 건설업이 비공개면 생산은 '자료 없음'이다.",
        "jobs_note": "산업 대분류별 종사자는 사업장 소재지 기준(전국사업체조사 계열, 시도·국가데이터처 공표)이다. 도시마다 대분류가 있는 가장 최근 연도를 쓴다. "
                     "비공개 칸은 '비공개'로 두고 0 으로 바꾸지 않는다.",
        "jobs_vs_grdp_note": "과학·문화는 종사자 분류가 GRDP 분류보다 정확하다: 종사자는 전문·과학·기술(M)만, 예술·스포츠·여가(R)만 따로 셀 수 있지만 "
                             "GRDP 의 사업서비스업·문화 및 기타서비스업은 사업시설관리·협회·수리 등과 섞여 있다.",
        "jobs_map": {"food": ["A"], "production": ["B", "C", "F"], "science": ["J", "M"], "culture": ["R"]},
        "ksic_ko": E.KSIC_KO,
        "per_capita_note": "1인당 GRDP 는 생산지 기준 총생산을 같은 해 12월 주민등록 인구로 나눈 값이라 통근 유입이 큰 도시가 높게 나온다.",
**({} if NO_HOUSING else {
        "housing_note": f"아파트 가격은 국토교통부 실거래 건별 원자료에서 {hmonth_range[0]}~{hmonth_range[-1]} 12개월 전체 거래의 "
                        "중위값을 직접 계산했다 (㎡당 매매가 = 거래금액 ÷ 전용면적, 매매가, 전세 보증금). 여러 구로 된 도시·시도·전국은 "
                        "소속 시군구의 거래를 모두 모아 다시 낸 중위값이다 (중위값의 중위값이 아님). "
                        f"매매 원자료 {hc['sale']['rows']:,}행 중 해제 {hc['sale']['cancelled']:,}건·주소 대응 실패 {hc['sale']['unmapped']:,}건·"
                        f"값 오류 {hc['sale']['bad_value']:,}건을 뺐고, 전월세 {hc['lease']['rows']:,}행 중 전세 {hc['lease']['jeonse']:,}건만 썼다.",
        "housing_counts": hc}),
        "range_note": "고용률·실업률·재정자립도의 시군구 값은 자치구 단위로만 공표돼 특별·광역시 전체 값이 시군구 표에 없다. 비율은 합치거나 평균할 수 없어 "
                      "자치구 값의 범위(최저–최고)와 값이 있는 자치구 수를 보이고, 그 옆에 시도 공식값(고용은 경제활동인구조사 월, 재정자립도는 "
                      "지방재정365 시도 전체 평균·본청)을 함께 둔다. 두 고용 조사는 서로 다른 조사다.",
        "coverage": {"cities_with_gdp": sum(1 for c in cities if c["gdp"] is not None),
                     "cities_all_yields": sum(1 for c in cities if c["yields"] and all(v is not None for v in c["yields"].values())),
                     "cities_production_partial": sum(1 for c in cities if c.get("yields_partial", {}).get("production")),
                     "states_production_partial": sum(1 for s_ in states if s_.get("yields_partial", {}).get("production")),
                     "nation_production_mining_excluded": nat.get("production_mining_excluded", 0),
                     "lens_land_coverage_pct": notes_cover},
        "industry_keys": E.INDUSTRY_KEYS, "industry_ko": E.INDUSTRY_KO,
    }
    save_json(site("cities.json"), cities)
    save_json(site("states.json"), states)
    save_json(site("nation.json"), nation)
    size = save_json(site("lenses.json"), lenses)
    log(f"생산 부분 합계(광업 비공개 제외): 도시 {sum(1 for c in cities if c.get('yields_partial', {}).get('production'))}, "
        f"시도 {sum(1 for s_ in states if s_.get('yields_partial', {}).get('production'))}, 전국 제외 단위 {nat.get('production_mining_excluded', 0)}")
    save_json(build("econ_audit.json"), {
        "empty_yield_cities": {c["name"]: {"missing": [k for k, v in c["yields"].items() if v is None],
                                           "undisclosed": c["gdp_undisclosed"], "gdp_year": c["gdp_year"]}
                               for c in cities if c["yields"] and any(v is None for v in c["yields"].values())},
        "no_gdp": empty_cities,
        "ignored_rows": [{"table": t, "sido": s, "name": n, "rows": k} for (t, s, n), k in sorted(ec.ignored.items())],
        "lens_coverage_pct": notes_cover,
        "legacy_code_conflicts": [list(map(str, c_)) for c_ in ec.conflicts],
        "growth_audit": growth_audit,
        "official_check": og_check,
        "official_raw_empty": OF.raw_empty,
    }, compact=False)
    log(f"렌즈 {len(new)}개 추가 (총 {len(lenses['lenses'])}), lenses.json {size / 1e6:.2f} MB")
    log("렌즈 육지 칸 덮음(%): " + ", ".join(f"{k} {v}" for k, v in notes_cover.items()))
    log(f"정리표에서 현재 지역에 붙이지 못해 버린 행: {sum(ec.ignored.values())}")


if __name__ == "__main__":
    sys.exit(main())

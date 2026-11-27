"""7b단계 (명세 docs/ideas/site_r3.md): 두 화면(site/·신여지도)이 함께 쓰는 빌드 계산.

build_phase6.py 다음, build_sources.py 앞에 돌린다. 새 자료를 받지 않고 이미 빌드된 site/data/*.json 만 읽는다. 같은 입력이면 결과가 같다.

1. 입지계수(LQ)와 특성 표시 (#11): cities[i].lq_gdp, lq_jobs, tags · nation.lq_rule, nation.tag_rule
   분모는 공식 전국값(지역소득 nation.official.gdp.by, 전국사업체조사 nation.official.jobs). 임계 판정은 반올림 전 값으로 한다.
2. 전국 기준값 (#10): nation.benchmarks (같은 조사·같은 산식은 전국값, 조사가 다른 고용률·재정자립도는 값이 있는 도시의 중앙값)
3. 닮은 도시 근거 (#13): cities[i].peer_reasons — build_econ.py 가 닮은 도시를 고른 거리(네 축)를 그대로 다시 계산해 가장 가까운 두 축과
   뚜렷한 차이 한 가지를 적는다. 다시 계산한 닮은 도시 순서가 cities[i].peers 와 다르면 빌드를 멈춘다.
4. 추천 시점 (#20): nation.presets — 극값 규칙 여섯 가지로 고른 도시·구간. 손으로 고른 도시·좌표 없음.
"""
import math
import statistics
import sys

import numpy as np

from lib import profile as PRF
from lib.common import load_json, save_json, site
from lib.hexgrid import Grid

LQ_MIN_SHARE_STORE = 0.01   # 도시 안 비중 1% 이상만 저장
TAG_SHARE, TAG_LQ = 0.05, 1.5
SMALL_POP, SMALL_LQ = 50000, 10
RK_TOP = 10
EXT_TAG, GROWTH_TAG = 0.2, 10.0


def log(*a):
    print("[insights]", *a, flush=True)


def r1(v):
    return None if v is None else round(float(v), 1)


def lq_txt(v):
    """표시용 배수: 10 이상이면 정수"""
    return f"{round(v):d}" if v >= 10 else f"{v:.1f}"


# =====================================================================
# 1. 입지계수·특성 표시
# =====================================================================
def build_lq(cities, nation):
    E = nation["econ"]
    N = nation["nation"]
    OG = N["official"]["gdp"]
    OJ = N["official"]["jobs"]
    keys, ko, kko = E["industry_keys"], E["industry_ko"], E["ksic_ko"]
    nat_g = {k: OG["by"][k] / OG["by"]["grdp"] for k in keys}
    nat_j = {L: OJ["by"][L] / OJ["total"] for L in kko}
    RK_NAME = {"gdp_per_capita": "1인당 GRDP", "export": "수출", "wage": "1인당 총급여"}
    n_rk = {k: sum(1 for c in cities if (c.get("ranks") or {}).get(k) is not None) for k in RK_NAME}
    stats = {"ind": 0, "rk": 0, "pop": 0, "small": 0, "none": 0}
    for c in cities:
        b = c.get("gdp_by_industry")
        und = set(c.get("gdp_undisclosed") or [])
        lqg, cand = {}, []
        if b and b.get("grdp"):
            for k in keys:
                v = b.get(k)
                if v is None or k in und:
                    continue
                sh = v / b["grdp"]
                lq = sh / nat_g[k]
                if sh >= LQ_MIN_SHARE_STORE:
                    lqg[k] = round(lq, 1)
                if sh >= TAG_SHARE and lq >= TAG_LQ:       # 반올림 전 판정
                    cand.append((lq, k, sh))
        lqj = {}
        J, JT = c.get("jobs"), c.get("jobs_total")
        if J and JT:
            for L in kko:
                v = J.get(L)
                if v is None:
                    continue
                sh = v / JT
                if sh >= LQ_MIN_SHARE_STORE:
                    lqj[L] = round(sh / nat_j[L], 1)
        c["lq_gdp"] = lqg
        c["lq_jobs"] = lqj
        tags = []
        if cand:
            lq, k, sh = max(cand)
            small = c["population"] < SMALL_POP and lq >= SMALL_LQ
            yr_diff = c.get("gdp_year") != OG["year"]
            tags.append({"t": "ind", "k": k, "lq": round(lq, 2), "sh": r1(sh * 100), "nat": r1(nat_g[k] * 100),
                         "small": small, "yr_diff": yr_diff, "txt": f"{ko[k]} 비중 ×{lq_txt(lq)}"})
            stats["ind"] += 1
            stats["small"] += small
        R = c.get("ranks") or {}
        t2 = None
        for k in ("gdp_per_capita", "export", "wage"):
            r = R.get(k)
            if r is not None and r <= RK_TOP:
                t2 = {"t": "rk", "k": k, "r": r, "n": n_rk[k], "txt": f"{RK_NAME[k]} {r}위"}
                break
        if t2 is None and c.get("extinction_index") is not None and c["extinction_index"] < EXT_TAG:
            v = c["extinction_index"]
            vt = f"{v:.2f}" if round(v, 2) < EXT_TAG else f"{v:.3f}"   # 0.195 를 0.20 으로 적어 '0.2 미만'과 어긋나지 않게
            t2 = {"t": "pop", "k": "extinction", "v": round(v, 3), "txt": f"소멸위험지수 {vt} (0.2 미만)"}
        if t2 is None and c.get("growth_5y") is not None and c["growth_5y"] >= GROWTH_TAG:
            v = c["growth_5y"]
            t2 = {"t": "pop", "k": "growth_5y", "v": round(v, 2), "txt": f"5년 인구 +{v:.1f}%"}
        if t2:
            tags.append(t2)
            stats[t2["t"]] += 1
        if not tags:
            stats["none"] += 1
        c["tags"] = tags
    log(f"LQ·특성 표시: {stats}")
    lq_rule = (f"입지계수(LQ)는 도시의 업종별 비중을 전국 공식 비중으로 나눈 배수다. 부가가치는 도시 시군구 합 GRDP 의 업종 비중 ÷ 지역소득 공식 전국 비중({OG['year']}), "
               f"종사자는 도시 사업장 소재지 종사자 비중 ÷ 전국사업체조사 공식 전국 비중({OJ['year']}). 1.0이면 전국과 같다. 도시 안 비중 1% 이상인 업종만 싣고 비공개 업종은 계산하지 않는다. "
               f"패널은 도시 안 비중 {int(TAG_SHARE * 100)}% 이상이면서 배수 {TAG_LQ} 이상(반올림 전 값으로 판정)인 업종을 강조한다.")
    tag_rule = (f"도시 머리의 특성 표시는 최대 2개다. ① 업종: 비공개가 아닌 부가가치 16업종 가운데 도시 안 비중 {int(TAG_SHARE * 100)}% 이상·입지계수 {TAG_LQ} 이상(반올림 전 판정)인 업종 중 배수가 가장 큰 1개. "
                f"② 지표: 1인당 GRDP 순위 {RK_TOP}위 이내 → 수출 순위 {RK_TOP}위 이내 → 1인당 총급여 순위 {RK_TOP}위 이내 → 소멸위험지수 {EXT_TAG} 미만 → 5년 인구 증감 +{GROWTH_TAG:.0f}% 이상 가운데 먼저 맞는 1개. "
                f"지표 이름과 수치만 적고 평가하는 말은 붙이지 않는다. 인구 {SMALL_POP:,}명 미만이면서 배수 {SMALL_LQ} 이상이면 단일 사업장 영향 주의를, 도시 GRDP 연도가 전국 공식 연도와 다르면 연도 차이를 함께 적는다.")
    nation["nation"]["lq_rule"] = lq_rule
    nation["nation"]["tag_rule"] = tag_rule
    nation["nation"]["lq_nat"] = {"gdp": {k: round(v * 100, 2) for k, v in nat_g.items()}, "gdp_year": OG["year"],
                                  "jobs": {L: round(v * 100, 2) for L, v in nat_j.items()}, "jobs_year": OJ["year"]}


# =====================================================================
# 2. 전국 기준값
# =====================================================================
# (key, 이름, 도시 값 읽기, 전국 값 경로(None 이면 도시 중앙값), 단위, 형식, 방향, 비교 방식)
BENCH = [
    ("growth_5y", "5년 인구 증감", lambda c: c.get("growth_5y"), ("growth_5y",), "%", "pct1", "neutral", "diff"),
    ("over65", "65세 이상 비율", lambda c: c["age"].get("over65"), ("age", "over65"), "%", "pct1", "neutral", "diff"),
    ("under15", "0–14세 비율", lambda c: c["age"].get("under15"), ("age", "under15"), "%", "pct1", "neutral", "diff"),
    ("working", "15–64세 비율", lambda c: c["age"].get("working"), ("age", "working"), "%", "pct1", "neutral", "diff"),
    ("mean_est", "평균연령(추정)", lambda c: c["age"].get("mean_est"), ("age", "mean_est"), "세", "f1", "neutral", "diff"),
    ("median_est", "중위연령(추정)", lambda c: c["age"].get("median_est"), ("age", "median_est"), "세", "f1", "neutral", "diff"),
    ("sex_ratio_20_39", "청년 성비", lambda c: c.get("sex_ratio_20_39"), ("sex_ratio_20_39",), "", "f1", "neutral", "diff"),
    ("extinction_index", "소멸위험지수", lambda c: c.get("extinction_index"), ("extinction_index",), "", "f2", "neutral", "diff"),
    ("gdp_per_capita", "1인당 GRDP", lambda c: c.get("gdp_per_capita"), ("gdp_per_capita",), "원", "won", "neutral", "ratio"),
    ("wage", "1인당 총급여", lambda c: (c.get("wage") or {}).get("per_filer"), ("wage", "per_filer"), "원", "won", "neutral", "ratio"),
    ("sale_per_m2", "아파트 매매 ㎡당", lambda c: (c.get("housing") or {}).get("sale_per_m2"), ("housing", "sale_per_m2"), "만원", "man", "neutral", "ratio"),
    ("sale_median", "아파트 매매 중위", lambda c: (c.get("housing") or {}).get("sale_median"), ("housing", "sale_median"), "만원", "won1e4", "neutral", "ratio"),
    ("jeonse_median", "아파트 전세 중위", lambda c: (c.get("housing") or {}).get("jeonse_median"), ("housing", "jeonse_median"), "만원", "won1e4", "neutral", "ratio"),
    ("degree", "대졸 이상 (15세 이상)", lambda c: (c.get("degree") or {}).get("share_15"), ("degree", "share_15"), "%", "pct1", "neutral", "diff"),
    ("employment", "고용률", lambda c: (c.get("employment") or {}).get("rate"), None, "%", "pct1", "neutral", "diff"),
    ("fiscal", "재정자립도", lambda c: c.get("fiscal_independence"), None, "%", "pct1", "neutral", "diff"),
]
EQ = {"diff": 0.05, "diff_f2": 0.005, "ratio_pct": 0.5}
# 공개판: 아파트 매매·전세 값이 없다 (lib/profile.py EXCLUDE housing) — 그 기준값·순위 분모·닮은 도시의 매매가 차이를 만들지 않는다
NO_HOUSING = PRF.is_off("housing")
HOUSING_BENCH = ("sale_per_m2", "sale_median", "jeonse_median")
if NO_HOUSING:
    BENCH = [b for b in BENCH if b[0] not in HOUSING_BENCH]


def dig(o, path):
    for p in path:
        o = (o or {}).get(p)
    return o


def build_benchmarks(cities, nation):
    N = nation["nation"]
    metrics = {}
    for key, name, get, path, unit, fmt, dr, mode in BENCH:
        if path is not None:
            v = dig(N, path)
            if v is None:
                raise RuntimeError(f"전국 기준값 없음: nation.{'.'.join(path)}")
            m = {"v": v, "ref": "nation", "src": "nation." + ".".join(path)}
        else:
            vals = [get(c) for c in cities if get(c) is not None]
            m = {"v": round(statistics.median(vals), 2), "ref": "city_median", "n": len(vals)}
        m.update({"label": name, "unit": unit, "fmt": fmt, "dir": dr, "mode": mode})
        if key == "gdp_per_capita":
            # 전국 시군구 합은 2023 (세종만 2024). 도시 연도가 이와 다르면(세종) 화면이 연도를 함께 적는다
            m["year"] = int(N.get("gdp_pop_ref") or N["official"]["gdp"]["year"])
            m["year_label"] = N.get("gdp_year_label")
        metrics[key] = m
    RK = tuple(k for k in ("population", "growth", "over65", "extinction", "gdp", "gdp_per_capita", "food", "production", "science", "culture", "wage", "housing", "export")
               if not (NO_HOUSING and k == "housing"))
    den = {k: sum(1 for c in cities if (c.get("ranks") or {}).get(k) is not None) for k in RK}
    nation["nation"]["benchmarks"] = {
        "rule": ("같은 조사·같은 산식으로 낸 지표는 전국값(nation)과 비교한다: 인구·연령·소멸위험지수는 주민등록, 1인당 GRDP 는 시군구 합 GRDP(전국도 시군구 합, "
                 f"{N.get('gdp_year_label')})÷같은 해 12월 인구, 총급여·{'' if NO_HOUSING else '아파트 가격·'}대졸 비율은 같은 원표의 전국 행. 고용률(지역별고용조사 시군 반기)과 재정자립도(시·군·자치구)는 "
                 "같은 산식의 전국값이 없어 값이 있는 도시의 중앙값(city_median)과 비교한다. 비교 줄은 차이(diff: 값 − 기준) 또는 배수(ratio: 값 ÷ 기준 − 1)이며, "
                 f"차이가 {EQ['diff']}(소멸위험지수 {EQ['diff_f2']}) 미만이거나 배수 차이가 {EQ['ratio_pct']}% 미만이면 '수준 같음'으로 적는다. "
                 "값이 없거나, 자치구 범위로만 있거나, 도시와 기준의 연도가 다르면 비교 줄을 만들지 않거나 연도를 함께 적는다. 화살표는 크고 작음만 뜻하고 좋고 나쁨을 뜻하지 않는다. "
                 "순위 막대의 분모는 그 순위가 있는 도시 수다."),
        "eq": EQ,
        "metrics": metrics,
        "rank_denominators": den,
    }
    log(f"전국 기준값 {len(metrics)}개, 순위 분모 {den}")


# =====================================================================
# 3. 닮은 도시 근거 (build_econ.py 의 거리와 같은 계산)
# =====================================================================
AXIS_KO = {"pop": "인구", "age": "고령 비율", "gdp": "1인당 GRDP", "ind": "산업 구성"}


def build_peer_reasons(cities, nation):
    keys16 = nation["econ"]["industry_keys"]
    feats = []
    for c in cities:
        f = {"lp": math.log10(max(c["population"], 1)), "o65": c["age"]["over65"]}
        if c["gdp_per_capita"]:
            f["lg"] = math.log10(c["gdp_per_capita"])
        if c["gdp_by_industry"] and c["gdp_by_industry"]["gva"]:
            for k in keys16:
                v = c["gdp_by_industry"][k]
                if v is not None:
                    f["s_" + k] = v / c["gdp_by_industry"]["gva"]
        feats.append(f)
    keys = sorted({k for f in feats for k in f})
    sd = {k: (np.std([f[k] for f in feats if k in f]) or 1) for k in keys}
    wts = {k: (1.0 if not k.startswith("s_") else 1.0 / len(keys16) * 2) for k in keys}
    # build_econ.py 와 같은 순서가 나오는지 먼저 확인 (다르면 근거가 실제 선택과 어긋나므로 멈춘다)
    for i, c in enumerate(cities):
        ds = []
        for j in range(len(cities)):
            if i == j:
                continue
            common = [k for k in keys if k in feats[i] and k in feats[j]]
            num_ = sum(wts[k] * ((feats[i][k] - feats[j][k]) / sd[k]) ** 2 for k in common)
            den = sum(wts[k] for k in common)
            ds.append((num_ / den if den else 1e9, j))
        ds.sort()
        got = [cities[j]["id"] for _, j in ds[:5]]
        if got != c["peers"]:
            raise RuntimeError(f"닮은 도시 다시 계산이 build_econ 결과와 다름: {c['name']} {got} != {c['peers']}")
    idx = {c["id"]: i for i, c in enumerate(cities)}
    n_diff = {"growth": 0, "wage": 0, None: 0} if NO_HOUSING else {"home": 0, "growth": 0, "wage": 0, None: 0}
    for i, c in enumerate(cities):
        out = []
        for pid in c["peers"]:
            j = idx[pid]
            fi, fj, o = feats[i], feats[j], cities[j]
            ax = {"pop": ((fi["lp"] - fj["lp"]) / sd["lp"]) ** 2, "age": ((fi["o65"] - fj["o65"]) / sd["o65"]) ** 2}
            if "lg" in fi and "lg" in fj:
                ax["gdp"] = ((fi["lg"] - fj["lg"]) / sd["lg"]) ** 2
            cs = [k for k in keys if k.startswith("s_") and k in fi and k in fj]
            if cs:
                ax["ind"] = sum(((fi[k] - fj[k]) / sd[k]) ** 2 for k in cs) / len(cs)
            order = sorted(ax, key=lambda a: (ax[a], list(AXIS_KO).index(a)))
            same = order[:2]
            r = {"id": pid, "same": same}
            if "ind" in same:
                k = max(cs, key=lambda k: min(fi[k], fj[k]))
                r.update({"ind": k[2:], "ind_a": r1(fi[k] * 100), "ind_b": r1(fj[k] * 100)})
            if "gdp" in same and c.get("gdp_year") != o.get("gdp_year"):
                r["gdp_years"] = [c.get("gdp_year"), o.get("gdp_year")]
            ha, hb = c.get("housing") or {}, o.get("housing") or {}
            diff = None
            if (not NO_HOUSING and ha.get("sale_per_m2") is not None and hb.get("sale_per_m2") is not None and (ha.get("trades") or 0) >= 10 and (hb.get("trades") or 0) >= 10):
                q = ha["sale_per_m2"] / hb["sale_per_m2"]
                if max(q, 1 / q) >= 1.35:
                    diff = ["home", round(q, 2)]
            if diff is None and c.get("growth_5y") is not None and o.get("growth_5y") is not None and abs(c["growth_5y"] - o["growth_5y"]) >= 5.0:
                diff = ["growth", round(c["growth_5y"] - o["growth_5y"], 1)]
            wa, wb = (c.get("wage") or {}).get("per_filer"), (o.get("wage") or {}).get("per_filer")
            if diff is None and wa and wb and max(wa / wb, wb / wa) >= 1.15:
                diff = ["wage", round(wa / wb, 2)]
            if diff:
                r["diff"] = diff
            n_diff[diff[0] if diff else None] += 1
            out.append(r)
        c["peer_reasons"] = out
    nation["nation"]["peer_rule"] = ("닮은 도시는 인구(로그)·고령 비율·1인당 GRDP(로그)·산업 16분류(부가가치 GVA 대비 비중)의 표준화 거리로 5곳을 고른다(build_econ.py). "
                                     "도시 아래 요약은 이 네 축 가운데 거리가 가장 작은 두 축(산업 구성이 들면 두 도시 모두 비중이 큰 업종과 두 비중)과, "
                                     + ("5년 인구 증감 5%p 이상 → 1인당 총급여 1.15배 이상 가운데 먼저 맞는 차이 하나를 적는다(공개판에는 아파트 매매가가 없어 그 차이는 보지 않는다). " if NO_HOUSING else
                                        "아파트 매매 ㎡당 가격 1.35배 이상(두 도시 모두 거래 10건 이상) → 5년 인구 증감 5%p 이상 → 1인당 총급여 1.15배 이상 가운데 먼저 맞는 차이 하나를 적는다. ")
                                     + 
                                     "맞는 차이가 없으면 차이를 적지 않는다.")
    log(f"닮은 도시 근거 {sum(len(c['peer_reasons']) for c in cities)}건, 차이 {n_diff}")


# =====================================================================
# 4. 추천 시점 (극값 규칙)
# =====================================================================
def build_presets(cities, nation, world):
    trade = load_json(site("trade.json"))
    G = Grid(world["grid"]["cols"], world["grid"]["rows"], world["grid"]["radius"])
    manf = lambda c: (c["gdp_by_industry"]["manufacturing"] / c["gdp_by_industry"]["grdp"]  # noqa: E731
                      if c.get("gdp_by_industry") and c["gdp_by_industry"].get("manufacturing") is not None and c["gdp_by_industry"].get("grdp") else None)
    paddy = lambda c: (c.get("farm") or {}).get("paddy_ha")  # noqa: E731
    have = lambda f: [c for c in cities if f(c) is not None]  # noqa: E731
    n_c = len(cities)
    items = []

    def city_item(pid, c, title, rule, metric, lens, ly=None):
        items.append({"id": pid, "kind": "auto", "title": title, "rule": rule, "metric": metric, "lens": lens, "ly": ly, "hide": [],
                      "city": c["id"], "route": None, "x": c["x"], "y": c["y"], "z": 2.6})
    c = max(cities, key=lambda c: c["population"])
    city_item("top_pop", c, f"인구 1위 · {c['name']}", f"도시 {n_c}곳 중 주민등록 인구가 가장 많은 곳", f"{round(c['population'] / 1e4):,}만명", "density")
    pool = [c for c in have(lambda c: c.get("gdp_per_capita")) if c["population"] >= 100000]
    c = max(pool, key=lambda c: c["gdp_per_capita"])
    city_item("top_gdppc", c, f"1인당 GRDP 1위 · {c['name']}", f"인구 10만 이상 도시 {len(pool)}곳 중 1인당 GRDP(시군구 합 {c['gdp_year']})가 가장 큰 곳",
              f"{c['gdp_per_capita'] / 1e8:.2f}억원", "gdp_pc")
    pool = have(manf)
    c = max(pool, key=manf)
    city_item("top_mfg", c, f"제조업 비중 1위 · {c['name']}", f"GRDP 가 있는 도시 {len(pool)}곳 중 GRDP 대비 제조업 부가가치 비중이 가장 큰 곳", f"{manf(c) * 100:.1f}%",
              "manufacturing_share")
    pool = have(lambda c: c.get("extinction_index"))
    c = min(pool, key=lambda c: c["extinction_index"])
    city_item("min_ext", c, f"소멸위험지수 최저 · {c['name']}", f"도시 {len(pool)}곳 중 소멸위험지수(20–39세 여성 ÷ 65세 이상)가 가장 낮은 곳", f"지수 {c['extinction_index']:.2f}",
              "extinction")
    pool = have(paddy)
    c = max(pool, key=paddy)
    city_item("top_paddy", c, f"논 면적 1위 · {c['name']}", f"논 면적이 있는 도시 {len(pool)}곳 중 농업면적조사 논 면적이 가장 큰 곳", f"{round(paddy(c)):,}ha",
              "paddy_share")
    R = trade["routes"]
    s = max(R["segments"], key=lambda g: g["total"])
    A, B = R["anchors"][s["a"]], R["anchors"][s["b"]]
    st = {x["code"]: x for x in load_json(site("states.json"))}
    items.append({"id": "top_route", "kind": "auto", "title": f"도로 화물 1위 구간 · {st[s['a']]['short']}–{st[s['b']]['short']}",
                  "rule": f"시도 간 도로 화물 O/D {R['pairs_total']}쌍 중 두 방향 합이 가장 큰 구간 ({R['year']})", "metric": f"{round(s['total'] / 1e4):,}만 톤",
                  "lens": None, "ly": ["wonders", "resources", "infra", "trade"], "hide": [], "city": None, "route": f"{s['a']}-{s['b']}",
                  "x": round((G.center(A["cell"])[0] + G.center(B["cell"])[0]) / 2, 1), "y": round((G.center(A["cell"])[1] + G.center(B["cell"])[1]) / 2, 1), "z": 1.6})
    nation["presets"] = {
        "rule": ("여섯 시점은 손으로 고르지 않고 빌드할 때마다 site/data 의 수치 극값 규칙으로 고른다(pipeline/build_insights.py). 도시 시점은 그 도시 깃발 자리를 전국 화면의 2.6배로, "
                 "구간 시점은 두 청사 칸의 가운데를 1.6배로 보여 준다. 편집자가 고른 시점을 더하려면 kind 를 'editorial'로 두고 '편집 선정'으로 표시해야 한다."),
        "items": items,
    }
    log("추천 시점: " + "; ".join(f"{x['id']} {x['title']} {x['metric']}" for x in items))


def main():
    world = load_json(site("world.json"))
    cities = load_json(site("cities.json"))
    nation = load_json(site("nation.json"))
    build_lq(cities, nation)
    build_benchmarks(cities, nation)
    build_peer_reasons(cities, nation)
    build_presets(cities, nation, world)
    a = save_json(site("cities.json"), cities)
    b = save_json(site("nation.json"), nation)
    log(f"cities.json {a:,} B, nation.json {b:,} B")


if __name__ == "__main__":
    sys.exit(main())

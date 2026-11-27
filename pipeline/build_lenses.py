"""렌즈: 인구 값을 칸에 내린다 -> site/data/lenses.json

읍면동(없으면 시군구) 인구를 그 단위의 표본점 가운데 육지 칸에 떨어진 점 수에 비례해 나눈다.
정수 인구는 최대 나머지 방식으로 나눠 전국 합이 원자료와 한 명도 어긋나지 않게 한다.
육지 칸에 표본점이 하나도 없는 작은 동은 대표점이 놓인 칸(그 칸이 육지가 아니면 같은 시군구의 가장 가까운 칸)에 전부 준다.
"""
import sys

import numpy as np

from lib import jumin, popstats
from lib import units as UN
from lib.common import build, load_json, rnd, save_json, site

GROUPS = [{"id": "people", "name": "사람"}, {"id": "age", "name": "나이"}, {"id": "future", "name": "지속"}]


def log(*a):
    print("[lenses]", *a, flush=True)


def pct_domain(vals, lo=2, hi=98, positive=False):
    v = np.array([x for x in vals if x is not None and (x > 0 or not positive)], float)
    if len(v) == 0:
        return None
    return [float(np.percentile(v, lo)), float(np.percentile(v, hi))]


def main():
    world = load_json(site("world.json"))
    npz = np.load(build("world_samples.npz"))
    samp, centers = npz["samp"], npz["centers"]
    owner = np.array(world["owner"])
    county = np.array(world["county"])
    land_frac = np.array([v or 0 for v in world["land_frac"]], float)
    N = len(owner)
    S = samp.shape[1]
    hex_km2 = world["hex_km2"]
    counties = world["counties"]
    dongs = load_json(build("dongs.json"))
    stats = load_json(build("sgg_stats.json"))
    vintage = stats["vintage"]
    ym, f_sgg, f_emd, _ = popstats.latest_files()
    land = owner >= 0
    sgg_index = {c["code"]: k for k, c in enumerate(counties)}

    # ---------- 단위(읍면동 또는 시군구)와 그 인구 ----------
    if f_emd:
        dong_rec, _ = popstats.dong_population(f_emd, dongs)
        unit_recs = [dong_rec[d["code"]] for d in dongs]
        unit_of_samp = samp                       # 표본점 -> 동 번호
        unit_sgg = [d["sgg"] for d in dongs]
        unit_rp = [(d["rx"], d["ry"]) for d in dongs]
        level = "읍면동"
    else:
        _, recs = jumin.read(f_sgg)
        leaf, _ = jumin.leaf_sgg(recs)
        byc = {r["code"][:5]: r for r in leaf}
        unit_recs = [byc[c["code"]] for c in counties]
        dsgg = np.array([sgg_index[d["sgg"]] for d in dongs])
        unit_of_samp = np.where(samp >= 0, dsgg[np.clip(samp, 0, None)], -1)
        unit_sgg = [c["code"] for c in counties]
        unit_rp = []
        for c in counties:
            cells = np.nonzero(county == sgg_index[c["code"]])[0]
            unit_rp.append(tuple(centers[cells].mean(0)))
        level = "시군구"
    U = len(unit_recs)
    log(f"단위: {level} {U}개")

    # 단위 × 칸 표본점 수 (육지 칸만)
    cells_idx = np.repeat(np.arange(N), S)
    us = unit_of_samp.ravel()
    ok = (us >= 0) & land[cells_idx]
    pairs = us[ok].astype(np.int64) * N + cells_idx[ok]
    uniq, cnt = np.unique(pairs, return_counts=True)
    pu, pc = uniq // N, uniq % N
    shares = {}  # 단위 -> [(칸, 점 수)]
    for u, c, k in zip(pu.tolist(), pc.tolist(), cnt.tolist()):
        shares.setdefault(u, []).append((c, k))
    no_samples = 0
    for u in range(U):
        if u in shares:
            continue
        no_samples += 1
        x, y = unit_rp[u]
        own = np.nonzero(county == sgg_index[unit_sgg[u]])[0]
        cand = own if len(own) else np.nonzero(land)[0]
        d2 = ((centers[cand] - [x, y]) ** 2).sum(1)
        shares[u] = [(int(cand[int(np.argmin(d2))]), 1)]
    log(f"육지 칸에 표본점이 없어 한 칸에 몰아준 {level}: {no_samples}개")

    # ---------- 나누기 ----------
    cell_pop = np.zeros(N, np.int64)
    ages = np.zeros((N, 21))
    male = np.zeros((N, 21))
    female = np.zeros((N, 21))
    for u, lst in shares.items():
        r = unit_recs[u]
        tot = r["total"]
        k = np.array([n for _, n in lst], float)
        cs = np.array([c for c, _ in lst])
        w = k / k.sum()
        exact = tot * w
        base = np.floor(exact).astype(np.int64)
        rem = tot - base.sum()
        if rem:
            order = np.lexsort((cs, -(exact - base)))  # 나머지가 큰 칸부터, 같으면 칸 번호 순
            base[order[:rem]] += 1
        cell_pop[cs] += base
        ages[cs] += np.outer(w, r["ages"])
        male[cs] += np.outer(w, r["male"])
        female[cs] += np.outer(w, r["female"])
    total = int(cell_pop.sum())
    want = sum(r["total"] for r in unit_recs)
    log(f"칸에 나눈 인구 합 {total:,} (원자료 {want:,}, 차이 {total - want})")
    if total != want:
        raise ValueError("칸 인구 합이 원자료와 다름")

    # ---------- 값 ----------
    def cell_ind(i):
        if not land[i] or cell_pop[i] == 0:
            return None
        return popstats.indicators({"total": float(ages[i].sum()), "ages": ages[i].tolist(),
                                    "male": male[i].tolist(), "female": female[i].tolist()})

    inds = [cell_ind(i) for i in range(N)]
    lf = np.maximum(land_frac, 1.0 / S)
    density = [rnd(cell_pop[i] / (hex_km2 * lf[i]), 0) if land[i] else None for i in range(N)]
    # 인구 증감은 시군구 값이라 5e 부터 칸에 펼치지 않고 시군구 값(by_county, world.counties 순서)만 싣는다.
    # 화면(render/lens.js ensureValues)이 육지 칸에 같은 값을 펼친다 — 칸마다 펼친 예전 저장과 값이 같다.
    growth_c = [rnd(stats["sgg"][c["code"]]["growth_latest"], 2) for c in counties]
    growth = [growth_c[county[i]] if land[i] else None for i in range(N)]  # 색 범위(백분위) 계산용 칸 배열

    def from_ind(key, nd):
        return [rnd(x[key], nd) if x and x[key] is not None else None for x in inds]

    over65 = from_ind("over65", 1)
    under15 = from_ind("under15", 1)
    age = from_ind("mean_est", 1)
    ext = from_ind("extinction_index", 3)
    sexr = from_ind("sex_ratio_20_39", 1)

    src = f"행정안전부 주민등록 인구통계 ({vintage})"
    src_g = f"행정안전부 주민등록 인구통계 (2020-12, {vintage})"
    lvl_note = f"{level} 값을 칸에 표본점 비율로 내렸다."
    dd = pct_domain(density, positive=True)
    gd = pct_domain(growth)
    gm = max(abs(gd[0]), abs(gd[1]))
    sd = pct_domain(sexr)  # 청년 성비는 남초 쪽으로 크게 치우쳐 있어 중심 100 양쪽을 따로 잡는다
    lenses = [
        {"id": "density", "group": "people", "name": "인구밀도", "emoji": "👥", "unit": "명/km²", "format": "int",
         "scale": "log", "ramp": ["#fbf3d5", "#f8d58c", "#f3a55a", "#e2683a", "#b8384a", "#7a1f5c", "#3a1149"],
         "higher_is": "neutral", "source": src,
         "description": f"칸 인구 ÷ (칸 넓이 {hex_km2} km² × 대한민국 땅 비율). {lvl_note}",
         "domain": [rnd(dd[0], 1), rnd(dd[1], 0)], "values": density},
        {"id": "growth", "group": "people", "name": "인구 증감", "emoji": "📈", "unit": "%", "format": "pct1",
         "scale": "diverging", "center": 0,
         "ramp": ["#a3242f", "#d9714f", "#f2c39c", "#f4efe6", "#b9dbe3", "#5b9fc2", "#215a91"],
         "higher_is": "neutral", "source": src_g,
         "description": f"2020-12 대비 {vintage} 주민등록 인구 변화율. 시군구 단위(일반구 신설·인천 개편으로 나뉜 구는 나뉘기 전 단위로 묶음).",
         "domain": [rnd(-gm, 2), rnd(gm, 2)], "by_county": growth_c},
        {"id": "over65", "group": "age", "name": "고령 인구", "emoji": "🧓", "unit": "%", "format": "pct1",
         "scale": "linear", "ramp": ["#f5f1e6", "#e2d3e6", "#c5a8d3", "#a07cbc", "#7a51a0", "#4f2a7c"],
         "higher_is": "neutral", "source": src, "description": f"65세 이상 인구 비율. {lvl_note}",
         "domain": [rnd(x, 1) for x in pct_domain(over65)], "values": over65},
        {"id": "under15", "group": "age", "name": "유소년 인구", "emoji": "🧒", "unit": "%", "format": "pct1",
         "scale": "linear", "ramp": ["#f4f3e2", "#d8ebc0", "#a6d393", "#66b16d", "#318a50", "#135d39"],
         "higher_is": "neutral", "source": src, "description": f"0–14세 인구 비율. {lvl_note}",
         "domain": [rnd(x, 1) for x in pct_domain(under15)], "values": under15},
        {"id": "age", "group": "age", "name": "평균연령(추정)", "emoji": "🎂", "unit": "세", "format": "f1",
         "scale": "linear", "ramp": ["#f1f5f8", "#c8dcea", "#93badb", "#5d92c3", "#3567a3", "#1b3d72"],
         "higher_is": "neutral", "source": src,
         "description": f"5세 계급 중간값(100세 이상은 102.5세)으로 낸 평균연령 추정치. 공식 평균연령과 다를 수 있다. {lvl_note}",
         "domain": [rnd(x, 1) for x in pct_domain(age)], "values": age},
        {"id": "extinction", "group": "future", "name": "소멸위험지수", "emoji": "⏳", "unit": "지수", "format": "f2",
         "scale": "bins", "breaks": [0.2, 0.5, 1.0, 1.5],
         "bin_labels": ["0.2 미만 소멸 고위험", "0.2–0.5 소멸위험", "0.5–1.0 주의", "1.0–1.5 보통", "1.5 이상 매우 낮음"],
         "ramp": ["#8e1b2e", "#d4553a", "#efb25c", "#a6cf8d", "#3f8f6b"],
         "higher_is": "good", "source": src,
         "description": f"20–39세 여성 인구 ÷ 65세 이상 인구. 0.5 미만이면 소멸위험, 0.2 미만이면 고위험으로 본다. {lvl_note}",
         "domain": [0, 1.5], "values": ext},
        {"id": "sex_ratio", "group": "future", "name": "청년 성비", "emoji": "⚖️", "unit": "명", "format": "f1",
         "scale": "diverging", "center": 100,
         "ramp": ["#a8346a", "#dc8bb0", "#f4dce7", "#f3f1ee", "#d3e2f1", "#7aa5d3", "#2b5ea4"],
         "higher_is": "neutral", "source": src,
         "description": f"20–39세 여성 100명당 남성 수. 100보다 크면 남성이 많다. {lvl_note}",
         "domain": [rnd(min(sd[0], 99.0), 1), rnd(max(sd[1], 101.0), 1)], "values": sexr},
    ]
    # 감사 01: 인구 증감은 나뉜 구를 나뉘기 전 단위로 묶어 계산한다 — 묶음과 그 이름을 렌즈에 적는다
    gl = next(l_ for l_ in lenses if l_["id"] == "growth")
    grp = {frozenset(stats["sgg"][c["code"]]["series_unit"]) for c in counties if stats["sgg"][c["code"]].get("growth_latest") is not None}
    UN.annotate(gl, [(k, "2020") for k in grp], UN.Namer(world, load_json(site("cities.json"))),
               suffix=f" (2020-12 → {vintage}, 같은 구역으로 묶어 비교)")
    out = {"vintage": vintage, "level": level, "groups": GROUPS, "lenses": lenses,
           "cell_pop": [int(v) if land[i] else None for i, v in enumerate(cell_pop)],
           "notes": [
               "색 범위는 육지 칸 값의 2–98 백분위다 (인구 증감은 0에서 대칭, 청년 성비는 100 양쪽을 따로, 소멸위험지수는 고정 구간).",
               "인구가 0인 칸은 비율을 계산하지 않고 '자료 없음'으로 둔다.",
               f"{level} 인구는 그 {level}의 표본점 가운데 육지 칸에 떨어진 점 수에 비례해 칸에 나눴다. "
               f"육지 칸에 표본점이 없는 {level} {no_samples}개는 대표점에 가장 가까운 자기 시군구 칸에 몰아줬다.",
           ]}
    size = save_json(site("lenses.json"), out)
    log(f"lenses.json {size / 1e6:.2f} MB")


if __name__ == "__main__":
    sys.exit(main())

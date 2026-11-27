"""검증 (명세 §8). 하나라도 어긋나면 0이 아닌 코드로 끝난다.  실행: python pipeline/validate.py"""
import glob
import math
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pyproj import Transformer  # noqa: E402

from lib import jumin, popstats  # noqa: E402
from lib import profile as PRF  # noqa: E402
from lib.common import SITE_DATA, build, load_json, site  # noqa: F401  # noqa: E402
from lib.hexgrid import Grid  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUTH_KOREA_KM2 = 100400
# 육지 칸으로 있어야 하는 섬: (이름, 경도, 위도, 시군구 코드). 위치 확인용 좌표다.
ISLANDS = [("독도", 131.8648, 37.2410, ["47940"]), ("울릉도", 130.9050, 37.4850, ["47940"]),
           ("백령도", 124.6650, 37.9580, ["28720"]), ("마라도", 126.2670, 33.1170, ["50130"]),
           ("가파도", 126.2720, 33.1680, ["50130"]), ("제주도", 126.5292, 33.3617, ["50110", "50130"])]

results = []
notes_out = []  # 판정 없는 출력 (감사 13: 검증 통과 수에 섞지 않는다)
skipped = []    # 이 판에서는 뜻이 없는 검사 (까닭을 찍고 건너뛴다 — 말없이 빼지 않는다)


def data_profile():
    """site/data 가 어느 판으로 빌드됐는지 (sources.json profile, 없으면 옛 빌드 = full)."""
    try:
        return ((load_json(site("sources.json")).get("profile") or {}).get("profile")) or "full"
    except (OSError, ValueError):
        return "full"


PROFILE = data_profile()
PUBLIC = PROFILE == "public"


def skip(name, reason):
    skipped.append((name, reason))
    print(f"[건너뜀] {name} — {reason}", flush=True)


def note(name, detail=""):
    notes_out.append((name, detail))
    print(f"[출력] {name}" + (f" — {detail}" if detail else ""), flush=True)


def lens_values(lz, world):
    """렌즈 칸 값 배열 (values, 또는 육지 칸 값만 실은 land_values 를 칸 배열로 펼침, 또는 시군구 값). 없으면 None."""
    if "values" in lz:
        return lz["values"]
    if "land_values" in lz:
        out = [None] * len(world["owner"])
        for i, v in zip(world["cover_share"]["land_cells"], lz["land_values"]):
            out[i] = v
        return out
    if "by_county" in lz:
        return [lz["by_county"][world["county"][i]] if world["owner"][i] >= 0 else None for i in range(len(world["owner"]))]
    return None


def decode_share(world, key):
    """world.cover_share[key] (land_cells 순서의 정수 %) -> 칸 번호 -> 값."""
    cs = world["cover_share"]
    return dict(zip(cs["land_cells"], cs[key]))


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"[{'통과' if ok else '실패'}] {name}" + (f" — {detail}" if detail else ""), flush=True)


def main():
    env = os.environ.get(PRF.ENV)
    print(f"검증하는 site/data 의 판: {PROFILE}" + (f" (빌드 명령의 판 {env})" if env else ""), flush=True)
    if env and env != PROFILE:
        check("판: 빌드 명령의 판 = site/data 의 판", False, f"{env} != {PROFILE}")
    world = load_json(site("world.json"))
    cities = load_json(site("cities.json"))
    states = load_json(site("states.json"))
    nation = load_json(site("nation.json"))
    lenses = load_json(site("lenses.json"))
    lenses_site = lenses
    if lenses.get("phase") == "6":
        # 6단계: 렌즈 막대에서 뺀 렌즈 12개는 사이트에 시군구 값만 남는다. 앞 단계 검사(칸 값 범위·덮은 비율 등)는
        # 사이트에 남은 렌즈는 사이트 값으로, 뺀 렌즈는 빌드 사본(data/build/lenses_pre6.json, 5e 결과)의 값으로 그대로 돌린다.
        snap = load_json(build("lenses_pre6.json"))
        gone = [l_ for l_ in snap["lenses"] if l_["id"] in lenses["retired"]]
        lenses = {**lenses, "lenses": lenses["lenses"] + gone}
    wlog = load_json(build("world_log.json"))
    cols, rows = world["grid"]["cols"], world["grid"]["rows"]
    N = cols * rows
    G = Grid(cols, rows, world["grid"]["radius"])

    # 1. 시군구 합 = 시도 합 = 전국 = 원자료 전국 행
    ym, f_sgg, _, f_nat = popstats.latest_files()
    _, recs = jumin.read(f_sgg)
    leaf, _ = jumin.leaf_sgg(recs)
    s_sgg = sum(r["total"] for r in leaf)
    _, nrecs = jumin.read(f_nat)
    nat_row = next(r["total"] for r in nrecs if jumin.is_nation(r["code"]))
    s_sido_raw = sum(r["total"] for r in nrecs if jumin.is_sido(r["code"]))
    s_states = sum(s["population"] for s in states)
    per_sido = all(s["population"] == sum(r["total"] for r in leaf if r["code"][:2] == s["code"]) for s in states)
    check("1. 시군구 합 = 시도 합 = 전국 = 원자료 전국 행",
          s_sgg == s_sido_raw == s_states == nation["nation"]["population"] == nat_row and per_sido,
          f"시군구 {s_sgg:,} / 시도(원자료) {s_sido_raw:,} / 시도(states.json) {s_states:,} / "
          f"전국(nation.json) {nation['nation']['population']:,} / 원자료 전국 행 {nat_row:,}")

    # 2. 칸 인구 합 = 전국
    cp = sum(v for v in lenses["cell_pop"] if v)
    check("2. 칸에 나눈 인구 합 = 전국 (오차 0)", cp == nat_row, f"{cp:,} - {nat_row:,} = {cp - nat_row}")

    # 3. 도시 인구 합 = 전국, 시군구는 정확히 한 도시
    s_city = sum(c["population"] for c in cities)
    seen = {}
    for c in cities:
        for s in c["sgg"]:
            seen[s] = seen.get(s, 0) + 1
    codes = {c["code"] for c in world["counties"]}
    once = set(seen) == codes and all(v == 1 for v in seen.values())
    check("3. 도시 인구 합 = 전국, 모든 시군구가 정확히 한 도시", s_city == nat_row and once,
          f"도시 {len(cities)}곳 합 {s_city:,}, 시군구 {len(seen)}/{len(codes)}, 중복 {sum(1 for v in seen.values() if v > 1)}")

    # 4. 모든 시군구가 칸을 하나 이상
    cnt = [0] * len(world["counties"])
    for k in world["county"]:
        if k >= 0:
            cnt[k] += 1
    missing = [world["counties"][j]["name"] for j, n in enumerate(cnt) if n == 0]
    before = wlog.get("missing_before", [])
    nm = {c["code"]: c["name"] for c in world["counties"]}
    check("4. 모든 시군구가 칸을 하나 이상 가짐 (보정 후)", not missing,
          f"보정 전 칸이 없던 시군구 {len(before)}개: {', '.join(nm[c] for c in before) or '없음'}; "
          f"보정 {len(wlog.get('fixes', []))}건 적용 후 칸이 없는 시군구 {len(missing)}개 {missing}")

    # 5. 육지 넓이
    nl = sum(1 for o in world["owner"] if o >= 0)
    km2 = nl * world["hex_km2"]
    dev = 100 * (km2 / SOUTH_KOREA_KM2 - 1)
    check("5. 육지 칸 넓이가 남한 넓이의 ±3% 안", abs(dev) <= 3,
          f"육지 {nl}칸 × {world['hex_km2']} km² = {km2:,.0f} km² ({dev:+.2f}%)")

    # 6. 섬
    tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    ox, oy = world["origin_5179"]
    mpu = world["meters_per_unit"]
    found, miss = [], []
    for name, lon, lat, sgg in ISLANDS:
        e, n = tf.transform(lon, lat)
        c = G.point_to_cell((e - ox) / mpu, (oy - n) / mpu)
        near = [c] + G.neighbors(c)
        hit = [k for k in near if world["owner"][k] >= 0 and world["counties"][world["county"][k]]["code"] in sgg]
        (found if hit else miss).append(f"{name}(칸 {hit[0] if hit else c})")
    marado_ok = any(s.startswith("마라도") or s.startswith("가파도") for s in found)
    core_ok = all(any(s.startswith(x) for s in found) for x in ("독도", "울릉도", "백령도", "제주도"))
    check("6. 독도·울릉도·백령도·마라도(또는 가파도)·제주가 육지 칸", core_ok and marado_ok,
          f"있음: {', '.join(found)}" + (f" / 없음: {', '.join(miss)}" if miss else ""))

    # 7. 배열 길이
    bad = []
    for k in ("owner", "county", "land_frac", "foreign", "elev", "elev_sd", "water", "relief", "cover"):
        if len(world[k]) != N:
            bad.append(f"world.{k}={len(world[k])}")
    for it in (lenses_site.get("retired_values") or {}).get("items", []):
        if len(it["values"]) != len(world["counties"]):
            bad.append(f"retired.{it['id']}={len(it['values'])}")
    for lz in lenses_site["lenses"]:
        if "values" in lz and len(lz["values"]) != N:
            bad.append(f"lens.{lz['id']}={len(lz['values'])}")
        if "by_county" in lz and len(lz["by_county"]) != len(world["counties"]):
            bad.append(f"lens.{lz['id']}.by_county={len(lz['by_county'])}")
        if "land_values" in lz:
            lc_ = world["cover_share"]["land_cells"]
            if len(lz["land_values"]) != len(lc_) or lc_ != [i for i in range(N) if world["owner"][i] >= 0]:
                bad.append(f"lens.{lz['id']}.land_values={len(lz['land_values'])} (육지 칸 {len(lc_)})")
    if len(lenses_site["cell_pop"]) != N:
        bad.append("cell_pop")
    check("7. JSON 배열 길이가 모두 cols × rows", not bad, f"{cols}×{rows}={N}" + (f", 어긋남 {bad}" if bad else ""))

    # 덧붙인 검사: 파일 크기, 도시 칸
    ws = os.path.getsize(site("world.json")) / 1e6
    tot = sum(os.path.getsize(p) for p in glob.glob(os.path.join(SITE_DATA, "*.json"))) / 1e6
    check("+ 파일 크기 (world.json ≤ 1.5 MB, 전체 ≤ 5 MB — 5b 2부 뒤에도 그대로 둠)", ws <= 1.5 and tot <= 5, f"world {ws:.2f} MB, 전체 {tot:.2f} MB")
    bad_city = [c["name"] for c in cities if not c["footprint"] or c["cell"] not in c["footprint"]]
    check("+ 모든 도시가 영토를 갖고 깃발 칸이 자기 영토 안", not bad_city, ", ".join(bad_city))
    rel = world["tables"]["relief"]
    check("+ 기복 기준값이 world.tables.relief 에 문장으로 있음", any(r.get("id") == "note" for r in rel))

    if any("gdp" in c for c in cities):
        print("\n--- 3단계: 경제 산출과 렌즈 ---")
        validate_econ(world, cities, lenses)

    if os.path.exists(site("wonders.json")):
        print("\n--- 5a단계: 지도 층 ---")
        validate_layers(world, cities, lenses)

    if "cover_share" in world:
        print("\n--- 5b단계 1부: 지형과 공식값 ---")
        validate_5b_terrain(world, states, nation)

    if os.path.exists(site("frontier.json")):
        print("\n--- 5b단계 2부: 층과 렌즈 ---")
        validate_5b_layers(world, lenses)

    if "cover_src" in world:
        print("\n--- 5c단계: 공식 토지피복 ---")
        validate_5c(world, cities, states, nation, lenses)

    if os.path.exists(site("trade.json")):
        print("\n--- 5d단계: 수출입·교역로·남은 위치 자료 ---")
        validate_5d(world, cities, states, nation, lenses)

    if any(l_["id"] == "veterans" for l_ in lenses["lenses"]):
        print("\n--- 5e단계: 돼지 시군 값·보훈대상자 ---")
        validate_5e(world, cities, states, lenses)

    if lenses_site.get("phase") == "6":
        print("\n--- 6단계: 정리·보고서·이용허락 ---")
        validate_6(world, cities, states, nation, lenses_site)

    if "benchmarks" in nation["nation"]:
        print("\n--- 7b단계: 공용 계산 (입지계수·특성 표시·전국 기준값·닮은 도시 근거·추천 시점·배치 규칙) ---")
        validate_7b(world, cities, states, nation, lenses_site)

    if "credits" in load_json(site("sources.json")):
        print("\n--- 출처 쪽·NOTICE.md ---")
        validate_sources_page()

    print(f"\n--- 빌드 판 (profile {PROFILE}) ---")
    validate_profile(world, cities, states, nation, lenses_site)

    failed =[r for r in results if not r[1]]
    print(f"\n검증 {len(results)}개 중 통과 {len(results) - len(failed)}개, 실패 {len(failed)}개 (판정 없는 출력 {len(notes_out)}개는 세지 않음"
          + (f", 이 판({PROFILE})에서 뜻이 없어 건너뛴 검사 {len(skipped)}개: {', '.join(n.split(' ')[0] for n, _ in skipped)}" if skipped else "") + f") — 판 {PROFILE}")
    return 1 if failed else 0


def validate_econ(world, cities, lenses):
    from lib import econ as E

    ec = E.Econ(world, cities)
    rows = [r for r in ec.table("grdp") if r["indicator"] == "grdp_current"]
    byk = {}
    for r in rows:
        byk.setdefault((r["year"], E.grdp_key(r["industry"])), []).append(r)
    umaps = {k: ec.unit_map(v, True) for k, v in byk.items()}

    # E1. 산업 합 + 순생산물세 = GRDP (0.5%)
    bad, skipped, n = [], 0, 0
    for c in cities:
        b = c.get("gdp_by_industry")
        if not b:
            continue
        if c["gdp_undisclosed"]:
            skipped += 1
            continue
        n += 1
        tot = sum(b[k] for k in E.INDUSTRY_KEYS) + b["net_taxes"]
        if abs(tot / b["grdp"] - 1) > 0.005:
            bad.append(f"{c['name']} {100 * (tot / b['grdp'] - 1):+.2f}%")
    check("E1. 도시 산업 합 + 순생산물세 = GRDP (±0.5%)", not bad,
          f"검사 {n}곳, 비공개가 있어 제외 {skipped}곳" + (f", 어긋남: {bad}" if bad else ""))

    # E2. 도시 GRDP 합 = 시군구(공표 단위) GRDP 합, 같은 연도 규칙
    sc = su = 0
    for c in cities:
        if c.get("gdp") is None:
            continue
        um = umaps[(str(c["gdp_year"]), "grdp")]
        su += sum(v for k, v in um.items() if k <= frozenset(c["sgg"])) * 1e6
        sc += c["gdp"]
    check("E2. 도시 GRDP 합 = 시군구 GRDP 합 (같은 연도 규칙)", abs(sc - su) < 1,
          f"도시 {sc / 1e12:,.3f}조 / 시군구 {su / 1e12:,.3f}조 원")

    # E3. 덮은 도시 수
    ng = sum(1 for c in cities if c.get("gdp") is not None)
    ny = sum(1 for c in cities if c.get("yields") and all(v is not None for v in c["yields"].values()))
    npart = sum(1 for c in cities if (c.get("yields_partial") or {}).get("production"))
    check("E3. GRDP 가 있는 도시 160곳 이상", ng >= 160,
          f"GRDP 있음 {ng}/{len(cities)}, 다섯 산출 모두 있음 {ny}/{len(cities)} (그중 생산이 부분 합계(광업 비공개 제외)인 도시 {npart})")

    # E4·E5. 렌즈 덮음, 범위
    land = [o >= 0 for o in world["owner"]]
    nl = sum(land)
    cover, low, rng = [], [], []
    # 감사 13: by_county 렌즈만이 아니라 칸 값(values)·육지 칸 값(land_values) 렌즈도 같은 기준으로 센다. 저장 길이가 틀리거나
    # 육지 밖 칸에 값이 있으면 미달로 본다. 렌즈에 적힌 coverage 가 있으면 다시 센 값과 같아야 한다.
    K_ = len(world["counties"])
    for lz in lenses["lenses"]:
        kind = "by_county" if "by_county" in lz else "land_values" if "land_values" in lz else "values" if "values" in lz else None
        want_len = {"by_county": K_, "land_values": len(world["cover_share"]["land_cells"]), "values": len(land)}.get(kind)
        if kind is None or len(lz[kind]) != want_len:
            low.append(f"{lz['id']} 저장 {kind} 길이 {len(lz[kind]) if kind else '-'} ≠ {want_len}")
            continue
        cvals = lens_values(lz, world)
        off = sum(1 for i in range(len(land)) if not land[i] and cvals[i] is not None)
        cv = sum(1 for i in range(len(land)) if land[i] and cvals[i] is not None) / nl
        cover.append(f"{lz['id']} {100 * cv:.1f}%")
        if cv < 0.5 or off:
            low.append(lz["id"] + (f" 육지 밖 값 {off}" if off else ""))
        cvf = lz.get("coverage")
        if isinstance(cvf, (int, float)) and abs(cvf - cv) > 0.0006:
            low.append(f"{lz['id']} coverage {cvf} ≠ 다시 센 {cv:.4f}")
        vs = [v for v in (lz["by_county"] if kind == "by_county" else cvals) if v is not None]
        # 증감률(diverging, 예: 인구 증감 — 5e 부터 by_county 로 저장)은 비율(0–100%)이 아니라 뺀다
        if lz["unit"] == "%" and lz.get("scale") != "diverging" and vs and (min(vs) < 0 or max(vs) > 100):
            rng.append(f"{lz['id']} [{min(vs)}, {max(vs)}]")
        if lz["id"] in ("gdp_pc", "wage", "home", "jeonse", "doctors", "fertility") and vs and min(vs) < 0:
            rng.append(f"{lz['id']} 음수 {min(vs)}")
    check("E4. 렌즈마다(시군구·칸·육지 칸 값 모두) 저장 길이가 맞고 값이 있는 육지 칸 50% 이상, 육지 밖 값 없음", not low, ", ".join(cover) + (f" / 미달 {low}" if low else ""))
    for c in cities:
        if c.get("gdp_per_capita") is not None and c["gdp_per_capita"] < 0:
            rng.append(f"{c['name']} gdp_per_capita")
        if c.get("wage") and c["wage"]["per_filer"] is not None and c["wage"]["per_filer"] < 0:
            rng.append(f"{c['name']} wage")
    check("E5. 비율 렌즈 0–100%, 1인당 값 음수 없음", not rng, ", ".join(rng) or "모두 범위 안")

    # E6. 빈 값이 0 으로 바뀌지 않았는가
    raw_empty, null_hit, zero_bad = 0, 0, []
    for c in cities:
        b = c.get("gdp_by_industry")
        if not b:
            continue
        y, T = str(c["gdp_year"]), frozenset(c["sgg"])
        for k in E.INDUSTRY_KEYS + ["net_taxes"]:
            um = umaps.get((y, k), {})
            if any(kk <= T and v is None for kk, v in um.items()):
                raw_empty += 1
                if b[k] is None:
                    null_hit += 1
                else:
                    zero_bad.append(f"{c['name']}.{k}")
    # 생산 예외를 따로 센다: 광업이 빈 도시의 생산은 null 이거나, 광업을 뺀 제조업 + 건설업 합(+ 공개된 단위의 광업)이고
    # yields_partial.production == ["mining"] 이어야 한다. 빈 광업을 0 이 아닌 값으로 메운 흔적이 있으면 실패.
    exc_ok, exc_bad, prod_null = 0, [], 0
    for c in cities:
        b = c.get("gdp_by_industry")
        if not b or b.get("mining") is not None:
            continue
        p_ = (c.get("yields") or {}).get("production")
        part = (c.get("yields_partial") or {}).get("production")
        if p_ is None:
            prod_null += 1
            continue
        y, T = str(c["gdp_year"]), frozenset(c["sgg"])
        units = [k for k in umaps[(y, "grdp")] if k <= T]
        exp, n_ex = 0.0, 0
        for k in units:
            mi = umaps.get((y, "mining"), {}).get(k)
            exp += umaps[(y, "manufacturing")][k] + umaps[(y, "construction")][k] + (mi or 0)
            n_ex += mi is None
        if part == ["mining"] and n_ex == c.get("production_mining_excluded") and abs(exp * 1e6 - p_) < 1:
            exc_ok += 1
        else:
            exc_bad.append(c["name"])
    # E7. 산업 대분류 종사자: 대분류 합 = 합계 (비공개 없는 도시, ±0.5%), 덮은 도시 수, 전국 합
    from collections import Counter
    jc = [c for c in cities if c.get("jobs")]
    full = [c for c in jc if all(v is not None for v in c["jobs"].values()) and c.get("jobs_total")]
    jbad = [f"{c['name']} {100 * (sum(c['jobs'].values()) / c['jobs_total'] - 1):+.2f}%" for c in full
            if abs(sum(c["jobs"].values()) / c["jobs_total"] - 1) > 0.005]
    nj = (nation_ := load_json(site("nation.json"))["nation"]).get("jobs")
    nsum = sum(c["jobs_total"] for c in jc if c.get("jobs_total") is not None)
    nat_ok = nj is None or nation_.get("jobs_total") in (None, nsum)
    nletters = sum(v for v in nj.values() if v is not None) if nj else None
    nnull = [k for k, v in (nj or {}).items() if v is None]
    # 종사자 정리표의 빈 칸이 0 으로 들어가지 않았는가 (도시가 고른 출처·연도·단위에서)
    braw = [r for r in ec.table("business") if r["indicator"] == "establishment_workers"]
    hit = bad0 = 0
    for c in jc:
        T = frozenset(c["sgg"])
        for r in braw:
            if r["raw_empty"] and r["source"] == c["jobs_source"] and r["year"] == str(c["jobs_year"]) and r["codes"] <= T:
                L = E.ksic_letter(r["industry"])
                if L == "total":
                    continue
                hit += 1
                if c["jobs"][L] is not None:
                    bad0 += 1
    check("E7. 산업 대분류 종사자: 대분류 합 = 합계 (±0.5%), 빈 칸은 null", not jbad and nat_ok and bad0 == 0,
          f"대분류가 붙은 도시 {len(jc)}/{len(cities)} (연도 {dict(Counter(c['jobs_year'] for c in jc))}), 비공개 없이 검사 {len(full)}곳"
          + (f", 어긋남 {jbad}" if jbad else "")
          + f". 전국: 도시 합계 행 합 {nsum:,}명 = nation.jobs_total {nation_.get('jobs_total')}, "
          f"대분류 합 {nletters:,}명" + (f" (비공개가 섞인 대분류 {nnull} 는 null)" if nnull else "")
          + f". 고른 출처의 빈 칸 {hit}개 → 도시 대분류 null 유지, 0 으로 들어간 곳 {bad0}")

    raw_cells = sum(1 for r in rows if r["raw_empty"])
    check("E6. 정리표 빈 값이 0 으로 들어간 곳 없음", not zero_bad and raw_empty == null_hit and not exc_bad,
          f"GRDP 정리표 빈 칸 {raw_cells}개(전 연도). 도시 선택 연도에서 빈 칸에 걸린 (도시, 산업) {raw_empty}건 = 산업별 값 null {null_hit}건. "
          f"예외(광업 비공개): 생산을 광업 몫 없이 부분 합계로 낸 도시 {exc_ok}곳(표식 확인), 생산 null {prod_null}곳"
          + (f", 0 으로 들어감: {zero_bad}" if zero_bad else "") + (f", 예외 규칙 어긋남: {exc_bad}" if exc_bad else ""))


def validate_layers(world, cities, lenses):
    import csv
    import io
    import zipfile
    from collections import Counter

    import shapefile

    from lib import housing as HS
    from lib.common import raw

    G = Grid(world["grid"]["cols"], world["grid"]["rows"], world["grid"]["radius"])
    owner, county = world["owner"], world["county"]
    code = [world["counties"][k]["code"] if k >= 0 else None for k in county]
    L = {n: load_json(site(f"{n}.json")) for n in ("wonders", "resources", "infrastructure")}
    parks = {p["id"]: p for p in L["wonders"]["parks"]}

    def rawcsv(rel):
        b = open(raw(*rel.split("/")), "rb").read()
        for enc in ("utf-8-sig", "cp949"):
            try:
                t = b.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        rows = list(csv.reader(io.StringIO(t)))
        return [h.strip() for h in rows[0]], [r for r in rows[1:] if any(c.strip() for c in r)]

    # L1. 모든 항목이 육지 칸에, 칸의 시군구 = 항목의 소재 시군구 (point 는 이웃 칸까지)
    bad, n_items, prec = [], 0, Counter()
    for nm, obj in L.items():
        for it in obj["items"]:
            n_items += 1
            c = it["cell"]
            prec[(nm, it["precision"])] += 1
            if not (0 <= c < G.n) or owner[c] < 0:
                bad.append(f"{it['name']}: 육지 칸 아님")
                continue
            sg = set(it["sgg"])
            if it["precision"] == "point":
                near = {code[k] for k in [c] + G.neighbors(c) if owner[k] >= 0}
                if not (near & sg):
                    bad.append(f"{it['name']}: 칸 {code[c]} ∉ {sorted(sg)} (이웃 포함)")
            elif code[c] not in sg:
                bad.append(f"{it['name']}: 칸 {code[c]} ∉ {sorted(sg)}")
            if it["kind"] == "national_park":
                p = parks[it["ref"]]
                if c not in p["cells"] or any(owner[k] < 0 for k in p["cells"]):
                    bad.append(f"{it['name']}: 아이콘 칸이 공원 칸 밖이거나 공원 칸에 바다가 있음")
    check("L1. 층 항목이 모두 육지 칸, 칸의 시군구 = 소재 시군구 (point 는 한 칸 거리 안)", not bad,
          f"항목 {n_items}개" + (f", 어긋남 {len(bad)}: {bad[:8]}" if bad else ""))

    # L2. 국립공원 수 = 경계 파일의 공원 수, 넓이 합
    z = zipfile.ZipFile(raw("datagokr", "wonders", "15017313_국립공원공단_국립공원_공원경계.zip"))
    shp = [i for i in z.namelist() if i.lower().endswith(".shp")][0]
    r = shapefile.Reader(shp=io.BytesIO(z.read(shp)), dbf=io.BytesIO(z.read(shp[:-4] + ".dbf")), shx=io.BytesIO(z.read(shp[:-4] + ".shx")))
    n_raw = len(r)
    np_ = len(L["wonders"]["parks"])
    # 5d 부터 area_km2 는 공식 지정면적이고 경계 폴리곤 넓이는 boundary_km2 (덮는 칸 계산용)
    bkm = lambda p: p.get("boundary_km2", p["area_km2"])
    area = sum(bkm(p) for p in L["wonders"]["parks"])
    check("L2. 국립공원 수 = 경계 파일의 공원 수", np_ == n_raw,
          f"공원 {np_} / 파일 {n_raw}, 폴리곤 넓이 합 {area:,.1f} km² ('공원경계버퍼' 폴리곤, 덮는 칸 계산에만 씀), "
          + ", ".join(f"{p['short']} {bkm(p):,.0f}" for p in L["wonders"]["parks"]))

    # L3. 세계유산 수 = 원자료 등재 건수 (5d 부터 구성 유산 정리표의 등재 건이 기준. 5a 등재 파일의 행은 모두 그중 하나에 대응해야 한다)
    whh, whrows = rawcsv("datagokr/wonders/15107994_국가유산청_한국의_유네스코_세계유산_정보.csv")
    wh = L["wonders"]["world_heritage"]
    placed = sum(1 for e in wh if any(c.get("cell") is not None for c in e["components"]))
    if any("visitor_match" in e for e in wh):
        from lib.terrain import layer_path as _lp
        with open(_lp("world_heritage_components.csv"), encoding="utf-8-sig", newline="") as f:
            comp_kinds = {r["kind"] for r in csv.DictReader(f)}
        wix = {h: i for i, h in enumerate(whh)}
        names_5a = {r[wix["세계유산명"]].strip() for r in whrows}
        matched_5a = {e["visitor_match"].split("'")[1] for e in wh if e.get("visitor_match")}
        check("L3. 세계유산 수 = 원자료 등재 건수 (5d: 구성 유산 정리표 등재 건, 5a 등재 파일 행이 모두 대응)",
              len(wh) == len(comp_kinds) and names_5a == matched_5a,
              f"세계유산 {len(wh)} / 정리표 등재 건 {len(comp_kinds)}, 5a 등재 파일 {len(whrows)}행 중 대응 {len(names_5a & matched_5a)} "
              f"(대응 없는 5a 행 {sorted(names_5a - matched_5a)}), 지도에 놓인 등재 건 {placed}, 못 놓은 등재 건 {[e['name'] for e in wh if not any(c.get('cell') is not None for c in e['components'])]}")
    else:
        check("L3. 세계유산 수 = 원자료 등재 건수", len(wh) == len(whrows),
              f"세계유산 {len(wh)} / 원자료 {len(whrows)}행, 위치 찾음 {placed}, 못 찾음 {[e['name'] for e in wh if not e['components']]}")

    # L4. 원전 가동 호기 수와 용량 합 = 원자료 합
    hdr, rows = rawcsv("datagokr/energy/15046076_원자력안전위원회_국내_원자력발전소_현황.csv")
    ix = {h: i for i, h in enumerate(hdr)}
    op = [r for r in rows if r[ix["구분"]].strip() == "운영원전"]
    raw_mw = sum(float(r[ix["용량1(MWe)"]]) for r in op)
    # 5b 부터 원전은 발전기 현황으로 지도에 놓고, 원안위 본부 목록은 대조용(resources.nuclear_nssc)으로 남는다
    nuc = L["resources"].get("nuclear_nssc") or [u for u in L["resources"]["unplaced"] if u["kind"] == "nuclear"]
    out_units = sum(u["units_operating"] for u in nuc)
    out_mw = sum(u["value"] for u in nuc)
    check("L4. 원전 가동 호기 수·용량 합 = 원자료", out_units == len(op) and abs(out_mw - raw_mw) < 1e-6,
          f"본부 {len(nuc)}곳, 가동 {out_units}기 {out_mw:,.0f} MW / 원자료 {len(op)}기 {raw_mw:,.0f} MW. "
          f"본부별 합 = 파일 '용량2': {all(u['cap2_matches'] for u in nuc)}. (원안위 파일에는 위치 필드가 없음 — 5b 에서 발전기 현황 소재지로 놓음)")

    # L5. 유산 렌즈: 칸별 건수 합 = 좌표가 유효한 건수
    hz = next(l_ for l_ in lenses["lenses"] if l_["id"] == "heritage")
    hv_ = lens_values(hz, world)
    s_ = sum(v for v in hv_ if v)
    land_bad = sum(1 for i, v in enumerate(hv_) if (owner[i] >= 0) != (v is not None))
    H = L["wonders"]["heritage"]
    excl = H["excluded"]
    outside = sum(v for k, v in excl.items() if "범위 밖" in k)
    nocoord = sum(v for k, v in excl.items() if "좌표 0" in k)
    with_coord = sum(H["raw"].values()) - nocoord - sum(v for k, v in excl.items() if "해제" in k)
    check("L5. 유산 렌즈 칸별 건수 합 = 좌표가 유효한 건수", s_ == H["valid"] == with_coord - outside and land_bad == 0,
          f"칸 합 {s_:,} = 유효 {H['valid']:,} (원자료 {sum(H['raw'].values()):,}건 중 좌표 있음 {with_coord:,}, 남한 범위 밖으로 뺌 {outside}, "
          f"좌표 0·없음 {nocoord}). 육지 칸 = 값 있는 칸 ({'일치' if not land_bad else f'{land_bad}칸 어긋남'})")

    # L6. 위치 정밀도: 값이 정해진 네 가지 중 하나이고, 파일의 precision_counts 가 항목에서 다시 센 수와 같고,
    # 지도에 못 놓은 항목(unplaced)에는 칸이 없다 (감사 13: 예전에는 판정 없이 출력만 했다)
    miss = {}
    for nm, obj in L.items():
        for k, kd in obj["kinds"].items():
            if kd.get("missing"):
                miss[kd["name"]] = len(kd["missing"])
    unpl = {nm: len(obj.get("unplaced", [])) for nm, obj in L.items()}
    l6bad = []
    for nm, obj in L.items():
        recount = Counter(it["precision"] for it in obj["items"])
        if any(p not in ("point", "area", "county", "sido") for p in recount):
            l6bad.append(f"{nm} 정밀도 값 {sorted(recount)}")
        if dict(recount) != {k: v for k, v in obj.get("precision_counts", {}).items() if v}:
            l6bad.append(f"{nm} precision_counts {obj.get('precision_counts')} ≠ 다시 셈 {dict(recount)}")
        l6bad += [f"{nm} 못 놓은 항목에 칸: {u.get('name')}" for u in obj.get("unplaced", []) if u.get("cell") not in (None, -1)]
    check("L6. 위치 정밀도 값·정밀도별 항목 수 = 다시 센 수, 못 놓은 항목에 칸 없음", not l6bad,
          "정밀도 " + ", ".join(f"{a}/{b} {v}" for (a, b), v in sorted(prec.items()))
          + f" · 지도에 못 놓은 항목 {unpl} · 종류별 빠진 수 {miss}" + (f" · 어긋남 {l6bad}" if l6bad else ""))

    # L7. 원자료의 빈 값이 0 으로 들어간 곳이 없다
    zero_bad, checked = [], 0
    hdr, rows = rawcsv("datagokr/energy/15049846_한국수자원공사_댐별_제원_정보.csv")
    ix = {h: i for i, h in enumerate(hdr)}
    # 5d 부터 관측소 이름이 맞는 댐은 지도 항목(items)으로 옮겨 간다 — 둘 다에서 찾는다 (한 댐이 양쪽에 있으면 오류)
    dams = {u["name"]: u for u in L["resources"]["unplaced"] if u["kind"] == "dam"}
    for it in L["resources"]["items"]:
        if it["kind"] == "dam":
            if it["name"] in dams:
                zero_bad.append(f"{it['name']} 목록과 지도에 둘 다")
            dams[it["name"]] = it
    for r in rows:
        u = dams[r[ix["시설명"]].strip() + "댐"]
        checked += 1
        if (r[ix["총저수용량"]].strip() == "") != (u["value"] is None):
            zero_bad.append(u["name"])
    hdr, rows = rawcsv("datagokr/industry/15085874_한국산업단지공단_전국산업단지현황통계_국가산업단지.csv")
    ix = {h: i for i, h in enumerate(hdr)}
    rawv = {}
    for r in rows:
        rawv.setdefault((r[ix["시도"]].strip(), r[ix["단지명"]].strip()), r[ix["가동업체(개)"]].strip())
    for it in L["resources"]["items"]:
        if it["kind"] != "industrial_national":
            continue
        cand = [v for (sd, n), v in rawv.items() if n.startswith(it["name"])]
        checked += 1
        if cand and (cand[0] == "") != (it["value"] is None):
            zero_bad.append(it["name"])
    # 철도역 정차 횟수: 원자료에 '여객열차 N회'가 없으면 null 이어야 한다
    hdr, rows = rawcsv("datagokr/transport/15067652_국가철도공단_철도역_정보.csv")
    ix = {h: i for i, h in enumerate(hdr)}
    stops = {r[ix["역이름"]].strip(): r[ix["열차정차횟수"]] for r in rows}
    import re as _re
    for it in L["infrastructure"]["items"]:
        if it["kind"] != "station":
            continue
        has = bool(_re.search(r"여객열차\s*\d+\s*회", stops.get(it["name"], "")))
        checked += 1
        if has != (it["value"] is not None):
            zero_bad.append(f"{it['name']} 정차")
    check("L7. 원자료의 빈 값이 0 으로 들어간 곳 없음", not zero_bad,
          f"댐·국가산업단지·철도역 값 {checked}건 대조, 빈 칸 → null 유지" + (f", 어긋남 {zero_bad}" if zero_bad else ""))

    # L8. 집값: 거래 건수 합 = 원자료 행 수 (제외 조건별 수)
    hc = load_json(site("nation.json"))["econ"].get("housing_counts")
    if hc:
        sale_f, lease_f = HS.files()
        raw_sale = sum(len(HS._read(p)[1]) for p in sale_f.values())
        raw_lease = sum(len(HS._read(p)[1]) for p in lease_f.values())
        s, l2 = hc["sale"], hc["lease"]
        city_tr = sum(c["housing"]["trades"] or 0 for c in cities)
        city_je = sum(c["housing"]["jeonse_trades"] or 0 for c in cities)
        ok = (s["included"] + s["cancelled"] + s["unmapped"] + s["bad_value"] == s["rows"] == raw_sale
              and l2["jeonse"] + l2["monthly"] + l2["unmapped"] + l2["bad_value"] == l2["rows"] == raw_lease
              and city_tr == s["included"] and city_je == l2["jeonse"])
        check("L8. 집값 거래 건수 합 = 원자료 행 수", ok,
              f"매매 원자료 {raw_sale:,}행 = 포함 {s['included']:,} + 해제 {s['cancelled']:,} + 주소 대응 실패 {s['unmapped']:,} + 값 오류 {s['bad_value']:,}; "
              f"도시 거래 건수 합 {city_tr:,}. 전월세 {raw_lease:,}행 = 전세 {l2['jeonse']:,} + 월세 {l2['monthly']:,} + 주소 대응 실패 {l2['unmapped']:,} "
              f"+ 값 오류 {l2['bad_value']:,}; 도시 전세 건수 합 {city_je:,}")


def validate_5b_terrain(world, states, nation):
    import collections
    import csv

    from lib import official as OF
    from lib import terrain as TR

    owner, county = world["owner"], world["county"]
    land = [o >= 0 for o in owner]
    nl = sum(land)

    # T1. 육지 칸 수·총넓이·칸별 소유 시군구가 지형 보강 전과 같다
    bl = load_json(build("land_baseline.json"))
    same_owner = bl["owner"] == owner
    same_county = bl["county"] == county and bl["counties"] == [c["code"] for c in world["counties"]]
    nl0 = sum(1 for o in bl["owner"] if o >= 0)
    check("T1. 육지 칸 수·총넓이·칸별 소유 시군구 = 지형 보강 전", same_owner and same_county and bl["hex_km2"] == world["hex_km2"],
          f"보강 전 {nl0}칸 {nl0 * bl['hex_km2']:,.0f} km² / 지금 {nl}칸 {nl * world['hex_km2']:,.0f} km², 소유 시도 {'같음' if same_owner else '다름'}, "
          f"소유 시군구 {'같음' if same_county else '다름'} (기준: {bl['made_from']})")

    # T2. 피복이 있는 육지 칸 비율 (98% 이상), 분류별 칸 수, crop_src 별 칸 수
    keys = world["cover_keys"]
    cov = [world["cover"][i] for i in range(len(owner)) if land[i]]
    has = sum(1 for v in cov if v > 0)
    dist = collections.Counter(keys[v - 1] for v in cov if v > 0)
    ck = world["crop_kind"]
    ck_src = [ck["srcs"][s_] if s_ is not None else None for s_ in ck["src"]]
    ck_kind = [ck["kinds"][k_] if k_ is not None else None for k_ in ck["kind"]]
    src_n = collections.Counter(s_ or "없음" for s_ in ck_src)
    kind_n = collections.Counter(f"{s_ or '없음'}·{k_ or '구분 없음'}" for s_, k_ in zip(ck_src, ck_kind))
    crop_cells = sum(1 for v in cov if v == keys.index("crop") + 1)
    off_land = sum(1 for i in range(len(owner)) if not land[i] and world["cover"][i] != 0)
    check("T2. 피복이 있는 육지 칸 98% 이상, 분류별·crop_src 별 칸 수 (출력)",
          has / nl >= 0.98 and len(ck["cells"]) == crop_cells and off_land == 0,
          f"{has}/{nl} ({100 * has / nl:.1f}%), 분류별 {dict(dist)}; 농경지 {crop_cells}칸 crop_src {dict(src_n)} — {dict(kind_n)}; "
          f"육지 아닌 칸의 피복 {off_land}")

    # T3. 전국 cover_share 가중 합의 숲 비율 (참고: 국토의 6할 남짓이 산림)
    cs = world["cover_share"]
    tot = {k: sum(v for v in cs[k] if v is not None) for k in keys}
    s_all = sum(tot.values())
    fw = tot["forest"] / s_all if s_all else None
    cm = world["cover_meta"]
    w_px = cm["forest_weighted"]
    nat_stats = nation["nation"].get("land_stats", {}).get("value")
    st_forest = nat_stats["by"]["산림"]["pct"] if nat_stats else None
    # 감사 13: None 만 보던 판정을 물리적 범위와 공식 통계 대조로 바꾼다. 칸 비율 평균(정수 %)과 칸 평균(정확한 값)이 모두
    # 국가토지피복통계 산림 비율과 ±6%p 안, 그리고 0.4–0.75 안 (두 판 공용 — 세분류 토지피복지도 도엽 통계를 칸에 나눈 값)
    t3_ok = (fw is not None and st_forest is not None and 0.4 <= fw <= 0.75 and 0.4 <= w_px <= 0.75
             and abs(100 * fw - st_forest) <= 6 and abs(100 * w_px - st_forest) <= 6)
    check("T3. 전국 피복 가중 숲 비율: 0.4–0.75 이고 국가토지피복통계 산림 비율과 ±6%p 안", t3_ok,
          f"칸 비율(정수 %, 대분류 7개 합 대비)의 평균 {100 * fw:.1f}%, 칸 평균(정확한 값) {100 * w_px:.1f}% — "
          f"국가토지피복통계 산림 {st_forest}%. 기후에너지환경부 세분류 토지피복지도 도엽 통계를 칸에 나눴고(해양수·갯벌 제외), "
          f"도엽 통계가 닿지 않는 {cm['src']['esa']}칸만 ESA WorldCover 로 채웠다. "
          f"전국 비율 {', '.join(f'{TR.COVER_KO[k]} {100 * tot[k] / s_all:.1f}%' for k in keys)}")

    # T4. 강: 국가하천 수 = 원자료 수, 5대 강 본류가 이름으로 있다
    _, rrecs, _ = TR.read_vector("rivers.geojson")
    raw_nat = {(str(r["rivcd"]), r["name"]) for r in rrecs if r["grade"] == "국가하천"}
    n_raw_nat = sum(1 for r in rrecs if r["grade"] == "국가하천")
    drawn = {r["name"] for r in world["rivers"] if r["grade"] == "국가하천"}
    five = ["한강", "낙동강", "금강", "영산강", "섬진강"]
    mains = {r["name"] for r in world["rivers"] if r.get("main")}
    labels = collections.Counter(l_["name"] for l_ in world["river_labels"])
    check("T4. 강: 국가하천 수 = 원자료 수, 5대 강 본류가 이름으로 있음",
          len(raw_nat) == n_raw_nat == world["river_meta"]["national_raw"] and drawn == {n for _, n in raw_nat} and set(five) <= mains,
          f"원자료 국가하천 {n_raw_nat}건(이름 {len({n for _, n in raw_nat})}개) / 그린 국가하천 이름 {len(drawn)}개, 지방하천 선 "
          f"{sum(1 for r in world['rivers'] if r['grade'] == '지방하천')}개 ({world['river_meta']['local_min_km']:g} km 이상). "
          f"대권역 본류 {sorted(mains)}, 이름표 {dict(labels)}")

    # T5. 호수로 바뀐 칸 수와 넓이, 갯벌 칸 수와 폴리곤 넓이 합
    lake_cells = sum(1 for i in range(len(owner)) if land[i] and world["water"][i] == 3)
    tid = world["tidal"]
    tile = sum(1 for w_ in world["water"] if w_ == 4)
    by = tid["by_sido"]
    s_by = sum(v["area_km2"] for v in by.values())
    tile_land = sum(1 for i in range(len(owner)) if world["water"][i] == 4 and owner[i] >= 0)
    check("T5. 호수 칸 수·넓이, 갯벌 칸 수·폴리곤 넓이 합 (출력)",
          lake_cells == world["lake_meta"]["lake_cells"] and tile == sum(v["tile_cells"] for v in by.values()) and tile_land == 0,
          f"호수 칸 {lake_cells}개 ({lake_cells * world['hex_km2']:,.1f} km², {world['lake_meta']['lake_cells_by_name']}), 칸 위 수면 폴리곤 "
          f"{len(world['lakes'])}면 (1 km² 이상), 이름표 {len(world['lake_labels'])}곳; 갯벌 타일 {tile}칸 (육지 칸 0), 갯벌 폴리곤 {tid['polygons']}면 "
          f"넓이 합 {tid['polygon_area_km2']:,.1f} km² (칸에 든 넓이 {tid['area_in_cells_km2']:,.1f}, 시도별 합 {s_by:,.1f}; {tid['year']}년 제작). "
          + ", ".join(f"{next(s['short'] for s in world['states'] if s['code'] == k)} {v['tile_cells']}칸·{v['area_km2']:,.1f} km²" for k, v in sorted(by.items())))

    # T6·T7. 공식 GRDP
    no = nation["nation"]["official"]
    oc = nation["nation"]["official_compare"]
    rows = list(csv.DictReader(open(OF.PATH, encoding="utf-8-sig", newline="")))
    # 감사 13: 빌드가 적어 둔 ratio 를 읽지 않고 원표(공식값 정리표)의 전국 행과 도시 GRDP 합(E2 에서 시군구 공표 단위 합과 같음을 확인)으로 다시 계산한다
    nat_row = [float(r["value"]) * 1e6 for r in rows if r["indicator"] == "grdp_current" and OF.nospace(r["industry"]) == "지역내총생산(시장가격)"
               and OF.nospace(r["sido_now"]) == "전국" and str(r["year"]) == str(oc["year"]) and (r["value"] or "").strip()]
    sgg_sum = sum(c["gdp"] for c in load_json(site("cities.json")) if c.get("gdp") is not None)
    ratio = nat_row[0] / sgg_sum if len(nat_row) == 1 and sgg_sum else None
    t6_ok = (ratio is not None and 0.9 <= ratio <= 1.1 and abs(oc["grdp"]["official"] - nat_row[0]) < 1 and abs(oc["grdp"]["sgg_sum"] - sgg_sum) < 1
             and abs(oc["grdp"]["ratio"] - ratio) < 1e-4)
    check("T6. 공식 전국 GRDP(원표 전국 행) ÷ 도시 GRDP 합 (0.9–1.1), 화면 값과 같음", t6_ok,
          f"{oc['year']} 원표 전국 행 {len(nat_row)}개 {nat_row[0] / 1e12 if nat_row else float('nan'):,.2f}조 ÷ 도시 합 {sgg_sum / 1e12:,.2f}조 = {ratio if ratio else float('nan'):.4f}"
          f" (화면: 공식 {oc['grdp']['official'] / 1e12:,.2f}조, 시군구 합({oc['sgg_sum_label']}) {oc['grdp']['sgg_sum'] / 1e12:,.2f}조, ratio {oc['grdp']['ratio']})")
    g = [r for r in rows if r["indicator"] == "grdp_current" and OF.nospace(r["industry"]) == "지역내총생산(시장가격)"]
    bad = []
    for y in sorted({r["year"] for r in g}):
        nat_ = sum(float(r["value"]) for r in g if r["year"] == y and OF.nospace(r["sido_now"]) == "전국")
        sido_ = sum(float(r["value"]) for r in g if r["year"] == y and OF.nospace(r["sido_now"]) != "전국")
        if abs(sido_ / nat_ - 1) > 0.005:
            bad.append(f"{y} {sido_ / nat_:.4f}")
    check("T7. 시도 공식 GRDP 합 = 전국 공식값 (±0.5%, 지역소득 표 안에서)", not bad and abs(oc["sido_sum_check"]["ratio"] - 1) <= 0.005,
          f"연도 {sorted({r['year'] for r in g})} 모두 확인, {oc['year']} 시도 17행 합 / 전국 행 = {oc['sido_sum_check']['ratio']}" + (f", 어긋남 {bad}" if bad else ""))

    # T8. 종사자 공식 대분류 합 = 공식 합계 (±0.5%)
    jb = []
    for nm, o in [("전국", no)] + [(s["short"], s["official"]) for s in states]:
        j = o.get("jobs")
        if not j:
            jb.append(f"{nm} 없음")
            continue
        s_ = sum(v for v in j["by"].values() if v is not None)
        if any(v is None for v in j["by"].values()) or abs(s_ / j["total"] - 1) > 0.005:
            jb.append(f"{nm} {s_:,}/{j['total']:,}")
    check("T8. 종사자 공식 대분류 합 = 공식 합계 (±0.5%)", not jb,
          f"전국·시도 {1 + len(states)}곳, 전국 대분류 합 {sum(no['jobs']['by'].values()):,} = 합계 {no['jobs']['total']:,} "
          f"(농림어업 {no['jobs']['by']['A']:,} · 광업 {no['jobs']['by']['B']:,}, 시군구 합에서는 비공개)" + (f", 어긋남 {jb}" if jb else ""))

    # T9. 증가율이 붙은 도시 수 (전·후), 이어 붙이지 않은 도시
    ga = nation["econ"]["growth_audit"]
    # 감사 13: 도시 수가 줄지 않았는지만 보던 판정에, 증가율이 붙은 도시마다 양 끝 값을 정리표에서 다시 찾아 계산한 증가율과
    # 빌드 값이 같은지, 이어 붙인 두 표의 단위가 같은지, 과거표가 '2020년 기준' 표인지, from < to 인지를 더한다
    from lib import econ as E_
    ec_ = E_.Econ(world, load_json(site("cities.json")))

    def gmaps(rows_):
        by_ = collections.defaultdict(list)
        for r_ in rows_:
            if r_["indicator"] == "grdp_current" and E_.grdp_key(r_["industry"]) == "grdp":
                by_[(re.sub(r"^layers-", "", r_["source"]), str(r_["year"]))].append(r_)
        return by_
    cur_rows, hist_rows = gmaps(ec_.table("grdp")), gmaps(ec_.table("grdp_history"))
    cur_y = collections.defaultdict(list)
    for (tid_, y_), rs_ in cur_rows.items():
        cur_y[y_] += rs_
    t9bad, t9n = [], 0
    for c in load_json(site("cities.json")):
        g_ = c.get("gdp_growth")
        if not g_:
            continue
        t9n += 1
        to_v = E_.agg(ec_.unit_map(cur_y[str(g_["to"])], True), c["sgg"])
        m_ = re.search(r"과거표 이어 붙임 \(([^,]+),", g_.get("series", ""))
        if m_:
            hr = hist_rows.get((m_.group(1), str(g_["from"])), [])
            from_v = E_.agg(ec_.unit_map(hr, True), c["sgg"]) if hr else None
            units = {r_["unit"] for r_ in hr} | {r_["unit"] for r_ in cur_rows.get((m_.group(1), str(g_["to"])), [])}
            if any("2020년 기준" not in r_["basis"] for r_ in hr) or len(units) != 1:
                t9bad.append(f"{c['name']} 과거표 기준·단위 {sorted(units)}")
        else:
            from_v = E_.agg(ec_.unit_map(cur_y[str(g_["from"])], True), c["sgg"])
        if to_v is None or not from_v or g_["from"] >= g_["to"] or abs(100 * (to_v / from_v - 1) - g_["rate"]) > 0.006:
            t9bad.append(f"{c['name']} {g_['from']}→{g_['to']} 빌드 {g_['rate']} / 다시 계산 {None if not (to_v and from_v) else round(100 * (to_v / from_v - 1), 2)}")
    check("T9. 시군구 GRDP 증가율: 붙은 도시 수가 줄지 않고, 도시마다 양 끝 값을 정리표에서 다시 계산한 증가율 = 빌드 값, 이어 붙인 표의 기준·단위가 같음",
          ga["after"] >= ga["before"] and not t9bad and t9n == ga["after"],
          f"다시 계산한 도시 {t9n}곳{' 어긋남 ' + str(t9bad[:6]) if t9bad else ' 모두 같음'}; "
          f"전 {ga['before']} → 후 {ga['after']}곳 (과거표 이어 붙임 {len(ga['spliced'])}곳, 시작 연도별 {ga['from_years']}). "
          f"이어 붙이지 않은 도시 {len(ga['rejected'])}곳 {[r['city'] for r in ga['rejected']]}. 과거표({len(ga['history_tables'])}개 표)는 2022년까지, "
          f"최신 표는 2023년이라 겹치는 연도가 없어 0.5% 대조가 실제로 걸린 도시는 "
          f"{sum(1 for v in ga['overlap_years'].values() if v)}곳. 2015년 기준표 {len(ga['history_2015_tables'])}개는 이어 붙이지 않음")

    # T10. 공식값의 빈 칸이 0 으로 들어가지 않았다
    empties = [r for r in rows if (r["value"] or "").strip() == ""]
    zero_raw = sum(1 for r in rows if (r["value"] or "").strip() not in ("",) and float(r["value"]) == 0)

    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from walk(v, f"{path}.{k}")
        elif isinstance(o, (int, float)) and not isinstance(o, bool) and o == 0:
            yield path

    zeros = [f"{s['short']}{p}" for s in states for p in walk(s.get("official", {}))] + [f"전국{p}" for p in walk(no)]

    def walk_none(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                if v is None:
                    yield f"{path}.{k}"
                else:
                    yield from walk_none(v, f"{path}.{k}")
    # 감사 13: 예전 판정('빈 행이 없거나 0 이 없음')은 빈 행이 0개면 늘 참이었다. 화면 자료의 0 은 원표의 0 행이 있어야만 나올 수 있고
    # (원표 0 행이 없으면 화면의 0 은 모두 잘못), 원표의 빈 행 수만큼은 화면 자료에 0 이 아닌 결측으로 남아야 한다
    nones = sum(1 for s in states for p in walk_none(s.get("official", {}))) + sum(1 for p in walk_none(no))
    check("T10. 공식값: 화면 자료의 0 은 원표 0 행이 있을 때만, 원표 빈 행이 있으면 화면에 결측(null)", (not zeros or zero_raw > 0) and (not empties or nones > 0),
          f"공식값 표 {len(rows):,}행 중 빈 값 {len(empties)}행, 원표 값이 0 인 행 {zero_raw}행; 화면 자료의 공식값 중 0 인 값 {len(zeros)}개 {zeros[:6]}")


def validate_5b_layers(world, lenses):
    import collections
    import csv
    import math

    from lib.terrain import layer_path

    G = Grid(world["grid"]["cols"], world["grid"]["rows"], world["grid"]["radius"])
    owner, county, water, foreign = world["owner"], world["county"], world["water"], world["foreign"]
    tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    ox, oy = world["origin_5179"]
    mpu = world["meters_per_unit"]
    res = load_json(site("resources.json"))
    inf = load_json(site("infrastructure.json"))
    won = load_json(site("wonders.json"))
    fr = load_json(site("frontier.json"))

    def rows(name):
        with open(layer_path(name), encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def num(s):
        s = (s or "").strip()
        return float(s) if s else None

    def as_int_(v):
        return None if v is None else int(round(v))

    # P1. 공항 15곳 point, 칸 중심에서 한 칸 거리 안
    loc = rows("airport_locations.csv")
    ap = [i for i in inf["items"] if i["kind"] == "airport"]
    far = []
    for it in ap:
        e, n = tf.transform(it["lon"], it["lat"])
        ux, uy = (e - ox) / mpu, (oy - n) / mpu
        cx, cy = G.center(it["cell"])
        d = math.hypot(ux - cx, uy - cy)
        if d > G.W + 1e-6:
            far.append(f"{it['name']} {d:.1f}")
    tr = rows("airport_traffic.csv")
    pax_raw = {r["name"].split("(")[0]: num(r["value"]) for r in tr if r["kind"] == "여객" and r["name"] != "전체 합계"}
    bad0 = [it["name"] for it in ap if (pax_raw.get(it["name"][:-2]) is None) != (it["value"] is None)]
    # 인천공항: 두 판 모두 국가철도공단 공항철도 역위치(15041331)의 두 터미널 역 좌표 중점 (원자료에서 다시 계산). 항공정보간행물(AIP) 좌표 행은 쓰지 않는다
    import hashlib
    loc_k = [r for r in loc if r["source_id"] != "incheon-aip"]
    man5 = load_json(os.path.join(ROOT, "data", "raw", "layers5", "manifest.json"))
    e5 = man5["p1-15041331"]
    b5 = open(os.path.join(ROOT, "data", "raw", "layers5", *e5["file"].split("/")), "rb").read()
    st5 = {r[2]: (float(r[3]), float(r[4])) for r in csv.reader(b5.decode("cp949").splitlines()[1:]) if r[0] == "공항철도주식회사" and r[2] in ("인천공항1터미널", "인천공항2터미널")}
    pa = [tf.transform(*st5[k]) for k in ("인천공항1터미널", "인천공항2터미널")]
    back = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    mlon, mlat = back.transform((pa[0][0] + pa[1][0]) / 2, (pa[0][1] + pa[1][1]) / 2)
    icn = [i for i in ap if i["name"] == "인천공항"]
    icn_bad = []
    if hashlib.sha256(b5).hexdigest() != e5["sha256"]:
        icn_bad.append("역위치 파일 sha256 이 수집 기록과 다름")
    if len(icn) != 1:
        icn_bad.append(f"인천공항 항목 {len(icn)}개")
    else:
        it = icn[0]
        if abs(it["lon"] - mlon) > 1e-6 or abs(it["lat"] - mlat) > 1e-6:
            icn_bad.append(f"좌표 {it['lon']}, {it['lat']} ≠ 두 역 중점 {mlon:.7f}, {mlat:.7f}")
        if it.get("source") != "data-15041331" or it.get("position_note") != "제1·2여객터미널 역 위치의 중점 — 공항 기준점이 아님":
            icn_bad.append("출처·위치 문구가 다름")
        if not any("제1·2여객터미널 역 위치의 중점 — 공항 기준점이 아님" in d for d in it.get("detail") or []):
            icn_bad.append("툴팁 상세에 위치 문구 없음")
        if it["value"] != as_int_(pax_raw.get("인천")):
            icn_bad.append("여객 값이 항공정보포털 값과 다름")
    if any(i.get("source") == "incheon-aip" for i in ap) or any(s_.get("key") == "incheon-aip" for s_ in inf["kinds"]["airport"]["source"]):
        icn_bad.append("항공정보간행물(AIP) 출처가 남음")
    check("P1. 공항 15곳(한국공항공사 14 + 인천공항)이 모두 point, 칸 중심에서 한 칸(칸 간격 %.1f 단위) 안, 인천공항 = 공항철도 두 터미널 역 중점(원자료에서 다시 계산)" % G.W,
          len(ap) == 15 and len(loc_k) == 14 and all(i["precision"] == "point" for i in ap) and not far and not bad0 and not icn_bad,
          f"공항 {len(ap)} / 한국공항공사 원자료 {len(loc_k)} + 인천, 최대 거리 {max(i['dist_u'] for i in ap):.1f} 단위"
          + (f", 인천 {icn[0]['lon']}, {icn[0]['lat']} (칸 {icn[0]['cell']}, {icn[0]['place']}, 여객 {icn[0]['value']:,}명)" if icn else "")
          + f", 실적 없는 공항(값 null) {[i['name'] for i in ap if i['value'] is None]}" + (f", 멀다 {far}" if far else "") + (f", 빈 값 어긋남 {bad0}" if bad0 else "")
          + (f", 인천 문제 {icn_bad}" if icn_bad else ""))

    # P2. 무역항 31곳이 모두 해안에 닿은 칸
    def sea(j):
        return owner[j] < 0 and foreign[j] != 1 and water[j] in (1, 2, 4)
    pt = [i for i in inf["items"] if i["kind"] == "trade_port"]
    not_coast = [i["name"] for i in pt if not any(sea(j) for j in G.neighbors(i["cell"]))]
    flagged = [f["name"] for f in inf["kinds"]["trade_port"].get("flags", [])]
    check("P2. 무역항 31곳이 모두 해안에 닿은 칸 (하천항은 예외로 표시)", len(pt) == 31 and set(not_coast) == set(flagged) and len(not_coast) <= 1,
          f"무역항 {len(pt)}곳, 해안 칸 {len(pt) - len(not_coast)}곳, 해안 칸이 아닌 곳 {not_coast} (빌드 표시 {flagged}: 시군구에 바다와 맞닿은 칸이 없는 하천항), "
          f"정밀도 {dict(collections.Counter(i['precision'] for i in pt))}, 화물 값 없음 {[i['name'] for i in pt if i['value'] is None]}")

    # P3. 발전기 MW 총합 = 연료원별 합 = 시군구 합 + 대응 실패분; 원전 대조
    gens = rows("generators.csv")
    raw_tot = sum(float(r["value"]) for r in gens)
    P = res["power"]
    s_fuel = sum(P["by_fuel_mw"].values())
    s_sido = sum(sum(v.values()) for v in P["by_sido"].values())
    ok = abs(raw_tot - P["total_mw"]) < 0.01 and abs(s_fuel - raw_tot) < 0.01 and abs(P["unit_sum_mw"] + P["failed"]["mw"] - raw_tot) < 0.01 \
        and abs(s_sido - P["unit_sum_mw"]) < 0.5 and len(gens) == P["generators"]
    nc = P["nuclear_compare"]
    check("P3. 발전기 MW 총합 = 연료원별 합 = 시군구 합 + 대응 실패분, 원전 대조 (출력)", ok and all(n["match"] for n in nc),
          f"원자료 {len(gens):,}기 {raw_tot:,.3f} MW = 연료원별 합 {s_fuel:,.3f} = 시군구 합 {P['unit_sum_mw']:,.3f} + 대응 실패 {P['failed']['count']}기 "
          f"{P['failed']['mw']:,.3f} MW (시도별 합 {s_sido:,.3f}). 원전(발전기 현황, 시군구별) vs 원자력안전위원회 본부(5a): "
          + "; ".join(f"{n['sgg']} {n['mw']:,.0f} MW {n['units']}기 ↔ {n['nssc_site']} {n['nssc_mw']:,.0f} MW {n['nssc_units']}기" for n in nc)
          + f" — 합 {sum(n['mw'] for n in nc):,.0f} vs {sum(u['value'] for u in res['nuclear_nssc']):,.0f} MW")

    # P4. 국립공원 탐방객 23개 대응, 합계 = 43,310,477
    pv = rows("park_visitors.csv")
    got = [p for p in won["parks"] if p.get("visitors")]
    tot = sum(p["visitors"]["value"] for p in got)
    check("P4. 국립공원 탐방객 23개 대응, 합계 = 43,310,477", len(got) == len(pv) == 23 and tot == 43310477 == sum(int(r["value"]) for r in pv),
          f"대응 {len(got)}/{len(won['parks'])} 공원, 원표 {len(pv)}행, 합계 {tot:,}명")

    # P5. 지리적표시: 유효 = 지도 + 시도 + 목록만, place_from 'name' 수
    gi = [i for i in res["items"] if i["kind"] == "gi"]
    GI = res["gi"]
    graw = rows("geographical_indications.csv")
    valid_raw = sum(1 for r in graw if (r["kind"], r["registration_status"]) in (("농산물", "유효"), ("임산물", "운영"), ("수산물", "")))
    pf = collections.Counter(i["place_from"] for i in gi)
    check("P5. 지리적표시 유효 건수 = 지도 + 시도 단위 + 목록만, place_from 'name' 수 (출력)",
          GI["valid"] == valid_raw == len(gi) + len(GI["sido_level"]) + len(GI["list_only"]),
          f"원자료 {len(graw)}건, 유효 {valid_raw} = 지도 {len(gi)} (등록지역 {pf['area']} · 이름 place_from 'name' {pf['name']}) + 시도 {len(GI['sido_level'])} "
          f"+ 목록만 {len(GI['list_only'])}; 뺀 것 {GI['excluded']}")

    # P6. 도로: 고속국도 노선 수와 총연장
    rs = inf["kinds"]["roads"]["stats"]
    ex = rs["expressway"]
    check("P6. 도로: 고속국도 노선 수·총연장 (출력, 참고 5,000 km 안팎)", 4000 <= ex["dedup_km"] <= 6500,
          f"고속국도 노선 {ex['routes']}개, 링크 {ex['links']:,}개 합 {ex['raw_link_km']:,.0f} km (상·하행·연결로가 따로라 약 2.4배) → 이어 붙이고 겹친 선을 뺀 뒤 "
          f"{ex['dedup_km']:,.0f} km. 일반국도 노선 {rs['national']['routes']}개 {rs['national']['raw_link_km']:,.0f} → {rs['national']['dedup_km']:,.0f} km. "
          f"그린 선 {rs['lines']:,}개 {rs['points']:,}점")

    # P7. 새 렌즈: 값이 있는 육지 칸 비율, 범위
    NEW = ["forest", "cropland", "built", "foreign", "pm25", "smoking", "obesity", "depression", "health_good", "disaster", "academies"]
    land = [o >= 0 for o in owner]
    nl = sum(land)
    by = {l_["id"]: l_ for l_ in lenses["lenses"]}
    cov, rng, missing = [], [], [n for n in NEW if n not in by]
    for n in NEW:
        if n not in by:
            continue
        lz = by[n]
        vals = lens_values(lz, world)
        c = sum(1 for i in range(len(owner)) if land[i] and vals[i] is not None) / nl
        cov.append(f"{n} {100 * c:.1f}%")
        vs = [v for v in vals if v is not None]
        if c < 0.5:
            rng.append(f"{n} 덮음 미달")
        if lz["unit"] == "%" and (min(vs) < 0 or max(vs) > 100):
            rng.append(f"{n} [{min(vs)}, {max(vs)}]")
        if n == "pm25" and min(vs) <= 0:
            rng.append(f"pm25 최소 {min(vs)}")
        if n in ("disaster", "academies") and min(vs) < 0:
            rng.append(f"{n} 음수")
        if any(not land[i] and vals[i] is not None for i in range(len(owner))):
            rng.append(f"{n} 육지 아닌 칸에 값")
    pmz = by.get("pm25")
    pmz = dict(pmz, values=lens_values(pmz, world)) if pmz else None
    check("P7. 새 렌즈 11개: 값이 있는 육지 칸 비율, 범위 (비율 0–100, PM2.5 양수)", not missing and not rng,
          ", ".join(cov) + (f" / PM2.5 범위 {min(v for v in pmz['values'] if v is not None)}–{max(v for v in pmz['values'] if v is not None)} µg/m³" if pmz else "")
          + (f" / 없음 {missing}" if missing else "") + (f" / 어긋남 {rng}" if rng else ""))

    # P8. 사이트 JSON 합계 8 MB 이하
    tot = sum(os.path.getsize(p) for p in glob.glob(os.path.join(SITE_DATA, "*.json"))) / 1e6
    check("P8. 사이트 JSON 합계 8 MB 이하", tot <= 8, f"{tot:.2f} MB")

    # +. 접경지역 17곳, 층 항목 정밀도·빠진 수 (출력)
    br = rows("border_areas.csv")
    prec = collections.Counter((i["kind"], i["precision"]) for obj in (res, inf) for i in obj["items"])
    check("+ 접경지역 17곳 = 원자료, 5b 층 항목 수·정밀도 (출력)", len(fr["areas"]) == len(br) == 17,
          f"접경 {len(fr['areas'])}곳 (제1항 {sum(1 for a in fr['areas'] if a['clause'] == 1)}, 제2항 {sum(1 for a in fr['areas'] if a['clause'] == 2)}); "
          + ", ".join(f"{k}/{p} {v}" for (k, p), v in sorted(prec.items())))


def validate_5c(world, cities, states, nation, lenses):
    import collections

    import numpy as np

    from lib import terrain as TR

    owner, county = world["owner"], world["county"]
    N = len(owner)
    land = [o >= 0 for o in owner]
    nl = sum(land)
    codes = [c["code"] for c in world["counties"]]
    cname = {c["code"]: c["name"] for c in world["counties"]}
    lc = world["cover_share"]["land_cells"]
    src_of = {i: (world["cover_src"]["kinds"][s_] if s_ is not None else None) for i, s_ in zip(lc, world["cover_src"]["src"])}
    hk = world["hex_km2"]

    by, nat, blank, year, _ = TR.read_me_stats()
    validate_landcover(world, lenses)

    # C6. 패널 '땅' 구역: 통계 행(+ 통째로 든 개편 전 구역 행)을 다시 더한 값과 같음, 개편 전 구역 기준 합 표시, 남는 빈 곳은 null
    from lib import crosswalk
    old_units = nation["land_stats_meta"]["old_units"]
    cw_bad = [k_ for k_, v_ in old_units.items() if crosswalk.SPLITS.get(v_["old_code"]) != v_["successors"]]

    def recompute(cs_, olds):
        acc = {}
        rows_ = [by[c] for c in cs_ if c in by] + [blank[tuple(o.split(" ", 1))] for o in olds]
        for g, parts in TR.STATS_ITEMS.items():
            acc[g] = sum(r[p_] for r in rows_ for p_ in parts)
        return acc
    mism, nulls, olded = [f"{k_} 후신 대응이 crosswalk 와 다름" for k_ in cw_bad], [], []
    for nm, o, mem in ([(c["name"], c, c["sgg"]) for c in cities]
                       + [(s_["short"], s_, [c for c in codes if c[:2] == s_["code"]]) for s_ in states]):
        ls = o.get("land_stats")
        expect_old = [k_ for k_, v_ in old_units.items() if set(v_["successors"]) <= set(mem)]
        covered = {c for k_ in expect_old for c in old_units[k_]["successors"]}
        missing = [c for c in mem if c not in by and c not in covered]
        if ls is None or (ls["value"] is None) != bool(missing) or sorted(ls.get("old_units") or []) != sorted(expect_old if not missing else ls.get("old_units") or []):
            mism.append(f"{nm} 값/빈 값·개편 전 표시 어긋남")
            continue
        if missing:
            nulls.append(nm)
            continue
        if expect_old:
            olded.append(f"{nm}({'·'.join(expect_old)})")
        r = recompute(mem, expect_old)
        for g, v in r.items():
            if ls["value"]["by"][g]["ha"] != round(v):
                mism.append(f"{nm}.{g}")
    nv = nation["nation"]["land_stats"]["value"]
    nat_ok = nv["total_ha"] == round(nat["총합계"]) and all(nv["by"][g]["ha"] == round(sum(nat[p_] for p_ in TR.STATS_ITEMS[g])) for g in TR.STATS_ITEMS)
    check("C6. 패널 '땅' 구역(국가토지피복통계) = 시군구 행 합 (+ 통째로 든 개편 전 구역 행), 개편 전 구역 기준 합 표시", not mism and nat_ok,
          f"현재 코드가 빈 행 {len(blank)}개({', '.join(f'{k[0]} {k[1]}' for k in sorted(blank))})는 자치구·일반구로 나누지 않음 → 개편 전 구역 기준 합 {olded}, 값을 비운 곳 {nulls}; "
          f"전국 = 통계 전국 행 {'일치' if nat_ok else '어긋남'} (총합계 {nv['total_ha']:,} ha, 논 {nv['by']['논']['ha']:,} · 밭 {nv['by']['밭']['ha']:,} · "
          f"산림 {nv['by']['산림']['ha']:,} ({nv['by']['산림']['pct']}%) · 시가화 {nv['by']['시가화']['ha']:,} ha)"
          + (f" / 어긋남 {mism[:8]}" if mism else ""))



def validate_landcover(world, lenses):
    """칸 토지피복 (두 판 공용, lib/cover_sheets.py): 세분류 토지피복지도 도엽 통계(15150509)에서 다시 계산해 대조하고,
    국가 토지피복 통계(15163128)와 전국·시군구 비율을 견준다. WMS 그림에서 나온 값이 어느 판에도 없음을 본다."""
    import collections
    import random

    import numpy as np
    import shapely

    from lib import cover_sheets as CS
    from lib import terrain as TR
    owner, county = world["owner"], world["county"]
    N = len(owner)
    land = np.array([o >= 0 for o in owner])
    lc = world["cover_share"]["land_cells"]
    codes = [c["code"] for c in world["counties"]]
    tz = np.load(build("terrain_cache.npz"))
    skeys = [str(k) for k in tz["share_keys"]]
    cs_ex = tz["cover_share"]
    q = skeys.index
    K = TR.COVER_KEYS
    cm = world["cover_meta"]

    # C1s. 원자료와 도엽 테두리: 파일 sha256, 도엽마다 가장 늦은 기준년도 행, 테두리 넓이 검산
    sh_codes, A, rec = CS.read_sheets()
    ix = CS.index_check(sh_codes, A)
    same_codes = [str(c) for c in tz["sheet_codes"]] == sh_codes
    import json as _json
    rec_ok = _json.loads(_json.dumps(rec, ensure_ascii=False)) == cm["sheets"]
    sea_sheet = sh_codes.index("33601010") if "33601010" in sh_codes else None
    probe = []
    if sea_sheet is not None:
        probe.append(f"33601010(제주 북쪽 바다) 해양수 {100 * A[sea_sheet, CS.CLASSES.index('해양수')] / A[sea_sheet].sum():.0f}%")
    check("C1s. 토지피복 원자료: 도엽 통계 sha256 = 수집 기록, 도엽마다 기준년도가 가장 늦은 행 하나, 도엽 테두리 넓이 검산(중앙값 1e-5 아래, 98% 이상이 0.1% 안), 계산 기록과 같음",
          ix["median_abs_rel"] < 1e-5 and ix["within_1e-3"] >= 0.98 * ix["sheets"] and same_codes and rec_ok,
          f"{rec['rule']} 테두리 검산: 1e-4 안 {ix['within_1e-4']:,}/{ix['sheets']:,}, 1e-3 안 {ix['within_1e-3']:,}, 중앙값 {ix['median_abs_rel']:.1e}, "
          f"10% 넘게 모자란 도엽 {ix['short_over_10pct']}개(휴전선·해안에서 잘린 도엽); 특별도곽 {len(CS.SPECIAL_MIN)}개; " + "; ".join(probe))

    # C2s. 칸 비율 = 도엽 면적 × 저장한 나눔 무게 (원자료로 다시 계산), 나눔 무게의 기하 표본 검산, 저장한 정수 % = 반올림
    leaf, excl = CS.leaf_matrix(A)
    si, ci, w = tz["alloc_sheet"], tz["alloc_cell"], tz["alloc_w"]
    alloc = np.zeros((N, len(CS.LEAVES)))
    np.add.at(alloc, ci, w[:, None] * leaf[si])
    alloc_bad = float(np.abs(alloc - tz["alloc"]).max())
    wsum = np.zeros(len(sh_codes))
    np.add.at(wsum, si, w)
    w_over = int((wsum > 1 + 1e-9).sum())
    has_me = land & (alloc.sum(1) > 0)
    tot = np.where(alloc.sum(1) > 0, alloc.sum(1), 1)
    L_ = {k: CS.LEAVES.index(k) for k in CS.LEAVES}
    want = {}
    for k in CS.SHARE_KEYS:
        if k == "forest":
            v = alloc[:, [L_["broadleaf"], L_["conifer"], L_["mixed"]]].sum(1)
        elif k == "crop":
            v = alloc[:, [L_[x] for x in ("paddy", "field", "orchard", "greenhouse", "crop_other")]].sum(1)
        else:
            v = alloc[:, L_[k]]
        want[k] = v / tot
    share_bad = sum(int((np.abs(cs_ex[has_me, q(k)] - want[k][has_me]) > 1e-9).sum()) for k in CS.SHARE_KEYS)
    stored_bad = 0
    for k in skeys:
        col = world["cover_share"].get(k)
        ex = cs_ex[lc, q(k)]
        for t, v in enumerate(col):
            e = ex[t]
            if (v is None) != bool(np.isnan(e)) or (v is not None and v != int(round(100 * e))):
                stored_bad += 1
    # 나눔 무게 기하 검산: 도엽 200개를 골라 (도엽 ∩ 칸 ∩ 행정경계) ÷ (도엽 ∩ 행정경계) 를 다시 잰다
    from pyproj import Transformer as _T
    tf = _T.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    G = Grid(world["grid"]["cols"], world["grid"]["rows"], world["grid"]["radius"])
    ox, oy, mpu, R = world["origin_5179"][0], world["origin_5179"][1], world["meters_per_unit"], world["grid"]["radius"]
    rng = random.Random(20261127)
    pick = sorted(rng.sample(range(len(sh_codes)), 200))
    polys = CS.sheet_polygons([sh_codes[k] for k in pick], tf)
    gj = load_json(os.path.join(ROOT, "data", "raw", "boundary", "HangJeongDong_ver20261001.geojson"))
    from shapely.geometry import shape as _shape
    dg = shapely.transform(np.array([_shape(f["geometry"]) for f in gj["features"]], dtype=object),
                           lambda xy: np.column_stack(tf.transform(xy[:, 0], xy[:, 1])))
    dg = shapely.simplify(shapely.make_valid(dg), 15.0, preserve_topology=True)
    cand = [i for i in range(N) if world["foreign"][i] == 0]
    hexes = []
    for i in cand:
        cx, cy = G.center(i)
        xs = [cx + R * math.cos(math.radians(60 * k - 30)) for k in range(6)]
        ys = [cy + R * math.sin(math.radians(60 * k - 30)) for k in range(6)]
        hexes.append(shapely.Polygon([(ox + x * mpu, oy - y * mpu) for x, y in zip(xs, ys)]))
    s2, c2, w2, _, _ = CS.allocate(polys, np.array(hexes, dtype=object), np.array(cand), dg)
    got = collections.defaultdict(float)
    for a_, b_, v_ in zip(s2, c2, w2):
        got[(pick[a_], int(b_))] += float(v_)
    stored_w = collections.defaultdict(float)
    pset = set(pick)
    for a_, b_, v_ in zip(si, ci, w):
        if int(a_) in pset:
            stored_w[(int(a_), int(b_))] += float(v_)
    geo_bad = sum(1 for k_ in set(got) | set(stored_w) if abs(got.get(k_, 0) - stored_w.get(k_, 0)) > 1e-6)
    check("C2s. 칸 비율 = 도엽 세분류 면적 × 나눔 무게(원자료로 다시 계산), 나눔 무게를 도엽 200개 표본에서 기하로 다시 잼, 도엽마다 무게 합 ≤ 1, 저장한 정수 % = 반올림",
          alloc_bad < 1e-3 and share_bad == 0 and stored_bad == 0 and w_over == 0 and geo_bad == 0,
          f"도엽 × 칸 {len(si):,}쌍, 다시 낸 칸 면적과의 최대 차이 {alloc_bad:.2e} ㎡, 비율 어긋남 {share_bad}, 저장값 어긋남 {stored_bad}, 무게 합 > 1 도엽 {w_over}, "
          f"표본 도엽 200개의 무게 어긋남 {geo_bad} (칸 {len({b for _, b in got})}개에 걸침); 해양수·갯벌로 나누지 않은 면적 {excl.sum() / 1e6:,.0f} km²")

    # C3s. 대표 피복·출처·세분: 도엽 통계가 닿은 육지 칸 = 'me', 나머지 육지 칸만 ESA, 대분류 합 100%, 숲 = 활엽+침엽+혼효, crop_kind·forest_kind 다시 고름
    src_of = {i: (world["cover_src"]["kinds"][s_] if s_ is not None else None) for i, s_ in zip(lc, world["cover_src"]["src"])}
    src_bad = sum(1 for i in lc if (src_of[i] == "me") != bool(has_me[i]))
    esa = tz["esa_cnt"]
    esa_cells = [i for i in lc if src_of[i] == "esa"]
    esa_bad = sum(1 for i in esa_cells if esa[i].sum() == 0 or any(abs(cs_ex[i, q(k)] - esa[i, j] / esa[i].sum()) > 1e-9 for j, k in enumerate(K))
                  or any(not np.isnan(cs_ex[i, q(k)]) for k in ("broadleaf", "conifer", "mixed", "paddy", "field", "orchard", "greenhouse")))
    maj = cs_ex[:, [q(k) for k in K]]
    hasc = np.array([src_of.get(i) is not None for i in range(N)])
    one_bad = int((np.abs(np.nansum(maj[hasc], 1) - 1) > 1e-9).sum())
    want_cover = np.where(hasc, np.argmax(np.nan_to_num(maj, nan=-1), 1) + 1, 0)
    cover_bad = int((np.array(world["cover"]) != want_cover).sum())
    me_m = has_me
    fsum_bad = int((np.abs(cs_ex[me_m, q("forest")] - cs_ex[me_m][:, [q("broadleaf"), q("conifer"), q("mixed")]].sum(1)) > 1e-9).sum())
    csub_bad = int((cs_ex[me_m][:, [q("paddy"), q("field"), q("orchard"), q("greenhouse")]].sum(1) > cs_ex[me_m, q("crop")] + 1e-9).sum())
    ck, fk = world["crop_kind"], world["forest_kind"]
    ck_map = {c_: (ck["keys"][k_] if k_ is not None else None) for c_, k_ in zip(ck["cells"], ck["kind"])}
    fk_map = {c_: fk["keys"][k_] for c_, k_ in zip(fk["cells"], fk["kind"])}
    ci_, fi_ = K.index("crop") + 1, K.index("forest") + 1
    kind_bad = 0
    for i in lc:
        if want_cover[i] == ci_:
            sub = [cs_ex[i, q(k)] for k in TR.CROP_KINDS]
            exp = (TR.CROP_KINDS[int(np.argmax(sub))] if max(sub) > 0 else None) if src_of[i] == "me" else None
            kind_bad += ck_map.get(i, "없음") != exp
        elif want_cover[i] == fi_ and src_of[i] == "me":
            kind_bad += fk_map.get(i) != TR.FOREST_KINDS[int(np.argmax([cs_ex[i, q(k)] for k in TR.FOREST_KINDS]))]
    kind_bad += sum(1 for c_ in ck["cells"] if want_cover[c_] != ci_) + sum(1 for c_ in fk["cells"] if want_cover[c_] != fi_ or src_of[c_] != "me")
    n_src = collections.Counter(src_of[i] or "없음" for i in lc)
    check("C3s. 대표 피복·출처: 도엽 통계가 닿은 육지 칸 = 'me', 나머지만 ESA(대분류만, ESA 셀 비율), 대분류 합 100%, 숲 = 활엽+침엽+혼효, 대표 피복·crop_kind·forest_kind 다시 고른 값과 같음",
          src_bad == 0 and esa_bad == 0 and one_bad == 0 and cover_bad == 0 and fsum_bad == 0 and csub_bad == 0 and kind_bad == 0 and n_src["me"] >= 0.99 * len(lc),
          f"칸 출처 {dict(n_src)} (육지 {len(lc)}칸, ESA 칸 {esa_cells} — {', '.join(world['counties'][county[i]]['name'] for i in esa_cells)}); "
          f"어긋남: 출처 {src_bad}, ESA 칸 {esa_bad}, 대분류 합 {one_bad}, 대표 피복 {cover_bad}, 숲 합 {fsum_bad}, 농경지 세부 {csub_bad}, 세분 {kind_bad}; "
          f"대표 피복 {dict(collections.Counter(K[v - 1] for v in world['cover'] if v))}, 숲 종류 {dict(collections.Counter(fk_map.values()))}")

    # C4s. 땅 렌즈 = 칸 비율 (숲·농경지·시가지는 모든 피복 칸, 논·밭·침엽수림 비중은 도엽 통계 칸만), 설명이 WMS 를 출처로 적지 않음
    by_id = {l_["id"]: l_ for l_ in lenses["lenses"]}
    if lenses.get("phase") == "6":
        # 렌즈 막대에서 뺀 렌즈(밭·침엽수림 비중)는 빌드 사본(5e 결과)의 칸 값으로 본다
        for l_ in load_json(build("lenses_pre6.json"))["lenses"]:
            if l_["id"] in (lenses.get("retired") or {}) and l_["id"] not in by_id:
                by_id[l_["id"]] = l_
    out, badl = [], []
    for lid, key in (("forest", "forest"), ("cropland", "crop"), ("built", "built"), ("paddy_share", "paddy"), ("field_share", "field"), ("conifer", None)):
        lz = by_id.get(lid)
        if not lz:
            badl.append(f"{lid} 없음")
            continue
        v = lens_values(lz, world)
        mism = 0
        for i in range(N):
            if not land[i]:
                mism += v[i] is not None
                continue
            if key is None:
                f_ = cs_ex[i, q("forest")]
                e = None if (src_of.get(i) != "me" or not (f_ >= 0.10)) else round(100 * cs_ex[i, q("conifer")] / f_, 1)
            elif key in ("paddy", "field"):
                e = None if src_of.get(i) != "me" or np.isnan(cs_ex[i, q(key)]) else round(100 * cs_ex[i, q(key)], 1)
            else:
                e = None if np.isnan(cs_ex[i, q(key)]) else round(100 * cs_ex[i, q(key)], 1)
            mism += (v[i] is None) != (e is None) or (e is not None and abs(v[i] - e) > 1e-6)
        c = sum(1 for i in range(N) if land[i] and v[i] is not None) / land.sum()
        out.append(f"{lid} {100 * c:.1f}%")
        if mism or c < 0.5:
            badl.append(f"{lid} 값 어긋남 {mism}·덮음 {100 * c:.1f}%")
        d_ = lz.get("description", "")
        if "WMS" in d_ or "ESA WorldCover 2021 v200 (CC BY 4.0, 250 m 최빈값 격자) — 공개판" in (lz.get("source") or ""):
            badl.append(f"{lid} 설명·출처가 WMS·옛 공개판 피복을 적음")
    check("C4s. 땅 렌즈: 숲·농경지·시가지·논·밭·침엽수림 비중 값 = 칸 비율(도엽 통계), 논·밭·침엽수림은 도엽 통계 칸만, 값이 있는 육지 칸 50% 이상", not badl,
          "; ".join(out) + (f" / 문제 {badl}" if badl else ""))

    # C5s. 국가 토지피복 통계(15163128, 공공누리 제1유형)와 대조: 전국·시군구 비율 (판정 기준은 lib/cover_sheets.TOL — 실제 차이를 보고 정함), 화면 문장의 숫자
    st, yr, srec = CS.read_stats()
    units, miss = CS.stats_units(st, world)
    li = np.array(lc)
    cmp_ = CS.compare(cs_ex, li, np.array(county), codes, st, units)
    tol = CS.TOL
    nat_rows, bad = [], []
    for k, nm in CS.COMPARE_KEYS:
        r = cmp_["nation"][k]
        nat_rows.append(f"{nm} 칸 {r['cells_pct']:.2f}% / 통계 {r['stats_pct']:.2f}% ({r['diff_pp']:+.2f}%p)")
        if abs(r["diff_pp"]) > tol["nation_pp"]:
            bad.append(f"전국 {nm} {r['diff_pp']:+.2f}%p")
        s_ = cmp_["summary"][k]
        if s_["big_p90_pp"] > tol["county_p90_pp"][k]:
            bad.append(f"시군구 90백분위 {nm} {s_['big_p90_pp']}%p")
        if s_["big_max_pp"] > tol["county_max_pp"][k]:
            bad.append(f"시군구 최대 {nm} {s_['big_max_pp']}%p")
    if cm["compare"]["nation"] != cmp_["nation"] or cm["compare"]["summary"] != cmp_["summary"]:
        bad.append("저장한 대조 값(cover_meta.compare)이 다시 낸 값과 다름")
    for k, nm in CS.COMPARE_KEYS:
        if f"{nm} {cmp_['nation'][k]['cells_pct']:.1f}% (통계 {cmp_['nation'][k]['stats_pct']:.1f}%)" not in cm["bias_note"]:
            bad.append(f"치우침 문장에 {nm} 숫자가 없음")
    if len(units) < 245 or len(miss) > 3:
        bad.append(f"통계 시군구 행 대응 {len(units)}, 못 함 {miss}")
    big = [r for r in cmp_["counties"] if r["cells"] >= tol["county_min_cells"]]
    check(f"C5s. 칸 비율 vs 국가 토지피복 통계({yr}, 공공누리 제1유형): 전국 숲·논·밭·시가화 ±{tol['nation_pp']}%p, 칸 {tol['county_min_cells']}개 이상 시군구의 90백분위·최대 차이가 기준 안, 화면 문장 숫자 = 다시 낸 값",
          not bad, "전국 — " + "; ".join(nat_rows) + f". 시군구(칸 {tol['county_min_cells']}개 이상) {len(big)}곳 — "
          + "; ".join(f"{nm} 중앙값 {cmp_['summary'][k]['big_median_pp']}·90백분위 {cmp_['summary'][k]['big_p90_pp']} (기준 {tol['county_p90_pp'][k]})·최대 {cmp_['summary'][k]['big_max_pp']} (기준 {tol['county_max_pp'][k]})%p" for k, nm in CS.COMPARE_KEYS)
          + f". 통계 행 대응 {len(units)}묶음, 못 함 {miss}" + (f" / 어긋남 {bad}" if bad else ""))
    # 시험 구역 표 (출력)
    regions = {"김제·익산(호남 평야)": ["김제시", "익산시"], "인제": ["인제군"], "서울": [c["name"] for c in world["counties"] if c["code"].startswith("11")],
               "연천·철원·고성(접경)": ["연천군", "철원군", "고성군"], "제주": ["제주시", "서귀포시"]}
    rows_ = []
    for rn, names in regions.items():
        js = {j for j, c in enumerate(world["counties"]) if c["name"] in names and (rn != "연천·철원·고성(접경)" or c["code"][:2] in ("41", "51"))}
        cells = [i for i in lc if county[i] in js and src_of[i] is not None]
        a = CS.cell_mean_shares(cs_ex[cells])
        g_ = collections.defaultdict(float)
        for nm_, cs_, gg in units:
            if all(codes.index(c) in js for c in cs_):
                for k2, v2 in gg.items():
                    g_[k2] += v2
        b = CS.shares_from_leaves(g_) if g_ else None
        rows_.append(f"{rn} 칸 {len(cells)}: " + ", ".join(f"{nm} {100 * a[k]:.1f}" + (f"/{100 * b[k]:.1f}" if b else "") for k, nm in CS.COMPARE_KEYS))
    note("C5s 시험 구역 (칸 평균 % / 통계 %)", " · ".join(rows_))

    # C7s. WMS 그림에서 나온 것이 어느 판에도 없음: 출처·출처 줄·계산 층 입력, 칸 기록의 미분류 열·WMS 출처 이름, 빌드 코드가 WMS 타일을 읽지 않음
    SJ = load_json(site("sources.json"))
    used = [x["key"] for x in SJ["sources"]]
    att = set(SJ["attribution"]["base"]) | {k for v in SJ["attribution"]["lenses"].values() for k in v} | {k for d in SJ.get("derived") or [] for k in d.get("inputs") or []}
    hit = sorted({k for k in used + sorted(att) if PRF.never_used(k)})
    probs = []
    if hit:
        probs.append(f"쓰지 않는 출처 key {hit}")
    if "unclassified" in world["cover_share"]["keys"] or "unclassified" in skeys:
        probs.append("미분류(WMS 투명 픽셀) 열이 있음")
    if any("me_cnt" == f or "me_codes" == f for f in tz.files):
        probs.append("terrain_cache 에 WMS 픽셀 수가 있음")
    names = " ".join(world["cover_src"]["names"]) + " " + cm.get("source", "") + " " + cm.get("label", "")
    if "WMS" in names or "중분류 2025" in names:
        probs.append(f"피복 출처 이름이 WMS 를 가리킴: {names[:80]}")
    for t in world["tables"]["cover"]:
        r = t.get("rule") or ""
        if "WMS" in r or "50 m 그림" in r:
            probs.append(f"피복 규칙 '{t.get('name')}' 이 WMS 를 적음")
    code_hits = []
    for fn in sorted(glob.glob(os.path.join(ROOT, "pipeline", "build_*.py")) + glob.glob(os.path.join(ROOT, "pipeline", "lib", "*.py"))):
        txt = open(fn, encoding="utf-8").read()
        for pat in ("me_tiles(", "count_me_pixels(", "wms-tile-", '"landcover_me", "tiles"', "landcover_me/tiles"):
            if pat in txt:
                code_hits.append(f"{os.path.basename(fn)}:{pat}")
    if code_hits:
        probs.append(f"빌드 코드가 WMS 타일을 읽음: {code_hits}")
    check("C7s. WMS 그림에서 나온 것이 이 판(" + PROFILE + ")에 없음: 출처·출처 줄·계산 층 입력에 WMS·범례 쪽·AIP key 없음, 미분류 열·WMS 픽셀 수 없음, 피복 출처 이름·규칙이 WMS 를 적지 않음, 빌드 코드가 WMS 타일을 읽지 않음",
          not probs, "피복 출처: " + names[:120] + f"; 검사한 빌드 코드 {len(glob.glob(os.path.join(ROOT, 'pipeline', 'build_*.py')))}+lib 파일" + (f" / 문제 {probs}" if probs else ""))


def validate_5d(world, cities, states, nation, lenses):
    """명세 5c 2부 §8. 원자료 정리표를 다시 읽어 화면 자료와 대조한다."""
    import collections
    import csv

    from lib.terrain import layer_path

    def rows(name):
        with open(layer_path(name), encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    def num(s):
        s = (s or "").replace(",", "").strip()
        return float(s) if s else None

    tj = load_json(site("trade.json"))
    res = load_json(site("resources.json"))
    won = load_json(site("wonders.json"))
    G = Grid(world["grid"]["cols"], world["grid"]["rows"], world["grid"]["radius"])
    owner = world["owner"]
    code = [world["counties"][k]["code"] if k >= 0 else None for k in world["county"]]

    # D1. 수출입: 도시 합 (+ 대응 못 한 공표 단위) = 시군구 합 = 시도 합 = 전국 합
    tr = rows("trade_sgg.csv")
    ok, det = True, []
    for ind, k in (("trade_export", "export"), ("trade_import", "import"), ("trade_balance", "balance")):
        raw_sum = sum(num(r["value"]) for r in tr if r["indicator"] == ind)
        raw_blank = sum(1 for r in tr if r["indicator"] == ind and num(r["value"]) is None)
        unm = sum(num(r["value"]) for r in tr if r["indicator"] == ind and not r["sgg_code_now"].strip()
                  and any(u["name"] == r["sgg_name_raw"] for u in nation["nation"]["trade"]["unmatched"]))
        s_city = sum(c["trade"][k] for c in cities if c.get("trade") and c["trade"][k] is not None)
        s_sido = sum(s["trade"][k] for s in states if s.get("trade"))
        nat = nation["nation"]["trade"][k]
        good = abs(s_city + unm - raw_sum) < 1 and abs(s_sido - raw_sum) < 1 and abs(nat - raw_sum) < 1 and raw_blank == 0
        ok &= good
        det.append(f"{k}: 도시 합 {s_city:,.0f} + 대응 못 함 {unm:,.0f} = 원표 시군구 합 {raw_sum:,.0f} = 시도 합 {s_sido:,.0f} = 전국 {nat:,.0f}")
    # 시도마다: 그 시도 도시 합 + 그 시도의 대응 못 한 단위 = 시도 합
    for s in states:
        sc = sum(c["trade"]["export"] for c in cities if c["sido"] == s["code"] and c.get("trade") and c["trade"]["export"] is not None)
        if abs(sc + sum(u["export"] for u in s["trade"]["unmatched"]) - s["trade"]["export"]) >= 1:
            ok = False
            det.append(f"시도 {s['short']} 어긋남")
    hs = rows("trade_sgg_hs2.csv")
    n_hs = sum(len(u["e"]) + len(u["i"]) for u in tj["units"].values())
    over5 = [k for k, u in tj["units"].items() if len(u["e"]) > 5 or len(u["i"]) > 5]
    ok &= n_hs + tj["trade"]["hs_unmatched_rows"] == len(hs) and not over5
    top = sorted((c for c in cities if c.get("trade") and c["trade"]["export"] is not None), key=lambda c: -c["trade"]["export"])[:5]
    rk_ok = all(c["ranks"]["export"] == k + 1 for k, c in enumerate(top))
    unm_l = nation["nation"]["trade"]["unmatched"]
    check("D1. 수출입: 도시 합 + 대응 못 한 단위 = 시군구 합 = 시도 합 = 전국 합, 품목 행 대조, 수출 상위 5 (출력)", ok and rk_ok,
          "; ".join(det) + f". 공표 단위 {nation['nation']['trade']['units']}, 현재 코드 대응 못 함 {len(unm_l)} ({', '.join(u['name'] for u in unm_l)}). "
          f"품목 행 {len(hs)} = 단위에 붙음 {n_hs} + 대응 못 함 {tj['trade']['hs_unmatched_rows']}, 5개 넘는 단위 {over5}. "
          f"수출 상위 5 도시: " + ", ".join(f"{c['name']} {c['trade']['export'] / 1e8:,.1f}억 달러" for c in top))

    # D2. 교역로: 289행 = 17×17, 구간 수, 시도 간 총 톤 = 원자료 총 톤 − 시도 안(전남광주 안 포함)
    od = rows("flows_od.csv")
    o17, d17 = {r["origin"] for r in od}, {r["destination"] for r in od}
    tot = sum(num(r["value"]) for r in od)
    diag = sum(num(r["value"]) for r in od if r["origin"] == r["destination"])
    gj = sum(num(r["value"]) for r in od if {r["origin"], r["destination"]} == {"광주", "전남"})
    R = tj["routes"]
    inter = R["totals"]["inter_t"]
    segs = R["segments"]
    seg_ok = len(segs) == R["top_n"] and all(s["total"] == s["ab"] + s["ba"] and s["a"] != s["b"] and "12" != s["a"] + s["b"] for s in segs)
    no_gj = all(not ({s["a"], s["b"]} <= {"12"}) for s in segs)
    anc = all(owner[a["cell"]] >= 0 and code[a["cell"]] in a["sgg"] for a in R["anchors"].values()) and len(R["anchors"]) == 16
    sid_sum = sum(s["freight"]["intra_t"] for s in states)
    check("D2. 교역로: 289행 = 17×17, 구간 수, 시도 간 톤 = 원자료 총 톤 − 시도 안 흐름(전남광주 안 포함)",
          len(od) == 289 == len(o17) * len(d17) and abs(inter - (tot - diag - gj)) < 1 and seg_ok and no_gj and anc and abs(sid_sum - (diag + gj)) < 1,
          f"{len(od)}행 = {len(o17)}×{len(d17)}, 원자료 총 {tot:,.0f}톤 − 대각 {diag:,.0f} − 광주↔전남 {gj:,.0f} = {tot - diag - gj:,.0f} = 시도 간 {inter:,.0f}톤 "
          f"(시도 쌍 {R['pairs_total']}개), 그린 구간 {len(segs)}개 {R['totals']['shown_t']:,}톤 ({100 * R['totals']['shown_t'] / inter:.1f}%), "
          f"1위 {segs[0]['a']}–{segs[0]['b']} {segs[0]['total']:,}톤; 끝점 칸 16곳 모두 청사 시군구 안 {anc}")

    # D3. 주력 업종: 업종별 전국 합(공개값), 아이콘 수, 비공개 칸 수, 빈 값이 0 으로 들어가지 않음
    k20 = rows("key_industries_2020.csv")
    K = res["key_industries"]
    blank_raw = collections.Counter(r["industry"][:3] for r in k20 if not r["value"].strip())
    ic = collections.Counter(i["industry"] for i in res["items"] if i["kind"].startswith("ind_"))
    low = [i["name"] for i in res["items"] if i["kind"].startswith("ind_") and i["value"] < K["threshold_share"] * K["national_2020"][i["industry"]] - 1e-9]
    zeros_raw = {(r["sgg_name_raw"], r["industry"][:3]) for r in k20 if r["value"].strip() == "0"}
    zero_city = [(cid, cd) for cid, d in K["by_city"].items() for cd, v in d.items() if v[0] == 0]
    check("D3. 주력 업종(2020 경제총조사): 업종별 전국 합(공개값)·아이콘 수·비공개 행 수, 아이콘은 모두 기준 이상, 빈 값은 0 아님",
          dict(blank_raw) == K["blank_rows_2020"] and not low and (not zero_city or zeros_raw),
          ", ".join(f"{cd} 전국 {K['national_2020'][cd]:,}명 · 아이콘 {ic[cd]} · 비공개 {K['blank_rows_2020'][cd]}행" for cd in K["codes"])
          + f". 기준 {K['threshold_share'] * 100:.0f}% 미달 아이콘 {low}; 2020 값이 0 인 도시 {len(zero_city)} (원표 0 행 {len(zeros_raw)})")

    # D4. 댐 대응 수 / 34, 광산 293 = 놓은 것 + 주소 대응 실패
    dk = res["kinds"]["dam"]
    dam_items = [i for i in res["items"] if i["kind"] == "dam"]
    dam_un = [u for u in res["unplaced"] if u["kind"] == "dam"]
    obs = {re.sub(r"\s+", "", r["name"]).removesuffix("댐"): r for r in rows("dam_observations.csv")}
    dam_bad = [i["name"] for i in dam_items if i["precision"] != "point" or re.sub(r"\s+", "", i["name"]).removesuffix("댐") not in obs]
    far = []
    tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    ox, oy = world["origin_5179"]
    mpu = world["meters_per_unit"]
    for i in dam_items:
        e, n = tf.transform(i["lon"], i["lat"])
        cx, cy = G.center(i["cell"])
        if math.hypot((e - ox) / mpu - cx, (oy - n) / mpu - cy) > 2 * G.W + 1e-6:
            far.append(i["name"])
    if PUBLIC:
        check("D4. 댐: 관측소 이름 대응 수 / 34 (공개판: 광산은 X5)", len(dam_items) + len(dam_un) == dk["count"] == 34 and not dam_bad and not far,
              f"댐 point {len(dam_items)}/{dk['count']} (못 놓음 {[u['name'] for u in dam_un]}, 관측소에만 있음 {len(dk['obs_only'])}곳), 관측소 좌표에서 두 칸 넘는 댐 {far}")
        skip("D4 의 '가행 광산 293 = 놓은 것 + 대응 실패'", "공개판은 국내광산검색 광산을 싣지 않는다 (X5 가 없음을 확인)")
    M = res.get("mines_5d") or {"by_city": {}, "by_sido": {}, "count": None, "placed": 0, "failed": [], "by_mineral": {}, "threshold": None}
    mines = rows("active_mines.csv")
    s_items = sum(i["value"] for i in res["items"] if i["kind"] == "mine")
    s_city = sum(sum(v.values()) for v in M["by_city"].values())
    s_sido = sum(sum(v.values()) for v in M["by_sido"].values())
    if not PUBLIC:
      check("D4. 댐: 관측소 이름 대응 수 / 34, 가행 광산 293 = 시군구에 놓은 것 + 주소 대응 실패",
          len(dam_items) + len(dam_un) == dk["count"] == 34 and not dam_bad and not far and len(mines) == M["count"] == M["placed"] + len(M["failed"]) == 293
          and s_city == s_sido,
          f"댐 point {len(dam_items)}/{dk['count']} (못 놓음 {[u['name'] for u in dam_un]}, 관측소에만 있음 {len(dk['obs_only'])}곳), 관측소 좌표에서 두 칸 넘는 댐 {far}; "
          f"광산 {len(mines)} = 대응 {M['placed']} + 실패 {len(M['failed'])} ({'; '.join(f['reason'] for f in M['failed'])}), 광종별 {M['by_mineral']}, "
          f"아이콘 {sum(1 for i in res['items'] if i['kind'] == 'mine')}개(≥{M['threshold']}곳, 광산 {s_items}곳), 시도 합 {s_sido} (두 광종 광산은 두 번)")

    # D5. 국립공원 23곳 공식 면적 대응, 합계
    pa = rows("park_area.csv")
    got = [p for p in won["parks"] if p.get("designated")]
    s_ = sum(p["area_km2"] for p in got)
    raw_s = sum(num(r["value"]) for r in pa)
    ls = [p["short"] for p in got if p["land_km2"] is not None]
    check("D5. 국립공원 23곳 공식 지정면적 대응, 합계", len(got) == len(pa) == 23 and abs(s_ - raw_s) < 1e-6,
          f"대응 {len(got)}/{len(won['parks'])}, 합 {s_:,.3f} km² = 원표 합 {raw_s:,.3f} (공표 합계 6,888.394), 육상·해상 구분 {ls}; "
          f"경계 파일 넓이 합 {sum(p['boundary_km2'] for p in got):,.1f} km² 는 덮는 칸 계산에만 씀")

    # D6. 세계유산 17건, 구성 유산 97 = point + county + 목록만
    wh = won["world_heritage"]
    comp = rows("world_heritage_components.csv")
    pc = collections.Counter(c["precision"] or "list" for e in wh for c in e["components"])
    bad = []
    for e in wh:
        for c in e["components"]:
            if c["precision"] is None:
                if c["cell"] is not None:
                    bad.append(c["name"] + " 목록만인데 칸이 있음")
                continue
            if owner[c["cell"]] < 0:
                bad.append(c["name"] + " 육지 칸 아님")
            elif c["precision"] == "point":
                # 이름이 국가유산 이름과 띄어쓰기만 빼고 같아야 한다
                if re.sub(r"\s+", "", c["matched"].split(" ", 1)[1]) != re.sub(r"\s+", "", c["name"]):
                    bad.append(c["name"] + " 이름 다름")
            elif code[c["cell"]] not in c["sgg"]:
                bad.append(c["name"] + " 칸의 시군구 다름")
    wi = [i for i in won["items"] if i["kind"] == "world_heritage"]
    check("D6. 세계유산 17건, 구성 유산 97 = point + county + 목록만",
          len(wh) == 17 and len(comp) == 97 == pc["point"] + pc["county"] + pc["list"] and not bad,
          f"등재 {len(wh)}건, 구성 유산 {len(comp)} = point {pc['point']} + county {pc['county']} + 목록만 {pc['list']}; 아이콘 {len(wi)}개 "
          f"(정밀도 {dict(collections.Counter(i['precision'] for i in wi))}); 목록만: "
          + ", ".join(f"{e['name']}·{c['name']}" for e in wh for c in e["components"] if not c["precision"]) + (f" / 어긋남 {bad}" if bad else ""))

    # D7. 한우 상위 15곳, 빈 값이 0 으로 들어가지 않음
    hw = rows("livestock_hanwoo.csv")
    hv = {r["sgg_code_now"]: num(r["value"]) for r in hw}
    ca = [i for i in res["items"] if i["kind"] == "cattle"]
    top_ok = all(len(i["sgg"]) == 1 and hv.get(i["sgg"][0]) == i["value"] for i in ca) and len(ca) == 15
    srt = sorted((v for v in hv.values() if v is not None), reverse=True)
    rank_ok = sorted((i["value"] for i in ca), reverse=True) == srt[:15]
    F = res["farm"]
    zero_c = [k for k, v in (F.get("cattle") or {"by_city": {}})["by_city"].items() if v == 0]
    raw_zero = [k for k, v in hv.items() if v == 0]
    pig = rows("livestock_pig_sido.csv")
    P = F["pigs_sido_2026"]
    pig_null = [k for k, v in P["by_sido"].items() if v is None]
    pig_ok = sum(1 for r in pig if r["sido_now"] != "전국") == sum(1 for v in P["by_sido"].values() if v is not None) and P["sum_sido"] == P["national"]
    if PUBLIC:
        check("D7. 돼지 시도 2026 3분기 (공개판: 한우는 X5)", pig_ok,
              f"돼지 시도 합 {P['sum_sido']:,} = 전국 행 {P['national']:,}, 원표에 없는 시도(null) {pig_null}")
        skip("D7 의 '한우 2026-10 상위 15곳'", "공개판은 축산물이력제 한우 값을 싣지 않는다 (X5 가 없음을 확인)")
    else:
      check("D7. 한우 2026-10 상위 15곳 = 원표 상위, 빈 값이 0 으로 들어가지 않음, 돼지 시도 2026 3분기",
          top_ok and rank_ok and (not zero_c or raw_zero) and sum(1 for r in hw if not r["value"].strip()) == 0 and pig_ok,
          ", ".join(f"{i['name'].split(' · ')[1]} {i['value']:,}" for i in sorted(ca, key=lambda i: i["rank"]))
          + f"; 원표 {len(hw)}행(빈 값 {sum(1 for r in hw if not r['value'].strip())}), 값이 0 인 도시 {len(zero_c)}; 돼지 시도 합 {P['sum_sido']:,} = 전국 행 {P['national']:,}, "
          f"원표에 없는 시도(null) {pig_null}")

    # D8. 사이트 JSON 합계 5 MB 이하, 새 렌즈
    tot = sum(os.path.getsize(p) for p in glob.glob(os.path.join(SITE_DATA, "*.json"))) / 1e6
    lz = next((l_ for l_ in lenses["lenses"] if l_["id"] == "export_pc"), None)
    vals = lens_values(lz, world) if lz else []
    land = [o >= 0 for o in owner]
    cv = sum(1 for i in range(len(owner)) if land[i] and vals[i] is not None) / sum(land) if lz else 0
    vs = [v for v in vals if v is not None]
    check("D8. 사이트 JSON 합계 5 MB 이하, 1인당 수출 렌즈 값이 있는 육지 칸 50% 이상·음수 없음",
          tot <= 5 and lz is not None and cv >= 0.5 and min(vs) >= 0,
          f"{tot:.3f} MB ({', '.join(f'{os.path.basename(p)[:-5]} {os.path.getsize(p) / 1e3:.0f} KB' for p in sorted(glob.glob(os.path.join(SITE_DATA, '*.json'))))}); "
          f"export_pc 값이 있는 육지 칸 {100 * cv:.1f}%, 범위 {min(vs):,.0f}–{max(vs):,.0f} 달러/명")

    # + 5d 항목 위치 정밀도·place_from (출력)
    prec = collections.Counter((i["kind"], i["precision"], i.get("place_from")) for obj in (res, won) for i in obj["items"]
                               if i["kind"] in ("world_heritage", "knowledge", "dam", "mine", "cattle", "export_hub") or i["kind"].startswith("ind_"))
    note("5d 층 항목 수·위치 정밀도·place_from", ", ".join(f"{k}/{p}/{f} {v}" for (k, p, f), v in sorted(prec.items())))


def validate_5e(world, cities, states, lenses):
    """명세 5e §5. 원자료(data/raw/layers3, 읽기만 — 데이터로만 쓴다)를 다시 읽어 화면 자료와 대조한다."""
    import csv
    import io

    from lib.common import raw

    def read_cp949(path):
        with open(path, "rb") as f:
            b = f.read()
        try:
            t = b.decode("utf-8-sig")
        except UnicodeDecodeError:
            t = b.decode("cp949")
        rows = list(csv.reader(io.StringIO(t, newline="")))
        return [h.strip() for h in rows[0]], [r for r in rows[1:] if any(x.strip() for x in r)]

    def nosp(s):
        return re.sub(r"\s+", "", s or "")

    res = load_json(site("resources.json"))
    P = res["farm"]["pigs"]
    # E1. 돼지: 층 값의 합(대응된 단위) + 대응 실패 값 = 원자료 최신 연도 합
    pdir = raw("layers3", "pig")
    pf = [f for f in os.listdir(pdir) if f.lower().endswith(".csv")]
    head, prow = read_cp949(os.path.join(pdir, pf[0]))
    H = {h: k for k, h in enumerate(head)}
    ylatest = max({r[H["년도"]].strip() for r in prow}, key=int)
    p26 = [r for r in prow if r[H["년도"]].strip() == ylatest]
    raw_vals = [r[H["전체두수"]].replace(",", "").strip() for r in p26]
    raw_sum = sum(int(v) for v in raw_vals if v)
    usum = sum(v for v in P["units"].values() if v is not None)
    unm = sum(u["value"] or 0 for u in P["unmatched"])
    pig_items = [i for i in res["items"] if i["kind"] == "pigs"]
    top = sorted((v for v in P["units"].values() if v is not None), reverse=True)[:15]
    top_ok = sorted((i["value"] for i in pig_items), reverse=True) == top and all(i["year"] == ylatest for i in pig_items)
    check(f"5e-E1. 돼지 {ylatest}: 층 값의 합 + 대응 실패 값 = 원자료 합, 아이콘 = 상위 15",
          len(pf) == 1 and usum + unm == raw_sum and top_ok and len(pig_items) == 15,
          f"단위 {len(P['units'])}개 합 {usum:,} + 대응 실패 {len(P['unmatched'])}행 {unm:,} = {usum + unm:,} / 원자료 {len(p26)}행 합 {raw_sum:,}; "
          f"대응 실패 {[u['name'] for u in P['unmatched']]}; 상위 15 {[(i['name'].split(' · ')[-1], i['value']) for i in sorted(pig_items, key=lambda i: i['rank'])]}")
    # E2. 돼지: 원자료의 빈 값이 0 으로 들어간 곳 없음 (0 인 단위 수 = 원자료에 0 으로 적힌 행 수, 빈 값 행 수 = null 단위 + 대응 실패 null)
    raw_blank = sum(1 for v in raw_vals if not v)
    raw_zero = sum(1 for v in raw_vals if v and int(v) == 0)
    u_zero = sum(1 for v in P["units"].values() if v == 0) + sum(1 for u in P["unmatched"] if u["value"] == 0)
    u_null = sum(1 for v in P["units"].values() if v is None) + sum(1 for u in P["unmatched"] if u["value"] is None)
    city_zero = [k for k, v in P["by_city"].items() if v == 0]
    check("5e-E2. 돼지: 원자료 빈 값이 0 으로 들어간 곳 없음 (빈 값 = null, 원자료 0 = 0)",
          raw_blank == u_null and raw_zero == u_zero and (not city_zero or raw_zero),
          f"원자료 빈 값 {raw_blank}행 / null 단위 {u_null}; 원자료 0 {raw_zero}행 / 0 인 단위 {u_zero}; 값이 0 인 도시 {len(city_zero)}; "
          f"원표에 행이 없어 자료 없음(null)인 도시 {sum(1 for v in P['by_city'].values() if v is None)}곳 (그 가운데 광역시 전체 값에 든 곳 {len(P['metro'])})")
    # E3. 보훈: 시군구 값의 합 (+ 현재 구로 나눌 수 없는 옛 구역 행) = 원자료 시군구 행 합 (중복 파일 제외 뒤)
    lz = next(l_ for l_ in lenses["lenses"] if l_["id"] == "veterans")
    A = lz["audit"]
    vdir = raw("layers3", "veterans")
    snames = {s["name"] for s in world["states"]}
    raw_cty, raw_tot, per_sido, dropped_ok = 0, 0, [], True
    names_by_file = {}
    for fn in sorted(os.listdir(vdir)):
        if not fn.lower().endswith(".csv"):
            continue
        head, rows = read_cp949(os.path.join(vdir, fn))
        H = {h: k for k, h in enumerate(head)}
        last = max({(int(r[H["연도"]]), int(r[H["분기"]])) for r in rows})
        lr = [r for r in rows if (int(r[H["연도"]]), int(r[H["분기"]])) == last]
        sd = lr[0][H["시도"]].strip()
        no = fn.split(".")[0]
        c_, t_ = 0, 0
        nm_set = set()
        for r in lr:
            nm = r[H["시군구"]].strip()
            v = int(r[H["합계"]].replace(",", ""))
            if nosp(nm) == nosp(sd) or "합계" in nosp(nm):
                t_ += v
            else:
                c_ += v
                nm_set.add(re.sub(r"\(.*\)$", "", nosp(nm)))
        names_by_file[no] = (sd, nm_set)
        if no in A["dropped_files"]:
            continue
        raw_cty += c_
        raw_tot += t_
        per_sido.append(f"{sd} {last[0]}Q{last[1]} 시군구 행 {c_:,} / 시도 이름·합계 행 {t_:,} (차 {t_ - c_:+,})")
    for no in A["dropped_files"]:
        sd, nm_set = names_by_file[no]
        keep = {d["keep"] for d in A["duplicates"]}
        cover = set().union(*(names_by_file[k][1] for k in keep)) if keep else set()
        dropped_ok &= sd not in snames and nm_set <= cover   # 옛 시도 이름 파일이고 시군구가 모두 소재 시도 파일에 있음
    lsum = sum(lz["counts"].values())
    rsum = sum(r_["value"] for r_ in A["residual"])
    usum_v = sum(u["value"] for u in A["unmatched"] if u["file"] not in A["dropped_files"])
    check("5e-E3. 보훈: 시군구 값의 합 (+ 현재 구로 나눌 수 없는 옛 구역 행) = 원자료 시군구 행 합 (중복 파일 제외 뒤), 시도 합계 행과의 차이 (출력)",
          lsum + rsum == raw_cty and dropped_ok and lsum + rsum + usum_v == A["raw_county_rows"],
          f"시군구 값 합 {lsum:,} + 옛 구역 행 {rsum:,} ({', '.join(r_['name'] + ' ' + str(r_['value']) for r_ in A['residual'])}) = {lsum + rsum:,} / 원자료 시군구 행 합 {raw_cty:,}; "
          f"뺀 중복 파일 {A['dropped_files']} (시군구 {len(A['duplicates'])}곳 겹침, 값이 다른 곳 {sum(1 for d in A['duplicates'] if not d['same'])}); "
          f"시도 이름·합계 행 합 {raw_tot:,} − 시군구 행 합 = {raw_tot - raw_cty:+,} — 이 가운데 이름으로 시군구를 정할 수 없는 묶음 "
          f"{', '.join(u['sido'] + ' ' + u['name'] + ' ' + format(u['value'], ',') for u in A['unmatched'])}; " + "; ".join(per_sido))
    # E4. 보훈: 256개 시군구 가운데 값이 있는 수 (240 미만이면 실패)
    bc = lz["by_county"]
    have = sum(1 for v in bc if v is not None)
    cname = {c["code"]: f"{c['sido']} {c['name']}" for c in world["counties"]}
    miss = [cname[world["counties"][k]["code"]] for k, v in enumerate(bc) if v is None]
    neg = [v for v in bc if v is not None and v <= 0]
    check("5e-E4. 보훈: 값이 있는 시군구 240개 이상 (256개 중)", have >= 240 and len(bc) == len(world["counties"]) == 256 and not neg,
          f"{have}/256, 값 없음 {miss}; 천 명당 범위 {min(v for v in bc if v is not None):.1f}–{max(v for v in bc if v is not None):.1f}; 대응 실패 이름 {len(A['unmatched'])}개")
    # E5. 사이트 JSON 합계 < 5 MB
    files = sorted(glob.glob(os.path.join(SITE_DATA, "*.json")))
    tot = sum(os.path.getsize(p) for p in files)
    check("5e-E5. 사이트 JSON 합계 < 5 MB", tot < 5e6,
          f"{tot:,} 바이트 = {tot / 1e6:.3f} MB ({', '.join(f'{os.path.basename(p)[:-5]} {os.path.getsize(p) / 1e3:.0f} KB' for p in files)})")


SPEC6_GROUPS = {
    "people": ["density", "growth", "fertility", "over65", "extinction", "foreign", "veterans"],
    "living": ["gdp_pc", "wage", "home", "jeonse", "employment", "fiscal", "assistance"],
    "industry": ["top_industry", "manufacturing_share", "export_pc"],
    "daily": ["single", "owner", "long_commute", "doctors", "pm25", "health"],
    "learn": ["degree", "academies", "religion", "religion_top"],
    "land": ["forest", "cropland", "paddy_share", "built", "heritage", "disaster"],
}
SPEC6_RETIRED = ["under15", "age", "sex_ratio", "migration", "farm_share", "smoking", "obesity", "depression", "health_good",
                 "paddy", "field_share", "conifer"]
# 공개판(profile public)에서 빼는 렌즈 (build_phase6.PUBLIC_REMOVED 와 같은 목록 — X8 이 lenses.json removed 와 대조)
PUBLIC_REMOVED_LENSES = ["home", "jeonse"]
if PUBLIC:
    SPEC6_GROUPS = {g: [i for i in ids if i not in PUBLIC_REMOVED_LENSES] for g, ids in SPEC6_GROUPS.items()}
    SPEC6_RETIRED = [i for i in SPEC6_RETIRED if i not in PUBLIC_REMOVED_LENSES]
SPEC6_N = sum(len(v) for v in SPEC6_GROUPS.values())


def validate_6(world, cities, states, nation, lenses):
    import collections
    K = len(world["counties"])
    # F1. 렌즈 수·묶음, 뺀 렌즈의 값이 시군구(또는 도시) 자료에 남아 있음
    ids = [l_["id"] for l_ in lenses["lenses"]]
    grp = {g["id"]: [l_["id"] for l_ in lenses["lenses"] if l_["group"] == g["id"]] for g in lenses["groups"]}
    same_tbl = grp == SPEC6_GROUPS
    rv = {it["id"]: it for it in lenses["retired_values"]["items"]}
    snap = {l_["id"]: l_ for l_ in load_json(build("lenses_pre6.json"))["lenses"]}
    kept = []
    bad = []
    for lid in SPEC6_RETIRED:
        it = rv.get(lid)
        if it is None or lid in ids:
            bad.append(f"{lid} 없음 또는 렌즈 막대에 남음")
            continue
        n_ = sum(1 for v in it["values"] if v is not None)
        if "by_county" in snap[lid] and it["values"] != snap[lid]["by_county"]:
            bad.append(f"{lid} 시군구 값이 5e 렌즈와 다름")
        if n_ < 0.5 * K:
            bad.append(f"{lid} 값 있는 시군구 {n_}")
        kept.append(f"{lid} {n_}/{K}")
    city_keys = {"under15": lambda c: c["age"]["under15"], "age": lambda c: c["age"]["mean_est"], "sex_ratio": lambda c: c["sex_ratio_20_39"]}
    for lid, f in city_keys.items():
        nc = sum(1 for c in cities if f(c) is not None)
        if nc != len(cities):
            bad.append(f"{lid} 도시 값 {nc}/{len(cities)}")
    redirect_ok = all(lenses["retired"].get(r) in ids for r in SPEC6_RETIRED)
    if PUBLIC:
        skip("F1 의 '렌즈 33종'", "공개판은 아파트 매매가·전세가를 싣지 않아 31종으로 센다 (빠진 2개는 X8). 뺀 렌즈 12개(침엽수림 비중 포함)는 두 판이 같다")
    check(f"F1. 렌즈 {SPEC6_N}종(명세 표 그대로{' — 공개판은 아파트 2종을 뺀 표' if PUBLIC else ''}), 묶음 6개, 뺀 렌즈 {len(SPEC6_RETIRED)}개의 값이 시군구 값(또는 도시 자료)에 남음",
          len(ids) == SPEC6_N and len(grp) == 6 and same_tbl and not bad and redirect_ok,
          f"렌즈 {len(ids)}종, 묶음 {len(grp)}개 ({', '.join(f'{g} {len(v)}' for g, v in grp.items())}), 표와 같음 {same_tbl}; "
          f"뺀 렌즈 시군구 값 {'; '.join(kept)}; 도시 자료 유소년·평균연령·청년 성비 {len(cities)}곳 모두; 옛 id 가 남은 렌즈로 이어짐 {redirect_ok}"
          + (f"; 문제 {bad}" if bad else ""))

    # F2. 건강 지수: 네 값이 모두 있는 시군구에서만 값, 전국(시군구 평균) 100 ± 0.5, 다시 계산한 값과 같음
    hl = next(l_ for l_ in lenses["lenses"] if l_["id"] == "health")
    parts = [("smoking", 1), ("obesity", 1), ("depression", 1), ("health_good", -1)]
    cols = [(rv[p]["values"], s_) for p, s_ in parts]
    full = [k for k in range(K) if all(v[k] is not None for v, _ in cols)]
    zs = []
    for v, s_ in cols:
        a = [v[k] for k in full]
        mu = sum(a) / len(a)
        sd = math.sqrt(sum((x - mu) ** 2 for x in a) / len(a))
        zs.append({k: s_ * (v[k] - mu) / sd for k in full})
    re_ = {k: 100 - 10 * sum(z[k] for z in zs) / 4 for k in full}
    hv = hl["by_county"]
    only_full = all((hv[k] is not None) == (k in re_) for k in range(K))
    mx = max(abs(hv[k] - re_[k]) for k in full)
    vals = [x for x in hv if x is not None]
    mean = sum(vals) / len(vals)
    pop = {c["code"]: 0 for c in world["counties"]}
    for i, p_ in enumerate(lenses["cell_pop"]):
        if p_:
            pop[world["counties"][world["county"][i]]["code"]] += p_
    pw = sum(hv[k] * pop[world["counties"][k]["code"]] for k in full) / sum(pop[world["counties"][k]["code"]] for k in full)
    check("F2. 건강 지수: 구성 값 네 개가 모두 있는 시군구에서만 값, 전국 평균 100 ± 0.5", only_full and abs(mean - 100) <= 0.5 and mx <= 0.051,
          f"값 있는 시군구 {len(vals)}/{K} (네 값 모두 있는 곳 {len(full)}), 시군구 평균 {mean:.3f}, 다시 계산한 값과 최대 차 {mx:.3f}, "
          f"범위 {min(vals):.1f}–{max(vals):.1f}; 참고: 인구 가중 평균 {pw:.2f} (명세의 '전국 평균'은 시군구 단순 평균으로 봄)")

    # F3. 배율 규칙: 전국 배율에서 그려지는 아이콘 수 (종류별), 합 150 이하
    L = {nm: load_json(site(f"{nm}.json")) for nm in ("wonders", "resources", "infrastructure")}
    items = [it for o in L.values() for it in o["items"]]
    no_tier = [it["id"] for it in items if it.get("tier") not in (0, 1, 2)]
    Z = L["wonders"].get("zoom", {})
    KG = Z.get("knowledge_groups", {})
    groups = KG.get("groups", [])

    def drawn_count(t):
        # 대학 묶음에 든 대학은 빼고 묶음 표지를 하나로 센다
        c = collections.Counter(it["kind"] for it in items if it.get("tier", 9) <= t and str(t) not in it.get("grouped", {}))
        c.update(g_["kind"] for g_ in groups if t in g_["view_tiers"])
        return c
    c0, c1 = drawn_count(0), drawn_count(1)
    never = [k for k in ("gi", "port", "station", "heritage_cluster", "rice", "cattle", "pigs") if c0.get(k)] + [k for k in c0 if k.startswith("ind_")]
    # 지식: 전국 = 과학기술원·출연연 전부 + 연구비 상위 5개 대학, 나머지 대학은 중간부터. 묶음은 같은 도시의 같은·이웃 칸 대학만
    by_id = {it["id"]: it for it in items}
    know = [it for it in items if it["kind"] == "knowledge"]
    univ = [it for it in know if str(it.get("inst_kind", "")).startswith("대학")]
    inst = [it for it in know if it not in univ]
    top5 = {u["id"] for u in sorted(univ, key=lambda u: (-(u.get("funding_won") or 0), u["id"]))[:KG.get("univ_national", 5)]}
    kbad = [it["name"] for it in inst if it.get("tier") != 0] + [u["name"] for u in univ if u.get("tier") != (0 if u["id"] in top5 else 1)]
    gbad = []
    for g_ in groups:
        ms = [by_id.get(m) for m in g_["members"]]
        if len(ms) < 2 or any(m is None or not str(m.get("inst_kind", "")).startswith("대학") for m in ms) or len({m["city"] for m in ms}) != 1:
            gbad.append(g_["id"])
        elif any(m.get("grouped", {}).get(str(t)) != g_["id"] for m in ms for t in g_["view_tiers"]):
            gbad.append(g_["id"] + " 표시 없음")
    pri = Z.get("draw_priority", {})
    zc0 = sum(Z.get("counts", {}).get("0", {}).values())
    check("F3. 배율 규칙: 전국 배율 아이콘 수(종류별) 합 150 이하, 지리적표시·어항·역·밀집지·주력 업종·농축산은 전국 배율에 없음, 규칙 문장이 JSON 에 있음, "
          "지식은 기관 전부 + 대학 연구비 상위 5만 전국(나머지 대학은 중간), 대학 묶음은 같은 도시 대학 2곳 이상, 그리기 우선순위(원전 먼저) 규칙이 있음",
          sum(c0.values()) <= 150 and not no_tier and not never and len(Z.get("rules", [])) >= 3 and not kbad and not gbad
          and pri.get("first") == ["nuclear"] and pri.get("rule") in Z.get("rules", []) and KG.get("rule") in Z.get("rules", []) and zc0 == sum(c0.values()),
          f"전국 {sum(c0.values())}: " + ", ".join(f"{k} {v}" for k, v in sorted(c0.items(), key=lambda kv: -kv[1]))
          + f" / 중간까지 {sum(c1.values())} / 전부 {len(items)}"
          + f"; 지식 전국 {c0.get('knowledge', 0)}(기관 {len(inst)} + 대학 {len(top5)}, 묶음 {sum(1 for g_ in groups if 0 in g_['view_tiers'])}개) · 중간 {c1.get('knowledge', 0)}"
          + f"(대학 {len(univ)}곳, 묶음 {' '.join(g_['name'] for g_ in groups if 1 in g_['view_tiers'])})"
          + (f"; tier 없음 {no_tier[:5]}" if no_tier else "") + (f"; 전국에 있으면 안 되는 종류 {never}" if never else "")
          + (f"; 지식 배율 어긋남 {kbad}" if kbad else "") + (f"; 묶음 문제 {gbad}" if gbad else "") + (f"; JSON counts 합 {zc0} ≠ {sum(c0.values())}" if zc0 != sum(c0.values()) else ""))

    # F4. 순위 보고서 (감사 13: 첫 모드의 시도 합만 보던 판정을 넓힌다)
    #  - 모든 수치·모든 모드의 시도 행과 도시 행(값·순위·제외 수·작은 도시 수·상위 8·하위 3)을 states.json·cities.json 에서 다시 만들어 대조
    #  - 전국 값을 nation.json 과 독립 계산(합칠 수 있는 수치는 시도 합, 비율은 구성 행의 원 인원)으로 대조
    from lib.common import rnd as rnd_
    R = {r["id"]: r for r in nation["reports"]["items"]}
    want = ["population", "over65", "extinction", "food", "production", "gold", "science", "culture"]
    rows_ = []
    bad = [w for w in want if w not in R]
    st_by = {s["code"]: s for s in states}
    PCMIN = nation["reports"]["per_capita_min_pop"]
    n_ = nation["nation"]

    def s_off(s, w):
        G = (s.get("official") or {}).get("gdp")
        return G["yields"][w] if G else None

    def s_pc(s, w):
        G = (s.get("official") or {}).get("gdp")
        p = s["pop_series"].get(str(G["year"])) if G else None
        return rnd_(G["yields"][w] / p, 0) if G and G["yields"][w] is not None and p else None

    def c_pc(c, w):
        v = c["yields"][w] if c.get("yields") else None
        p = c["pop_series"].get(str(c.get("gdp_pop_ref"))) if c.get("gdp_pop_ref") else None
        return rnd_(v / p, 0) if v is not None and p else None
    FN = {("population", "total"): (lambda s: s["population"], lambda c: c["population"], None),
          ("population", "growth"): (lambda s: s["growth_5y"], lambda c: c["growth_5y"], PCMIN),
          ("over65", "total"): (lambda s: s["age"]["over65"], lambda c: c["age"]["over65"], None),
          ("extinction", "total"): (lambda s: s["extinction_index"], lambda c: c["extinction_index"], None)}
    for w in ("food", "production", "gold", "science", "culture"):
        FN[(w, "total")] = (lambda s, w=w: s_off(s, w), lambda c, w=w: c["yields"][w] if c.get("yields") else None, None)
        FN[(w, "per_capita")] = (lambda s, w=w: s_pc(s, w), lambda c, w=w: c_pc(c, w), PCMIN)
    n_modes = 0
    for w in want:
        r = R.get(w)
        if not r:
            continue
        for m in r["modes"]:
            fn = FN.get((w, m["id"]))
            if fn is None:
                bad.append(f"{w}/{m['id']} 다시 계산할 규칙 없음")
                continue
            n_modes += 1
            sf, cf, pmin = fn
            exp_s = sorted(({"code": s["code"], "value": sf(s)} for s in states), key=lambda x: -(x["value"] if x["value"] is not None else -1e30))
            got_s = [{"code": x["code"], "value": x["value"]} for x in m["sido"]]
            if got_s != exp_s or [x["rank"] for x in m["sido"]] != [k + 1 if x["value"] is not None else None for k, x in enumerate(exp_s)]:
                bad.append(f"{w}/{m['id']} 시도 행이 다시 만든 순위와 다름")
            elig = [c for c in cities if not (pmin and c["population"] < pmin)]
            vals_ = [(c["id"], cf(c)) for c in elig]
            ok_ = sorted([(i, v) for i, v in vals_ if v is not None], key=lambda t: -t[1])
            CR = m["cities"]
            exp_top = [{"id": i, "value": v, "rank": k + 1} for k, (i, v) in enumerate(ok_[:8])]
            exp_bot = [{"id": i, "value": v, "rank": k + 1} for k, (i, v) in list(enumerate(ok_))[-3:]] if len(ok_) > 11 else \
                [{"id": i, "value": v, "rank": k + 1} for k, (i, v) in list(enumerate(ok_))[8:]]
            strip = lambda lst: [{k: x[k] for k in ("id", "value", "rank")} for x in lst]  # noqa: E731
            if (strip(CR["top"]) != exp_top or strip(CR["bottom"]) != exp_bot or CR["n"] != len(ok_)
                    or CR["excluded"] != sum(1 for _, v in vals_ if v is None) or CR["filtered_small"] != len(cities) - len(elig)):
                bad.append(f"{w}/{m['id']} 도시 행(상위·하위·제외·작은 도시 수)이 다시 만든 순위와 다름")
        # 전국 값
        m0 = r["modes"][0]
        comp = [x["value"] for x in r["composition"]["rows"]]
        if r["additive"]:
            s_rep = sum(x["value"] for x in m0["sido"] if x["value"] is not None)
            if w == "population":
                nat = n_["population"]
                s_raw = sum(s["population"] for s in states)
                comp_ok = sum(comp) == nat
            else:
                nat = n_["official"]["gdp"]["yields"][w]
                s_raw = sum(s_off(s, w) for s in states)
                comp_ok = abs(sum(v for v in comp if v is not None) - nat) <= abs(nat) * 0.001
            if not (s_rep == s_raw and abs(s_raw - nat) <= max(1, abs(nat) * 1e-9) and r["national"] == nat and comp_ok):
                bad.append(f"{w} 전국 {r['national']:,.0f} / 시도 합 {s_rep:,.0f} / 다시 더함 {s_raw:,.0f} / nation {nat:,.0f} / 구성 합 {'같음' if comp_ok else '다름'}")
            rows_.append(f"{w} 시도 16 합 = 전국 {nat:,.0f} (차 {s_raw - nat:,.0f})")
        else:
            if w == "over65":
                indep = 100 * sum(comp) / n_["population"]
                ok_n = r["national"] == n_["age"]["over65"] and abs(indep - r["national"]) < 0.01
            else:
                indep = comp[0] / comp[1]
                ok_n = r["national"] == n_["extinction_index"] and abs(indep - r["national"]) < 0.0006
            if not ok_n:
                bad.append(f"{w} 전국 {r['national']} / nation {n_['age']['over65'] if w == 'over65' else n_['extinction_index']} / 구성 행으로 다시 계산 {indep:.4f}")
            rows_.append(f"{w} 비율 전국 {r['national']} = 구성 행으로 다시 계산 {indep:.3f}")
    check("F4. 순위 보고서 자료: 수치 8개 모든 모드의 시도·도시 행(값·순위·제외·상하위)을 states·cities 에서 다시 만든 것과 같고, 전국 값 = 시도 합(합칠 수 있는 수치) 또는 구성 인원으로 다시 계산한 비율",
          not bad and n_modes == sum(len(R[w]["modes"]) for w in want if w in R),
          f"모드 {n_modes}개 대조; " + "; ".join(rows_) + (f"; 문제 {bad}" if bad else ""))

    # F5. 출처 기록 (감사 13·15): 모든 출처에 이용허락 필드, 주소는 http(s), 원자료 파일이 실제로 있고 sha256·바이트가 같음
    #  (묶음은 기록의 files 마다, 수작업 표는 저장소의 코드 파일), 쓴 곳 문구가 이용허락 열과 어긋나지 않음
    import hashlib
    from lib.common import RAW, ROOT
    SJ = load_json(site("sources.json"))
    S = SJ["sources"]
    no_f = [s["key"] for s in S if "license" not in s or "license_url" not in s]
    unk = sum(1 for s in S if s.get("license") == "미확인")
    frm = collections.Counter(s.get("license_from") or "미확인" for s in S)
    hcache = {}

    def sha(p):
        if p not in hcache:
            h = hashlib.sha256()
            with open(p, "rb") as fh:
                for blk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(blk)
            hcache[p] = (h.hexdigest(), os.path.getsize(p))
        return hcache[p]
    pbad, n_files = [], 0
    for s in S:
        k = s["key"]
        u = s.get("url")
        if not (isinstance(u, str) and u.startswith(("https://", "http://"))) and not s.get("manual"):
            pbad.append(f"{k} 주소 {u!r}")
        if s.get("license") not in (None, "미확인") and "이용허락 미확인" in (s.get("used_in") or ""):
            pbad.append(f"{k} 쓴 곳 '이용허락 미확인' ↔ 이용허락 {s['license'][:20]}")
        f = s.get("file")
        if not f:
            pbad.append(f"{k} 파일 경로 없음")
            continue
        base = ROOT if s.get("file_root") == "repo" else RAW
        p = os.path.join(base, *f.rstrip("/").split("/"))
        if os.path.isdir(p):
            # 묶음: 기록의 files 마다 디렉터리 안에 같은 sha256 파일이 있어야 한다
            fl = s.get("files") or []
            if not fl:
                pbad.append(f"{k} 디렉터리인데 파일별 기록(files) 없음")
                continue
            have = {}
            for dp, _, fs in os.walk(p):
                for fn_ in fs:
                    if fn_ in ("manifest.json", "manifest.tsv"):
                        continue
                    hh, bb = sha(os.path.join(dp, fn_))
                    have[hh] = bb
            for e in fl:
                n_files += 1
                if not e.get("sha256") or e["sha256"] not in have or (e.get("bytes") is not None and have[e["sha256"]] != e["bytes"]):
                    pbad.append(f"{k} 묶음 파일 {e.get('file') or e.get('title')} sha256 불일치·없음")
        elif os.path.isfile(p):
            n_files += 1
            hh, bb = sha(p)
            if not s.get("sha256") or hh != s["sha256"] or (s.get("bytes") is not None and bb != s["bytes"]):
                pbad.append(f"{k} {f} sha256·바이트 불일치 (기록 {str(s.get('sha256'))[:12]}/{s.get('bytes')}, 파일 {hh[:12]}/{bb})")
        else:
            pbad.append(f"{k} 파일 없음 {f}")
    check("F5. 출처 기록: 이용허락 필드, http(s) 주소(수작업 표 제외), 원자료 파일(묶음은 파일마다)·sha256·바이트 일치, 쓴 곳과 이용허락이 어긋나지 않음",
          not no_f and not pbad,
          f"출처 {len(S)}건, 확인한 파일 {n_files}개, '미확인' {unk}건, 값의 근거 {dict(frm)}, licenses.csv {'있음' if os.path.exists(build('licenses.csv')) else '없음'}"
          + (f"; 필드 없음 {no_f[:10]}" if no_f else "") + (f"; 문제 {len(pbad)}건 {pbad[:8]}" if pbad else ""))

    # F7. 공표 단위 (감사 01): 시 전체·개편 전 구 단위로만 공표된 값이 여러 시군구에 칠해지면 그 단위가 렌즈에 적혀 있어야 한다.
    #  나뉜 구 묶음(부천·화성·인천 개편)의 구들이 모두 같은 값이면 공표 단위 기록이 있어야 하고, 기록된 단위의 시군구는 모두 같은 값이어야 한다.
    from lib import crosswalk as CW
    cidx = {c["code"]: k for k, c in enumerate(world["counties"])}
    fams = {}
    for old, new_ in CW.SPLITS.items():
        fams.setdefault(frozenset(new_), old)
    fams = [frozenset(cidx[c] for c in f) for f in fams] + [frozenset(cidx[c] for c in CW.SPLITS["28110"] + CW.SPLITS["28140"])]
    fams = [f for f in fams if len(f) > 1]
    ubad, n_units, n_l = [], 0, 0
    for lz in list(lenses["lenses"]) + list(lenses["retired_values"]["items"]):
        bc = lz.get("by_county") if "by_county" in lz else (lz.get("values") if lz.get("level", "").startswith("시군구 값") else None)
        if bc is None or len(bc) != K:
            continue
        n_l += 1
        covered = {}
        for u in lz.get("units", []):
            n_units += 1
            vs_ = {bc[k] for k in u["counties"]}
            if len(vs_) != 1 or None in vs_:
                ubad.append(f"{lz['id']} {u['name']} 단위 안 값이 다름 {vs_}")
            if not u.get("label") or u["name"] not in u["label"]:
                ubad.append(f"{lz['id']} {u['name']} 표시 문구 없음")
            covered[frozenset(u["counties"])] = u
        for f in fams:
            vs_ = {bc[k] for k in f}
            # 범주 렌즈(최대 종교 등)는 이웃 구의 범주가 우연히 같을 수 있어 '같은 값 → 공표 단위' 추론에서 뺀다 (기록된 단위의 일관성은 위에서 본다)
            if lz.get("format") != "cat" and len(vs_) == 1 and None not in vs_ and not any(f <= cu for cu in covered):
                ubad.append(f"{lz['id']} {'·'.join(world['counties'][k]['name'] for k in sorted(f))} 같은 값인데 공표 단위 기록 없음")
            if f in covered and not covered[f]["reorg"] and covered[f].get("year") and covered[f]["year"] < 2024:
                ubad.append(f"{lz['id']} {covered[f]['name']} {covered[f]['year']} 값인데 '개편 전' 표시 없음")
    check("F7. 공표 단위 (감사 01): 나뉜 구가 모두 같은 값이면 렌즈에 공표 단위(시 전체·개편 전) 기록, 기록된 단위 안 값이 같고 표시 문구가 있음",
          not ubad and n_units > 0, f"시군구 값 렌즈·뺀 지표 {n_l}개, 공표 단위 기록 {n_units}개" + (f"; 문제 {ubad[:8]}" if ubad else ""))

    # F8. 공유 그림 출처 (감사 03): 출처 줄 규칙이 모든 렌즈·뺀 지표를 덮고, 가리키는 key 가 모두 있고, 지도 바탕에 행정경계·OSM·토지피복이 있고,
    #  이용조건 경고(감사 02)가 토지피복 출처 기록과 restrictions 에 있다
    A = SJ.get("attribution") or {}
    keys_ = {s["key"] for s in S}
    allids = [l_["id"] for l_ in lenses["lenses"]] + [it["id"] for it in lenses["retired_values"]["items"]]
    abad = [i for i in allids if i not in A.get("lenses", {})]
    abad += [f"{i}:{k}" for i, ks in A.get("lenses", {}).items() for k in ks if k not in keys_]
    abad += [k for k in A.get("base", []) if k not in keys_]
    base_need = ("boundary_admdong", "osm-water", "data-15150509")
    abad += [k for k in base_need if k not in A.get("base", [])]
    # 토지피복은 두 판 모두 공공누리 제1유형 도엽 통계 — WMS 그림 이용조건 경고(옛 감사 02)는 없어야 맞다 (C7s 가 WMS 출처가 없음을 본다)
    rs_ok = not any(PRF.never_used(r.get("key") or "") for r in SJ.get("restrictions", [])) and all(s.get("license_short") for s in S)
    check("F8. 공유 그림 출처 줄 규칙이 렌즈 전부를 덮고 key 가 모두 있음, 지도 바탕에 행정경계·OSM·토지피복(세분류 토지피복지도 도엽 통계), WMS 경고 없음",
          not abad and rs_ok, f"렌즈·뺀 지표 {len(allids)}개, 지도 바탕 key {len(A.get('base', []))}개 ({', '.join(A.get('base', []))[:200]}), 경고 {len(SJ.get('restrictions', []))}건" + (f"; 문제 {abad[:8]}" if abad else "") + ("" if rs_ok else "; WMS 경고가 남음"))

    # F9. 도시 포함 범위 (감사 05): 자치구를 묶은 도시는 범위 문구가 있고, 같은 광역시 안의 군 도시 이름을 모두 적는다
    sid_name = {s_["code"]: s_["name"] for s_ in states}
    rbad = []
    for c in cities:
        if c["kind"] in ("특별시", "광역시") and len(c["sgg"]) > 1:
            gun = [o["name"] for o in cities if o["sido"] == c["sido"] and o is not c and o["name"].endswith("군") and sid_name[c["sido"]].endswith("광역시")]
            sc_ = c.get("scope") or ""
            if not sc_ or f"자치구 {len(c['sgg'])}곳" not in sc_ and "자치구" not in sc_ or any(g_ not in sc_ for g_ in gun):
                rbad.append(f"{c['name']} '{sc_}' (군 {gun})")
    check("F9. 자치구를 묶은 도시의 범위 문구: 자치구 수와 따로 둔 군 이름", not rbad, f"문제 {rbad}" if rbad else "모두 있음 · " + "; ".join(f"{c['name']}: {c['scope']}" for c in cities if c.get("scope"))[:300])

    # F6. 사이트 JSON 합계 < 5 MB
    files = sorted(glob.glob(os.path.join(SITE_DATA, "*.json")))
    tot = sum(os.path.getsize(p) for p in files)
    check("F6. 사이트 JSON 합계 < 5 MB", tot < 5e6,
          f"{tot:,} 바이트 = {tot / 1e6:.3f} MB ({', '.join(f'{os.path.basename(p)[:-5]} {os.path.getsize(p) / 1e3:.0f} KB' for p in files)})")


def validate_7b(world, cities, states, nation, lenses):
    """7b단계 (docs/ideas/site_r3.md): 빌드가 새로 싣는 계산(입지계수·특성 표시·전국 기준값·닮은 도시 근거·추천 시점·배치 예산)을
    원래 값에서 다시 계산해 대조한다. build_insights.py 의 코드를 가져다 쓰지 않고 따로 계산한다."""
    import statistics
    N = nation["nation"]
    E = nation["econ"]
    OG, OJ = N["official"]["gdp"], N["official"]["jobs"]
    keys16, kko = E["industry_keys"], E["ksic_ko"]
    fin = lambda v: isinstance(v, (int, float)) and math.isfinite(v)  # noqa: E731

    # G1. 입지계수: 도시 비중 ÷ 전국 공식 비중 (비중 1% 이상, 비공개 제외), 소수 1자리. NaN·무한대 없음
    bad, n_g, n_j = [], 0, 0
    for c in cities:
        b, und = c.get("gdp_by_industry"), set(c.get("gdp_undisclosed") or [])
        exp = {}
        if b and b.get("grdp"):
            for k in keys16:
                v = b.get(k)
                if v is None or k in und:
                    continue
                sh = v / b["grdp"]
                if sh >= 0.01:
                    exp[k] = round(sh / (OG["by"][k] / OG["by"]["grdp"]), 1)
        got = c.get("lq_gdp")
        if got is None or set(got) != set(exp) or any(not fin(got[k]) or abs(got[k] - exp[k]) > 1e-9 for k in exp):
            bad.append(f"{c['name']} 부가가치 {got} != {exp}"[:120])
        if any(k in und for k in (got or {})):
            bad.append(f"{c['name']} 비공개 업종에 LQ")
        n_g += len(exp)
        J, JT = c.get("jobs"), c.get("jobs_total")
        expj = {}
        if J and JT:
            for L in kko:
                v = J.get(L)
                if v is not None and v / JT >= 0.01:
                    expj[L] = round((v / JT) / (OJ["by"][L] / OJ["total"]), 1)
        gotj = c.get("lq_jobs")
        if gotj is None or set(gotj) != set(expj) or any(not fin(gotj[k]) or abs(gotj[k] - expj[k]) > 1e-9 for k in expj):
            bad.append(f"{c['name']} 종사자 {gotj} != {expj}"[:120])
        if J and any(J.get(L) is None for L in (gotj or {})):
            bad.append(f"{c['name']} 비공개 대분류에 LQ")
        n_j += len(expj)
    check("G1. 입지계수 다시 계산: 도시 비중 ÷ 공식 전국 비중(지역소득·전국사업체조사), 비중 1% 이상·비공개 제외, 값 일치·유한",
          not bad and n_g > 0 and n_j > 0, f"부가가치 {n_g}칸 · 종사자 {n_j}칸" + (f"; 문제 {len(bad)}건 {bad[:4]}" if bad else ""))

    # G2. 특성 표시: 최대 2개, 업종은 반올림 전 '비중 5% 이상·배수 1.5 이상' 가운데 최대, 지표는 정해진 순서의 첫 조건, 평가하는 말 없음
    BANNED = ["부자", "성장 거점", "쇠퇴", "경제 중심", "강세", "특화", "우수", "낙후", "선도", "중심지"]
    RKN = {"gdp_per_capita": "1인당 GRDP", "export": "수출", "wage": "1인당 총급여"}
    bad, cnt = [], {"ind": 0, "slot2": 0, "small": 0, "none": 0}
    for c in cities:
        T = c.get("tags")
        if not isinstance(T, list) or len(T) > 2:
            bad.append(f"{c['name']} 개수 {T}")
            continue
        b, und = c.get("gdp_by_industry"), set(c.get("gdp_undisclosed") or [])
        cand = []
        if b and b.get("grdp"):
            for k in keys16:
                v = b.get(k)
                if v is None or k in und:
                    continue
                sh = v / b["grdp"]
                lq = sh / (OG["by"][k] / OG["by"]["grdp"])
                if sh >= 0.05 and lq >= 1.5:
                    cand.append((lq, k, sh))
        exp = []
        if cand:
            lq, k, sh = max(cand)
            small = c["population"] < 50000 and lq >= 10
            exp.append(("ind", k, small, c.get("gdp_year") != OG["year"], f"{E['industry_ko'][k]} 비중 ×{round(lq):d}" if lq >= 10 else f"{E['industry_ko'][k]} 비중 ×{lq:.1f}"))
        R = c.get("ranks") or {}
        t2 = next((("rk", k) for k in ("gdp_per_capita", "export", "wage") if R.get(k) is not None and R[k] <= 10), None)
        if t2 is None and c.get("extinction_index") is not None and c["extinction_index"] < 0.2:
            t2 = ("pop", "extinction")
        if t2 is None and c.get("growth_5y") is not None and c["growth_5y"] >= 10.0:
            t2 = ("pop", "growth_5y")
        if t2:
            exp.append(t2)
        got = [(t["t"], t["k"], t.get("small"), t.get("yr_diff"), t.get("txt")) if t["t"] == "ind" else (t["t"], t["k"]) for t in T]
        if got != exp:
            bad.append(f"{c['name']} {got} != {exp}"[:140])
        for t in T:
            if any(w in t.get("txt", "") for w in BANNED):
                bad.append(f"{c['name']} 평가하는 말 '{t['txt']}'")
            if t["t"] == "rk" and t.get("txt") != f"{RKN[t['k']]} {R[t['k']]}위":
                bad.append(f"{c['name']} 순위 문구 {t.get('txt')}")
            if t["t"] == "ind" and t["k"] in und:
                bad.append(f"{c['name']} 비공개 업종 표시")
        cnt["ind"] += any(t["t"] == "ind" for t in T)
        cnt["slot2"] += any(t["t"] != "ind" for t in T)
        cnt["small"] += any(t.get("small") for t in T)
        cnt["none"] += not T
    check("G2. 특성 표시 다시 고르기: 최대 2개, 업종 조건은 반올림 전 값으로 판정, 지표는 정해진 순서의 첫 조건, 문구는 지표 이름과 수치뿐",
          not bad and bool(N.get("tag_rule")) and bool(N.get("lq_rule")), f"{cnt}" + (f"; 문제 {len(bad)}건 {bad[:4]}" if bad else ""))

    # G3. 전국 기준값: 전국 비교는 nation.json 의 그 값과 같고, 도시 중앙값은 다시 낸 중앙값, 순위 분모는 순위가 있는 도시 수
    BM = N.get("benchmarks") or {}
    M = BM.get("metrics") or {}
    bad = []
    GET = {"employment": lambda c: (c.get("employment") or {}).get("rate"), "fiscal": lambda c: c.get("fiscal_independence")}
    for k, m in M.items():
        if m["ref"] == "nation":
            v = N
            for part in m["src"].split(".")[1:]:
                v = (v or {}).get(part)
            if v is None or v != m["v"]:
                bad.append(f"{k} {m['v']} != {m['src']} {v}")
        elif m["ref"] == "city_median":
            vals = [GET[k](c) for c in cities if GET[k](c) is not None]
            if round(statistics.median(vals), 2) != m["v"] or len(vals) != m.get("n"):
                bad.append(f"{k} 중앙값 {m['v']}/{m.get('n')} != {statistics.median(vals)}/{len(vals)}")
        else:
            bad.append(f"{k} 기준 종류 {m['ref']}")
        if m.get("mode") not in ("diff", "ratio") or not m.get("label"):
            bad.append(f"{k} 방식·이름")
    if (M.get("gdp_per_capita") or {}).get("year") != int(N.get("gdp_pop_ref") or 0):
        bad.append(f"1인당 GRDP 기준 연도 {(M.get('gdp_per_capita') or {}).get('year')} != {N.get('gdp_pop_ref')}")
    need = ["growth_5y", "over65", "gdp_per_capita", "wage", "sale_per_m2", "employment", "fiscal", "extinction_index"]
    if PUBLIC:
        need.remove("sale_per_m2")
        skip("G3 의 '아파트 기준값·순위 분모'", "공개판은 아파트 매매·전세가 없다 (X4 가 없음을 확인)")
    for k in need:
        if k not in M:
            bad.append(f"{k} 없음")
    den = BM.get("rank_denominators") or {}
    for k, v in den.items():
        n_ = sum(1 for c in cities if (c.get("ranks") or {}).get(k) is not None)
        if v != n_:
            bad.append(f"분모 {k} {v} != {n_}")
    check("G3. 전국 기준값: 전국 비교값 = nation.json 의 같은 값, 도시 중앙값(고용률·재정자립도) 다시 계산, 순위 분모 = 순위 있는 도시 수",
          not bad and len(M) >= (11 if PUBLIC else 14) and bool(BM.get("rule")) and len(den) >= (8 if PUBLIC else 9),
          f"지표 {len(M)}개, 분모 {den.get('export')}(수출)·{den.get('housing')}(아파트)·{den.get('population')}(인구)" + (f"; 문제 {bad[:5]}" if bad else ""))

    # G4. 닮은 도시 근거: build_econ.py 의 네 축 거리로 다시 계산해 가장 가까운 두 축, 산업 업종·비중, 정해진 차이 규칙
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
    fk = sorted({k for f in feats for k in f})
    import numpy as np  # noqa: E402
    sd = {k: (np.std([f[k] for f in feats if k in f]) or 1) for k in fk}
    idx = {c["id"]: i for i, c in enumerate(cities)}
    bad, n_r = [], 0
    ORD = ["pop", "age", "gdp", "ind"]
    for i, c in enumerate(cities):
        PR = c.get("peer_reasons") or []
        if [r["id"] for r in PR] != c["peers"]:
            bad.append(f"{c['name']} 근거 순서 {[r['id'] for r in PR]} != {c['peers']}")
            continue
        for r in PR:
            n_r += 1
            j = idx[r["id"]]
            fi, fj, o = feats[i], feats[j], cities[j]
            ax = {"pop": ((fi["lp"] - fj["lp"]) / sd["lp"]) ** 2, "age": ((fi["o65"] - fj["o65"]) / sd["o65"]) ** 2}
            if "lg" in fi and "lg" in fj:
                ax["gdp"] = ((fi["lg"] - fj["lg"]) / sd["lg"]) ** 2
            cs = [k for k in fk if k.startswith("s_") and k in fi and k in fj]
            if cs:
                ax["ind"] = sum(((fi[k] - fj[k]) / sd[k]) ** 2 for k in cs) / len(cs)
            same = sorted(ax, key=lambda a_: (ax[a_], ORD.index(a_)))[:2]
            if r["same"] != same:
                bad.append(f"{c['name']}–{o['name']} 축 {r['same']} != {same}")
            if "ind" in same:
                k = max(cs, key=lambda k: min(fi[k], fj[k]))
                if r.get("ind") != k[2:] or r.get("ind_a") != round(fi[k] * 100, 1) or r.get("ind_b") != round(fj[k] * 100, 1):
                    bad.append(f"{c['name']}–{o['name']} 업종 {r.get('ind')} {r.get('ind_a')}/{r.get('ind_b')} != {k[2:]}")
            ha, hb = c.get("housing") or {}, o.get("housing") or {}
            diff = None
            if ha.get("sale_per_m2") is not None and hb.get("sale_per_m2") is not None and (ha.get("trades") or 0) >= 10 and (hb.get("trades") or 0) >= 10:
                q = ha["sale_per_m2"] / hb["sale_per_m2"]
                if max(q, 1 / q) >= 1.35:
                    diff = ["home", round(q, 2)]
            if diff is None and c.get("growth_5y") is not None and o.get("growth_5y") is not None and abs(c["growth_5y"] - o["growth_5y"]) >= 5.0:
                diff = ["growth", round(c["growth_5y"] - o["growth_5y"], 1)]
            wa, wb = (c.get("wage") or {}).get("per_filer"), (o.get("wage") or {}).get("per_filer")
            if diff is None and wa and wb and max(wa / wb, wb / wa) >= 1.15:
                diff = ["wage", round(wa / wb, 2)]
            if r.get("diff") != diff:
                bad.append(f"{c['name']}–{o['name']} 차이 {r.get('diff')} != {diff}")
            if r.get("diff") and r["diff"][0] == "home" and min(ha.get("trades") or 0, hb.get("trades") or 0) < 10:
                bad.append(f"{c['name']}–{o['name']} 거래 10건 미만인데 매매가 차이")
    check("G4. 닮은 도시 근거: 닮은 도시 순서와 같고, 네 축 거리로 다시 낸 가까운 두 축·업종 비중·차이 규칙(매매가는 두 곳 모두 거래 10건 이상)과 일치",
          not bad and n_r == 5 * len(cities) and bool(N.get("peer_rule")), f"근거 {n_r}건" + (f"; 문제 {len(bad)}건 {bad[:4]}" if bad else ""))

    # G5. 추천 시점 6선: 모두 자동(kind=auto), 규칙·수치 문장, 극값 규칙으로 다시 고른 대상과 같음, 렌즈가 있음
    PS = (nation.get("presets") or {}).get("items") or []
    trade = load_json(site("trade.json"))
    lids = {l_["id"] for l_ in lenses["lenses"]}
    by = {p_["id"]: p_ for p_ in PS}
    manf = lambda c: (c["gdp_by_industry"]["manufacturing"] / c["gdp_by_industry"]["grdp"] if c.get("gdp_by_industry") and c["gdp_by_industry"].get("manufacturing") is not None and c["gdp_by_industry"].get("grdp") else None)  # noqa: E731
    want = {
        "top_pop": max(cities, key=lambda c: c["population"])["id"],
        "top_gdppc": max([c for c in cities if c.get("gdp_per_capita") and c["population"] >= 100000], key=lambda c: c["gdp_per_capita"])["id"],
        "top_mfg": max([c for c in cities if manf(c) is not None], key=manf)["id"],
        "min_ext": min([c for c in cities if c.get("extinction_index") is not None], key=lambda c: c["extinction_index"])["id"],
        "top_paddy": max([c for c in cities if (c.get("farm") or {}).get("paddy_ha") is not None], key=lambda c: c["farm"]["paddy_ha"])["id"],
    }
    seg = max(trade["routes"]["segments"], key=lambda g_: g_["total"])
    bad = []
    if len(PS) != 6 or any(p_.get("kind") != "auto" or not p_.get("rule") or not p_.get("metric") for p_ in PS):
        bad.append("6개·자동·규칙·수치")
    for k, cid in want.items():
        if k not in by or by[k].get("city") != cid:
            bad.append(f"{k} {by.get(k, {}).get('city')} != {cid}")
    if "top_route" not in by or by["top_route"].get("route") != f"{seg['a']}-{seg['b']}":
        bad.append("top_route")
    bad += [f"{p_['id']} 렌즈 {p_['lens']}" for p_ in PS if p_.get("lens") and p_["lens"] not in lids]
    check("G5. 추천 시점 6선: 모두 자동 선정(kind=auto)·규칙·수치 문장, 극값 규칙으로 다시 고른 도시·구간과 같음, 렌즈가 렌즈 목록에 있음",
          not bad, "; ".join(f"{p_['id']} {p_['title']}" for p_ in PS) + (f"; 문제 {bad}" if bad else ""))

    # G6. 배치 규칙 (wonders.json zoom): 우선군 ①원전 ②공항·무역항, 예산 수치, 규칙 문장의 공항·무역항 수 = 전국 단계 항목 수
    W_ = load_json(site("wonders.json"))
    items = W_["items"] + load_json(site("resources.json"))["items"] + load_json(site("infrastructure.json"))["items"]
    Z = W_["zoom"]
    dp, bg = Z.get("draw_priority") or {}, Z.get("budget") or {}
    na = sum(1 for it in items if it["kind"] == "airport" and it.get("tier") == 0)
    nt = sum(1 for it in items if it["kind"] == "trade_port" and it.get("tier") == 0)
    ok6 = (dp.get("first") == ["nuclear"] and dp.get("second") == ["airport", "trade_port"]
           and all(isinstance(bg.get(k), int) and bg[k] > 0 for k in ("flags_desktop", "flags_mobile", "icons_desktop", "icons_mobile", "mobile_vw"))
           and bg.get("z_max") == 2.0 and f"공항 {na}곳" in dp.get("rule", "") and f"무역항 {nt}곳" in dp.get("rule", "")
           and f"데스크톱 {bg.get('icons_desktop')}개" in dp.get("rule", ""))
    check("G6. 배치 규칙: 우선군 ①원전 ②공항·무역항, 배치 예산 수치, 규칙 문장의 공항·무역항 수와 예산이 자료와 같음", ok6,
          f"전국 단계 공항 {na} · 무역항 {nt}, 예산 {bg}")

    # G7. 도시 머리의 짧은 범위 문구 (scope_label): scope 가 있는 도시는 모두 있고, 자치구 수와 따로 둔 군 이름이 같다
    bad = []
    for c in cities:
        if not c.get("scope"):
            continue
        sl = c.get("scope_label") or ""
        n_ = re.search(r"자치구 (\d+)곳", c["scope"])
        if not sl or (n_ and f"{n_.group(1)}곳" not in sl):
            bad.append(f"{c['name']} '{sl}'")
        m_ = re.search(r"· (.+)은 따로 도시", c["scope"])
        if m_ and any(g_ not in sl for g_ in m_.group(1).split("·")):
            bad.append(f"{c['name']} 군 이름 '{sl}'")
    check("G7. 도시 머리 짧은 범위 문구: 범위 문구가 있는 도시는 모두 있고 자치구 수·따로 둔 군 이름이 같음", not bad,
          "; ".join(f"{c['name']}: {c.get('scope_label')}" for c in cities if c.get("scope")) + (f"; 문제 {bad}" if bad else ""))


def validate_sources_page():
    """출처 쪽(site/sources/)과 NOTICE.md: 출처·표기 기록의 필수 칸, 실린 글꼴의 이용허락, 계산한 층의 규칙 문장, 제한 분류, NOTICE.md 동기, 출처 쪽이 읽는 필드."""
    import json as _json
    from lib import notice as NT
    from lib.common import ROOT
    SJ = load_json(site("sources.json"))
    S, C, D = SJ.get("sources") or [], SJ.get("credits") or [], SJ.get("derived") or []
    keys_ = {s.get("key") for s in S}

    # S1. 출처·표기 기록마다 기관·제목·이용허락(또는 '미확인')·쓴 곳
    bad = []
    for s in S + C:
        for k_ in ("publisher", "title", "license", "used_in"):
            if not str(s.get(k_) or "").strip():
                bad.append(f"{s.get('key')} {k_} 없음")
    unk = sum(1 for s in S if s.get("license") == "미확인")
    check("S1. 출처·표기 기록마다 기관·제목·이용허락(확인 못 하면 '미확인')·쓴 곳이 있음", not bad and S and C,
          f"자료 출처 {len(S)}건(미확인 {unk}), 표기 {len(C)}건(글꼴 {sum(1 for c in C if c.get('kind') == 'font')})" + (f"; 문제 {bad[:8]}" if bad else ""))

    # S2. 사이트에 실린 글꼴 파일마다 이용허락 기록: 파일 sha256·바이트, 이용허락 파일이 있고 OFL 1.1 이며 sha256 이 같음
    bad = []
    rec = {}
    for c in C:
        if c.get("kind") != "font":
            continue
        for fr in c.get("files") or []:
            rec[fr.get("file")] = (c, fr)
        lf = os.path.join(ROOT, *(c.get("license_file") or "-").split("/"))
        if not os.path.isfile(lf):
            bad.append(f"{c.get('key')} 이용허락 파일 없음 {c.get('license_file')}")
            continue
        o = NT.parse_ofl(lf)
        if not o["license"] or o["license"] != c.get("license"):
            bad.append(f"{c.get('key')} 이용허락 {c.get('license')!r} ≠ 파일 {o['license']!r}")
        if NT.sha256_file(lf)[0] != c.get("license_sha256"):
            bad.append(f"{c.get('key')} 이용허락 파일 sha256 다름")
        if (o["reserved_font_name"] or None) != (c.get("reserved_font_name") or None):
            bad.append(f"{c.get('key')} 예약 글꼴 이름 다름")
    shipped = NT.shipped_font_files()
    for p_ in shipped:
        if p_ not in rec:
            bad.append(f"{p_} 이용허락 기록 없음")
            continue
        hh, bb = NT.sha256_file(os.path.join(ROOT, *p_.split("/")))
        if hh != rec[p_][1].get("sha256") or bb != rec[p_][1].get("bytes"):
            bad.append(f"{p_} sha256·바이트 다름")
    check("S2. 사이트에 실린 글꼴 파일마다 이용허락 기록 (파일 sha256, 이용허락 파일 OFL 1.1·sha256·예약 글꼴 이름이 기록과 같음)", not bad and shipped,
          f"글꼴 파일 {len(shipped)}개: {', '.join(os.path.basename(x) for x in shipped)}" + (f"; 문제 {bad[:8]}" if bad else ""))

    # S3. 계산한 층: 규칙 문장 = 그 자리(site/data JSON)의 문장, 입력 출처 key 가 모두 있음
    bad = []
    for d in D:
        try:
            texts = [NT.resolve_rule(sp, lambda fn: load_json(site(fn)))[0] for sp in d.get("rule_from") or []]
            parts = NT.resolve_rule(d["parts_from"], lambda fn: load_json(site(fn))) if d.get("parts_from") else (None, None)
            want = " ".join(texts) if texts else parts[0]
            if not want or d.get("rule") != want:
                bad.append(f"{d.get('key')} 규칙 문장이 자리의 문장과 다름")
            if d.get("parts_from") and d.get("parts") != parts[1]:
                bad.append(f"{d.get('key')} 조각 목록이 자리와 다름")
        except (KeyError, StopIteration, ValueError, TypeError) as e:
            bad.append(f"{d.get('key')} 규칙 자리를 찾지 못함 ({type(e).__name__})")
        miss = [k for k in d.get("inputs") or [] if k not in keys_]
        if miss:
            bad.append(f"{d.get('key')} 없는 입력 key {miss[:3]}")
        if not d.get("inputs") and not d.get("inputs_note"):
            bad.append(f"{d.get('key')} 입력 없음")
    rid = next((d for d in D if d.get("key") == "derived-ridges"), None)
    if not rid or not {"terrain_srtm30plus", "wamis-rivlinen"} <= set(rid.get("inputs") or []):
        bad.append("산줄기 기록(derived-ridges)이 없거나 입력에 표고·하천이 없음")
    check("S3. 계산한 층: 규칙 문장이 site/data JSON 의 그 자리 문장과 같고, 입력 출처 key 가 모두 있음 (산줄기 = 표고 + 하천)", not bad and D,
          f"계산한 층 {len(D)}개: {', '.join(d.get('title', '') for d in D)}" + (f"; 문제 {bad[:8]}" if bad else ""))

    # S4. 제한 분류: 이용허락 원문·메모로 다시 분류한 것 = 기록, 제한 자료마다 영향 받는 곳 기록, API 약관 제한 자료 없음
    bad = []
    for s in S:
        want = NT.restriction_kinds(s)
        if (s.get("restriction_kinds") or []) != want:
            bad.append(f"{s.get('key')} 분류 {s.get('restriction_kinds')} ≠ 다시 분류 {want}")
        if want and not isinstance(s.get("affects"), dict):
            bad.append(f"{s.get('key')} 영향 받는 곳(affects) 없음")
    # 토지피복은 두 판 모두 공공누리 제1유형 도엽 통계라 API 약관(api_terms) 분류가 붙은 자료가 없어야 한다
    api = [s.get("key") for s in S if "api_terms" in (s.get("restriction_kinds") or [])]
    if api:
        bad.append(f"API 약관 분류가 남은 자료 {api}")
    codes = [k.get("code") for k in SJ.get("restriction_kinds") or []]
    if codes != [c_ for c_, *_ in NT.RESTRICTION_KINDS]:
        bad.append("분류 이름표(restriction_kinds) 다름")
    nr = sum(1 for s in S if s.get("restriction_kinds"))
    by_kind = ", ".join(f"{NT.KIND_NAME[c_]} {sum(1 for s in S if c_ in (s.get('restriction_kinds') or []))}" for c_ in NT.KIND_NAME)
    check("S4. 이용조건 분류: 원문·메모로 다시 분류한 결과 = 기록, 제한 자료마다 쓰는 곳 기록, API 약관 제한 자료 없음(토지피복 WMS 를 쓰지 않음)", not bad,
          f"조건이 있는 자료 {nr}건 ({by_kind})" + (f"; 문제 {bad[:6]}" if bad else ""))

    # S5. NOTICE.md = sources.json 으로 다시 만든 글
    try:
        cur = NT.read_notice()
    except OSError:
        cur = None
    want = NT.render_notice(SJ)
    diff = ""
    if cur is not None and cur != want:
        a_, b_ = cur.splitlines(), want.splitlines()
        i_ = next((i for i, (x, y) in enumerate(zip(a_, b_)) if x != y), min(len(a_), len(b_)))
        diff = f"; {i_ + 1}째 줄부터 다름 (파일 {len(a_)}줄, 다시 만든 글 {len(b_)}줄)"
    check("S5. NOTICE.md 가 sources.json 과 맞음 (build_notice.py 로 다시 만든 글과 같음)", cur == want,
          ("NOTICE.md 없음" if cur is None else f"{len(want.encode('utf-8')):,} 바이트") + diff)

    # S6. 출처 쪽이 읽는 필드: site/sources/js/sources.js 의 FIELDS 가 자료에 있고, f(기록, '이름') 으로 읽는 이름이 FIELDS 에 있음, 두 판에서 오가는 링크
    bad = []
    js_p = os.path.join(ROOT, "site", "sources", "js", "sources.js")
    js = open(js_p, encoding="utf-8").read() if os.path.isfile(js_p) else ""
    m_ = re.search(r"/\*FIELDS\*/(.*?)/\*END\*/", js, re.S)
    try:
        FL = _json.loads(m_.group(1)) if m_ else None
    except ValueError:
        FL = None
    if not FL:
        bad.append("sources.js 에 FIELDS 블록이 없거나 읽지 못함")
        FL = {}
    ents = {"top": [SJ], "summary": [SJ.get("summary")] if SJ.get("summary") else [],
            "counts": [SJ["summary"]["counts"]] if isinstance((SJ.get("summary") or {}).get("counts"), dict) else [],"cite": [SJ.get("cite")] if SJ.get("cite") else [],
            "restriction_kind": SJ.get("restriction_kinds") or [], "attribution": [SJ.get("attribution")] if SJ.get("attribution") else [],
            "source": S, "affects": [s["affects"] for s in S if isinstance(s.get("affects"), dict)],
            "file": [x for s in S + C for x in s.get("files") or []], "derived": D, "part": [p_ for d in D for p_ in d.get("parts") or []], "credit": C,
            "profile": [SJ["profile"]] if isinstance(SJ.get("profile"), dict) else [], "excluded": (SJ.get("profile") or {}).get("excluded") or [],
            "check_needed": (SJ.get("profile") or {}).get("check_needed") or [], "consent_kept": (SJ.get("profile") or {}).get("consent_kept") or [],
            "notice": [s["required_notice"] for s in S if isinstance(s.get("required_notice"), dict)], "shipped": [r for s in S for r in s.get("shipped") or []]}
    # 한 판에만 있는 선택 필드 (전체판의 WMS 토지피복 경고 restriction) — 다른 판에 없어도 문제로 세지 않는다
    # restriction(이용조건 경고 글)은 지금 어느 출처에도 없다 — 토지피복 WMS 경고가 없어진 뒤로. 출처 쪽은 있으면 그린다
    PROFILE_ONLY = {"source": {"restriction"}}
    declared = set()
    for ent, spec in FL.items():
        rows_ = ents.get(ent)
        if rows_ is None:
            bad.append(f"FIELDS 의 '{ent}' 가 무엇인지 모름")
            continue
        declared |= set(spec.get("required", [])) | set(spec.get("optional", []))
        if not rows_ and spec.get("required"):
            bad.append(f"'{ent}' 기록이 하나도 없음")
        for k_ in spec.get("required", []):
            miss = [str(r.get("key", "?"))[:24] for r in rows_ if not isinstance(r, dict) or k_ not in r]
            if miss:
                bad.append(f"{ent}.{k_} 없는 기록 {len(miss)}건 ({miss[:3]})")
        for k_ in spec.get("optional", []):
            if rows_ and not any(isinstance(r, dict) and k_ in r for r in rows_):
                if k_ in PROFILE_ONLY.get(ent, ()):
                    note(f"S6 {ent}.{k_}", f"이 판({PROFILE})의 기록에는 없는 필드 (다른 판에만 있음)")
                    continue
                bad.append(f"{ent}.{k_} 가 어느 기록에도 없음")
    # f(f(x, 'a'), 'b') 처럼 겹친 호출도 모두 잡도록 앞보기로 찾는다
    used = {m2 for _, m2 in re.findall(r"(?=\bf\(\s*([^,()]+(?:\([^()]*\))?)\s*,\s*'([a-z_0-9]+)'\s*\))", js)}
    und = sorted(used - declared)
    if und:
        bad.append(f"FIELDS 에 없는 필드를 읽음 {und}")
    links = {"site/sources/index.html": ['href="../"', 'href="../yeojido/"', 'js/sources.js'],
             "site/js/ui/almanac.js": ['href="sources/"'], "site/yeojido/js/ui/almanac.js": ["'../sources/'"], "site/yeojido/js/main.js": ["'../sources/'"]}
    for fp, needles in links.items():
        p_ = os.path.join(ROOT, *fp.split("/"))
        txt = open(p_, encoding="utf-8").read() if os.path.isfile(p_) else ""
        for nd in needles:
            if nd not in txt:
                bad.append(f"{fp} 에 링크 {nd} 없음")
    if "'../data/sources.json'" not in js:
        bad.append("sources.js 가 ../data/sources.json 을 읽지 않음")
    check("S6. 출처 쪽이 읽는 필드(sources.js FIELDS)가 sources.json 에 있고 읽는 이름이 모두 선언됨, 두 판 ↔ 출처 쪽 링크", not bad,
          f"선언한 필드 {len(declared)}개, 코드에서 읽는 필드 {len(used)}개" + (f"; 문제 {bad[:8]}" if bad else ""))



def _walk_strings(o, path=""):
    """JSON 안의 모든 (경로, 문자열)."""
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk_strings(v, f"{path}.{k}")
    elif isinstance(o, list):
        for k, v in enumerate(o):
            yield from _walk_strings(v, f"{path}[{k}]")
    elif isinstance(o, str):
        yield path, o


def path_exists(doc, path):
    """'a.b', '[*].x', 'lenses[id=assistance]', 'items[kind=mine]' 꼴 경로가 doc 에 있는가 (목록은 하나라도 있으면)."""
    cur = [doc]
    for part in re.findall(r"[^.\[\]]+|\[[^\]]*\]", path):
        nxt = []
        for c in cur:
            if part.startswith("["):
                sel = part[1:-1]
                if not isinstance(c, list):
                    continue
                if sel == "*":
                    nxt += c
                else:
                    k, v = sel.split("=", 1)
                    nxt += [x for x in c if isinstance(x, dict) and str(x.get(k)) == v]
            elif isinstance(c, dict) and part in c:
                nxt.append(c[part])
        cur = nxt
        if not cur:
            return False
    return True


def validate_profile(world, cities, states, nation, lenses):
    """빌드 판(profile): 기록이 서로 맞는지, 공개판이 빼야 할 것을 정말 뺐는지 (lib/profile.py EXCLUDE 와 같은 표로 다시 확인)."""
    import numpy as np
    SJ = load_json(site("sources.json"))
    P = SJ.get("profile") or {}
    S = SJ.get("sources") or []
    keys = {x["key"] for x in S}
    files = {fn: load_json(site(fn)) for fn in ("world.json", "cities.json", "states.json", "nation.json", "lenses.json", "sources.json",
                                                 "wonders.json", "resources.json", "infrastructure.json", "trade.json", "frontier.json", "ridges.json")}
    import fnmatch as _fn
    # X1. 판 기록이 서로 맞음
    bad = []
    wp = world.get("build_profile", "full")
    if P.get("profile") not in PRF.PROFILES:
        bad.append(f"sources.json profile.profile = {P.get('profile')!r}")
    if wp != PROFILE:
        bad.append(f"world.json build_profile {wp} ≠ {PROFILE}")
    if P.get("profile") != wp:
        bad.append(f"sources.json profile {P.get('profile')} ≠ world.json build_profile {wp}")
    if ("removed" in lenses) != PUBLIC:
        bad.append("lenses.json removed 가 공개판에만 있어야 함")
    if [e["id"] for e in P.get("excluded") or []] != [e["id"] for e in PRF.EXCLUDE]:
        bad.append("profile.excluded 묶음이 lib/profile.py EXCLUDE 와 다름")
    for e in P.get("excluded") or []:
        if not e.get("what") or not e.get("why") or not e.get("sources"):
            bad.append(f"profile.excluded {e.get('id')}: 무엇·까닭·출처 key 가 비었음")
    nt = open(os.path.join(ROOT, "NOTICE.md"), encoding="utf-8").read() if os.path.exists(os.path.join(ROOT, "NOTICE.md")) else ""
    if f"## 이 판: {P.get('name')} (`{P.get('profile')}`)" not in nt:
        bad.append("NOTICE.md 에 판 머리가 없음")
    check("X1. 판 기록: sources.json profile = world.json build_profile = 렌즈 removed, 뺀 묶음 = lib/profile.py EXCLUDE (무엇·까닭·출처), NOTICE.md 머리",
          not bad, f"판 {PROFILE} ({P.get('name')}), 묶음 {len(P.get('excluded') or [])}" + (f"; 문제 {bad}" if bad else ""))
    # X3. 두 판 공용 토지피복·인천공항 위치: 칸 피복은 도엽 통계(me)·ESA 보완뿐, 숲 종류 있음, 쓰지 않는 출처 key(WMS·범례 쪽·AIP)가 사이트 JSON 어디에도 없음,
    #     다른 판의 사본이 있으면 피복 기록이 같음 (토지피복은 판 차이가 아니다)
    cs = world["cover_src"]
    bad = []
    if cs["kinds"] != ["me", "esa"] or "도엽 통계" not in cs["names"][0]:
        bad.append(f"cover_src.kinds/names {cs['kinds']} {cs['names'][:1]}")
    if not world.get("forest_kind") or not world["forest_kind"].get("cells"):
        bad.append("forest_kind 없음")
    for k in ("broadleaf", "conifer", "mixed"):
        if k not in world["cover_share"].get("keys", []):
            bad.append(f"cover_share.{k} 없음")
    if "profile" in (world.get("cover_meta") or {}):
        bad.append("cover_meta.profile 이 있음 (판마다 다른 피복이라는 뜻)")
    hits = []
    for fn, J in files.items():
        for path, v in _walk_strings(J):
            if any(_fn.fnmatchcase(v, p_) for p_ in PRF.NEVER_KEYS) or re.search(r"(?<![\w-])(incheon-aip|landcover-me-wms-lv2-2025y|landcover-me-intro-land-html)(?![\w-])", v):
                hits.append(f"{fn}{path}={v[:60]}")
    if hits:
        bad.append(f"쓰지 않는 출처 key {hits[:4]}")
    other = os.path.join(ROOT, "data", "build", "site_data_full", "world.json") if PUBLIC else None
    same_txt = "다른 판 사본 없음 (전체판 검증은 공개판 사본을 두지 않는다)"
    if other and os.path.exists(other):
        W2 = load_json(other)
        diff = [k for k in ("cover", "cover_share", "cover_src", "crop_kind", "forest_kind", "cover_meta") if W2.get(k) != world.get(k)]
        diff += [f"tables.cover" for _ in [0] if W2["tables"].get("cover") != world["tables"].get("cover")]
        if diff:
            bad.append(f"전체판 사본과 피복 기록이 다름: {diff}")
        I2 = load_json(os.path.join(ROOT, "data", "build", "site_data_full", "infrastructure.json"))
        a1 = [i for i in files["infrastructure.json"]["items"] if i["kind"] == "airport"]
        a2 = [i for i in I2["items"] if i["kind"] == "airport"]
        if [(i["name"], i["lon"], i["lat"], i["cell"]) for i in a1] != [(i["name"], i["lon"], i["lat"], i["cell"]) for i in a2]:
            bad.append("전체판 사본과 공항 위치가 다름")
        same_txt = "전체판 사본(data/build/site_data_full)과 피복 기록·공항 위치가 " + ("같음" if not diff else "다름")
    n_src = {}
    for v in cs["src"]:
        n_src[cs["kinds"][v] if v is not None else None] = n_src.get(cs["kinds"][v] if v is not None else None, 0) + 1
    check("X3. 두 판 공용 토지피복·인천공항: 칸 피복 = 도엽 통계(me) + ESA 보완, 숲 종류 있음, 쓰지 않는 출처(WMS 그림·범례 쪽·AIP) key 가 사이트 JSON 어디에도 없음, 다른 판 사본과 같음",
          not bad, f"칸 출처 {n_src}, 숲 종류 칸 {len(world['forest_kind']['cells']) if world.get('forest_kind') else 0}; {same_txt}" + (f"; 문제 {bad}" if bad else ""))
    if not PUBLIC:
        # 전체판: 공개판이 빼는 자료가 들어 있음을 기록이 밝히는지 (공개 배포 금지)
        ok = "내부 열람용" in (P.get("statement") or "") and all(e.get("sources") for e in P.get("excluded") or [])
        check("X2. 전체판: 판 기록이 '내부 열람용'이고 공개판이 빼는 묶음마다 이 판에 든 출처를 적음", ok,
              ", ".join(f"{e['id']} {len(e['sources'])}건" for e in P.get("excluded") or []))
        for nm, why in (("X4. 공개판 주택", "전체판은 아파트 매매·전세를 싣는다"),
                        ("X5. 공개판 광산·한우", "전체판은 두 자료를 싣는다"),
                        ("X6. 공개판: 빼는 출처 key 가 사이트 JSON 어디에도 없음", "전체판에는 있다")):
            skip(nm, why)
    else:
        # X4. 주택
        bad = []
        for nm_, rows_ in (("cities", cities), ("states", states)):
            n_ = sum(1 for c in rows_ if "housing" in c)
            if n_:
                bad.append(f"{nm_}.housing {n_}곳")
        if "housing" in nation["nation"]:
            bad.append("nation.housing")
        if any("housing" in (c.get("ranks") or {}) for c in cities):
            bad.append("cities.ranks.housing")
        E = nation.get("econ") or {}
        bad += [f"nation.econ.{k}" for k in ("housing_note", "housing_counts") if k in E]
        BM = (nation["nation"].get("benchmarks") or {})
        bad += [f"benchmarks.metrics.{k}" for k in ("sale_per_m2", "sale_median", "jeonse_median") if k in (BM.get("metrics") or {})]
        if "housing" in (BM.get("rank_denominators") or {}):
            bad.append("rank_denominators.housing")
        if any((r.get("diff") or [None])[0] == "home" for c in cities for r in c.get("peer_reasons") or []):
            bad.append("닮은 도시 차이에 'home'")
        lids = {l_["id"] for l_ in lenses["lenses"]} | {it["id"] for it in (lenses.get("retired_values") or {}).get("items", [])} | set(lenses.get("retired") or {})
        bad += [f"렌즈 {k}" for k in ("home", "jeonse") if k in lids]
        if any(x.startswith("molit-apartment-") for x in keys):
            bad.append("sources.json 에 molit-apartment-*")
        if "아파트" in (nation["nation"].get("peer_rule") or "").replace("아파트 매매가가 없어", ""):
            bad.append("peer_rule 이 아파트 차이를 적음")
        check("X4. 공개판 주택: 아파트 매매·전세 값·렌즈·순위·전국 기준·닮은 도시 차이·출처가 없음 (다른 값으로 메우지 않음)", not bad,
              "도시·시도·전국 housing 0, 렌즈 home·jeonse 없음" + (f"; 문제 {bad}" if bad else ""))
        # X5. 광산·한우·인천공항 좌표
        bad = []
        R = files["resources.json"]
        for k in ("mine", "cattle"):
            n_ = sum(1 for it in R["items"] if it["kind"] == k)
            if n_ or k in R["kinds"]:
                bad.append(f"resources {k}: 항목 {n_}, 종류 {'있음' if k in R['kinds'] else '없음'}")
        if "mines_5d" in R:
            bad.append("resources.mines_5d")
        if "cattle" in R.get("farm", {}):
            bad.append("resources.farm.cattle")
        zr = " ".join(files["wonders.json"]["zoom"]["rules"])
        if "한우" in zr or "광산" in zr:
            bad.append("배율 규칙에 한우·광산")
        INF = files["infrastructure.json"]
        check("X5. 공개판 광산·한우: 항목·종류·패널 값·배율 규칙에 없음", not bad,
              "광산·한우 항목 0" + (f"; 문제 {bad}" if bad else ""))
        # X6. 빼는 출처 key 가 어느 사이트 JSON 에도 없음 (출처 기록·출처 줄·층 항목 source·종류 source 모두)
        pats = [p_ for e in PRF.EXCLUDE for p_ in e["sources"]]
        # 뺀 출처의 실제 key (profile 기록) — 값 전체가 key 이거나 글 안에 key 가 단어로 들어 있으면 찾는다
        ex_keys = sorted({x["key"] for e in P.get("excluded") or [] for x in e.get("sources") or []}, key=len, reverse=True)
        kre = re.compile(r"(?<![\w-])(" + "|".join(re.escape(k) for k in ex_keys) + r")(?![\w-])") if ex_keys else None
        hits = []
        for fn, J in files.items():
            for path, v in _walk_strings(J):
                if fn == "sources.json" and path.startswith(".profile"):
                    continue   # 뺀 것의 목록 자체
                if any(_fn.fnmatchcase(v, p_) for p_ in pats) or (kre and kre.search(v)):
                    hits.append(f"{fn}{path}={v[:80]}")
        check("X6. 공개판: 빼는 출처 key 가 사이트 JSON 어디에도 없음 (profile 의 뺀 목록만 예외)", not hits,
              f"무늬 {len(pats)}개, 찾은 자리 {len(hits)}" + (f": {hits[:6]}" if hits else ""))
    # X7. 변경금지 통계 목록(check_needed) = 남긴 변경금지 자료, 그 문장이 '원 통계를 바꾸지 않는다'를 밝힘, 상업 허락만 걸린 자료 기록
    nd = sorted(x["key"] for x in S if "noderivs" in (x.get("restriction_kinds") or []))
    got = sorted(x["key"] for x in P.get("check_needed") or [])
    bad = []
    if nd != got:
        bad.append(f"변경금지 {nd} ≠ 변경금지 통계 목록 {got}")
    if "원 통계를 바꾸지 않는다" not in (P.get("check_rule") or "") or "조건 확인 필요" in (P.get("check_rule") or ""):
        bad.append("변경금지 통계 문장이 '원 통계를 바꾸지 않는다'를 밝히지 않음")
    for x in P.get("check_needed") or []:
        if not x.get("where"):
            bad.append(f"{x['key']}: 영향 받는 곳이 없음")
    cons = sorted(x["key"] for x in S if "consent" in (x.get("restriction_kinds") or []))
    kept = sorted(x["key"] for x in P.get("consent_kept") or [])
    if PUBLIC and cons != kept:
        bad.append(f"사전 허락 분류 {cons} ≠ 남긴 까닭 기록 {kept}")
    if PUBLIC and any(k not in PRF.KEEP_CONSENT for k in cons):
        bad.append(f"사전 허락 자료가 공개판에 남았는데 까닭(KEEP_CONSENT)이 없음: {[k for k in cons if k not in PRF.KEEP_CONSENT]}")
    check("X7. 변경금지 통계 = 남긴 변경금지 자료(영향 받는 곳 포함, '원 통계를 바꾸지 않는다' 문장), 공개판에 남은 사전 허락 자료는 상업 이용에만 걸린 것(까닭 기록)", not bad,
          f"변경금지 통계 {got}, 상업 허락만 {kept}" + (f"; 문제 {bad}" if bad else ""))
    # X8. 뺀 렌즈의 옛 링크
    if PUBLIC:
        RM = lenses.get("removed") or {}
        lids = {l_["id"] for l_ in lenses["lenses"]}
        bad = [k for k, v in RM.items() if k in lids or (v.get("near") is not None and v["near"] not in lids) or not v.get("reason")]
        want = {"home", "jeonse"}
        if set(RM) != want:
            bad.append(f"removed {sorted(RM)} ≠ {sorted(want)}")
        check("X8. 공개판 뺀 렌즈: removed 가 아파트 2종이고, 막대에 없고, 옛 링크가 갈 렌즈가 있거나(near) 지형, 까닭 문장", not bad,
              ", ".join(f"{k}→{v.get('near') or '지형'}" for k, v in RM.items()) + (f"; 문제 {bad}" if bad else ""))
    else:
        skip("X8. 공개판 뺀 렌즈", "전체판은 렌즈를 빼지 않는다")
    # S7. 조건부·미확인·대체·수작업 출처마다 실린 자리, 그 자리가 사이트 JSON 에 있음 (감사 05)
    bad, n_ = [], 0
    for x in S:
        cond = bool(x.get("restriction_kinds")) or (x.get("license") or "미확인") == "미확인" or x.get("alternative") or x.get("manual")
        if not cond:
            continue
        n_ += 1
        sh = x.get("shipped") or []
        if not sh:
            bad.append(f"{x['key']}: 실린 곳 없음")
        for r in sh:
            if r.get("file") not in files or not path_exists(files[r["file"]], r.get("path") or ""):
                bad.append(f"{x['key']}: {r.get('file')} {r.get('path')} 없음")
    check("S7. 조건부·미확인·대체·수작업 출처마다 실린 자리(사이트 JSON 필드)가 있고 그 필드가 실제로 있음 (감사 05)", not bad,
          f"출처 {n_}건" + (f"; 문제 {bad[:6]}" if bad else ""))
    # S8. SRTM30+ 지정 고지 원문·상업 이용 조건, OSM ODbL 안내 (감사 04·05)
    bad = []
    srt = next((x for x in S if x["key"] == "terrain_srtm30plus"), None)
    rn = (srt or {}).get("required_notice") or {}
    paras = rn.get("paragraphs") or []
    if len(paras) != 5 or not srt.get("commercial_use"):
        bad.append(f"SRTM30+ 고지 문단 {len(paras)}개, 상업 이용 조건 {'있음' if (srt or {}).get('commercial_use') else '없음'}")
    for ptxt in paras:
        if ptxt not in nt:
            bad.append(f"NOTICE.md 에 고지 문단 없음: {ptxt[:40]}…")
    rawp = os.path.join(ROOT, "data", "raw", "layers4", "terrain.html")
    if os.path.exists(rawp):
        import hashlib as _h
        import html as _html
        b_ = open(rawp, "rb").read()
        m_ = re.search(r"<td>license</td>\s*<td>String</td>\s*<td>(.*?)</td>", b_.decode("utf-8"), re.S)
        flat = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<br\s*/?>", " ", m_.group(1)))).strip() if m_ else ""
        if flat != re.sub(r"\s+", " ", " ".join(paras)).strip():
            bad.append("고지 문단이 보관한 제공자 쪽 원문과 다름")
        if rn.get("from_sha256") != _h.sha256(b_).hexdigest():
            bad.append("보관본 sha256 이 다름")
        src_txt = "보관한 제공자 쪽과 대조"
    else:
        src_txt = "원자료(data/raw) 없음 — 보관본 대조는 건너뜀"
        note("S8 보관본 대조", src_txt)
    osm = next((x for x in S if x["key"] == "osm-water"), None)
    if not osm or "ODbL" not in (osm.get("odbl") or "") or (osm.get("odbl") or "") not in nt:
        bad.append("OSM 호수의 ODbL 안내가 sources.json·NOTICE.md 에 없음")
    check("S8. SRTM30+ 저작권 고지·지정 문단 원문과 상업 이용 조건, OSM 파생 자료의 ODbL 안내가 sources.json 과 NOTICE.md 에 있음 (감사 04·05)", not bad,
          f"고지 {len(paras)}문단 · {src_txt}" + (f"; 문제 {bad}" if bad else ""))

if __name__ == "__main__":
    sys.exit(main())

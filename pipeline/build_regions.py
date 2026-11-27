"""지역 집계: 시군구 -> 도시(규칙), 시도, 전국의 인구 지표 -> site/data/{cities,states,nation}.json

도시 정의 결과는 data/build/cities_check.csv 로 내보낸다.
"""
import csv
import math
import re
import sys

import numpy as np

from lib import crosswalk, jumin, popstats
from lib.common import build, load_json, rnd, save_json, site

# 시도청 소재지는 5b 부터 행정안전부 공표본의 청사 주소(data/build/layers/municipal_offices.csv)에서 읽는다 (read_offices).
# 수도 표시는 수작업 값이다 (청사 표에 '수도' 구분이 없음).
NATIONAL_CAPITAL = "서울"
OFFICES = "municipal_offices.csv"
SPECIAL_OFFICES = "special_city_offices.csv"
SPECIAL_ACT = "「전남광주통합특별시 설치를 위한 특별법」 제7조제3항"
# 특례시 (지방자치법 제198조의 인구 100만 이상 대도시. 지정 현황 수작업 표)
SPECIAL_CITIES = {("41", "수원시"), ("41", "고양시"), ("41", "용인시"), ("41", "화성시"), ("48", "창원시")}
GWANGJU_RANGE = (12200, 12399)  # 전남광주통합특별시 안의 옛 광주광역시 자치구 코드 범위 (12210–12330)


def log(*a):
    print("[regions]", *a, flush=True)


def define_cities(counties, states):
    """시군구 -> 도시. 규칙은 명세 §4.1."""
    sido_name = {s["code"]: s["name"] for s in states}
    short = {s["code"]: s["short"] for s in states}
    groups = {}  # key -> dict
    how = {}
    for c in counties:
        code, nm, sd = c["code"], c["name"], c["sido"]
        m = re.fullmatch(r"(.+시) (.+구)", nm)
        if m:  # 규칙 2: 일반구 -> 앞의 시
            key = (sd, m.group(1))
            name, full, kind, rule = m.group(1), f"{sido_name[sd]} {m.group(1)}", "시", "2 일반구를 시로"
        elif nm.endswith("구"):
            if sd == "12":
                if not (GWANGJU_RANGE[0] <= int(code) <= GWANGJU_RANGE[1]):
                    raise ValueError(f"전남광주통합특별시의 자치구가 광주 코드 범위 밖: {code} {nm}")
                key = (sd, "광주")
                name, full, kind, rule = "광주", f"{sido_name[sd]} 광주 (옛 광주광역시 자치구)", "광역시", "3 광주 자치구(코드 범위)"
            else:  # 규칙 1: 특별·광역시 자치구
                key = (sd, short[sd])
                kind = "특별시" if sido_name[sd].endswith("특별시") else "광역시"
                name, full, rule = short[sd], sido_name[sd], "1 자치구를 특별·광역시로"
        elif sd == "36":  # 규칙 4: 세종
            key = (sd, "세종")
            name, full, kind, rule = "세종", sido_name[sd], "특별자치시", "4 세종"
        else:  # 규칙 4·5: 제주시·서귀포시, 나머지 시·군, 광역시 안의 군
            key = (sd, nm)
            kind = "군" if nm.endswith("군") else "시"
            name, full = nm, f"{sido_name[sd]} {nm}"
            rule = "5 광역시 안의 군" if sido_name[sd].endswith("광역시") and nm.endswith("군") else (
                "4 제주 행정시" if sd == "50" else "5 시·군")
        if (sd, name) in SPECIAL_CITIES:
            kind = "특례시"
        g = groups.setdefault(key, {"name": name, "full": full, "sido": sd, "kind": kind, "sgg": [], "rule": rule})
        g["sgg"].append(code)
        how[code] = rule
    # 감사 05: 자치구를 묶은 도시의 포함 범위. 같은 광역시 안의 군은 따로 도시이므로 '자치구 N곳 합 · ○○군 별도'로 적는다
    for g in groups.values():
        if not g["rule"].startswith(("1 ", "3 ")):
            continue
        n = len(g["sgg"])
        if g["rule"].startswith("3 "):
            g["scope"] = f"옛 광주광역시 자치구 {n}곳의 합"
            g["scope_label"] = f"옛 광주 자치구 {n}곳 합"
            continue
        gun = [o["name"] for o in groups.values() if o is not g and o["sido"] == g["sido"] and o["rule"].startswith("5 광역시 안의 군")]
        g["scope"] = f"자치구 {n}곳의 합" + (f" · {'·'.join(gun)}은 따로 도시 (이 도시 값에 넣지 않음)" if gun else "")
        # 7b: 도시 패널 머리의 짧은 부제 (scope 와 같은 사실, 줄여 쓴 것)
        g["scope_label"] = f"자치구 {n}곳 합" + (f" · {'·'.join(gun)} 별도" if gun else "")
    for g in groups.values():
        g.pop("rule")
    return list(groups.values()), how


def weighted_center(items):
    w = sum(i[2] for i in items)
    if w <= 0:
        return None
    return sum(i[0] * i[2] for i in items) / w, sum(i[1] * i[2] for i in items) / w


def read_offices(world, groups):
    """청사 소재지: 원표의 기관 이름(시도 표기 포함)과 주소(시군구부터)를 읽어 현재 시군구로 옮긴다 (county 정밀도).

    - 주소 앞뒤의 '(산격청사)', '(제1청사)' 같은 괄호 표기는 청사 이름으로 남기고 주소 대응에서는 뗀다.
    - 주소에는 시도가 없으므로 기관 이름 앞의 시도 표기를 시도로 쓴다 (주소 대응기 AddressResolver, 외부 지오코딩 없음).
    - 시군구청은 주소의 시군구가 기관 이름의 시군구와 같은지 대조한다.
    """
    import csv as _csv
    from lib.address import AddressResolver
    from lib.terrain import layer_path
    res = AddressResolver(world, groups)
    sido_name = {s["code"]: s["name"] for s in world["states"]}
    out, fails = [], []
    with open(layer_path(OFFICES), encoding="utf-8-sig", newline="") as f:
        rows = list(_csv.DictReader(f))
    for r in rows:
        name, kind, addr = r["name"].strip(), r["kind"].strip(), r["address"].strip()
        tag = " ".join(re.findall(r"\(([^()]*)\)", addr))
        clean = re.sub(r"\([^()]*\)", " ", addr).strip()
        sd, rest = res.sido_of(name)
        hit = res.resolve(clean, sido_hint=name) if sd else None
        located = "주소"
        if not hit and kind in ("시군구청", "일반구청"):
            # 주소가 읍·면부터 적혀 시군구가 없으면(예: '청량읍 군청로 1') 기관 이름의 시군구로 둔다
            hit = res.resolve(name)
            located = "기관 이름 (주소에 시군구가 없음)" if hit else located
        rec = {"name": name, "kind": kind, "address": addr, "office_tag": tag or None, "sido": sd,
               "sgg": sorted(hit["codes"]) if hit else None, "precision": "county" if hit else None, "source": r["source_id"],
               "located_by": located}
        if located != "주소":
            fails.append({"name": name, "address": addr, "reason": "주소에 시군구가 없어 기관 이름의 시군구로 놓음", "placed": True})
        if not hit:
            fails.append({"name": name, "address": addr, "reason": "주소에서 현재 시군구를 찾지 못함"})
            continue
        if kind in ("시군구청", "일반구청"):
            own = res.resolve(name)
            rec["name_matches"] = bool(own and set(hit["codes"]) <= set(own["codes"]))
        else:
            # 본청: 기관 이름이 시도 표기만이면 본청, '…북부청사'처럼 뒤에 말이 붙으면 별도 청사 (원표 표기대로 둘 다 싣는다)
            rec["main"] = rest == ""
            rec["sido_label"] = name if rest == "" else name
            rec["current_sido_name"] = sido_name[sd]
        out.append(rec)
    specials = []
    with open(layer_path(SPECIAL_OFFICES), encoding="utf-8-sig", newline="") as f:
        for r in _csv.DictReader(f):
            specials.append({"name": r["name"].strip(), "kind": r["kind"].strip(), "year": r["year"].strip(),
                             "address": (r["address"] or "").strip() or None, "source": r["source_id"]})
    return out, fails, specials, res


def pop_fields(p, series, growth):
    ind = popstats.indicators(p)
    out = {
        "population": p["total"],
        "pop_series": series,
        "growth_5y": rnd(growth, 2),
        "age": {"mean_est": rnd(ind["mean_est"], 1), "median_est": rnd(ind["median_est"], 1),
                "under15": rnd(ind["under15"], 2), "working": rnd(ind["working"], 2),
                "over65": rnd(ind["over65"], 2), "women_20_39": rnd(ind["women_20_39"], 2)},
        "extinction_index": rnd(ind["extinction_index"], 3),
        "extinction_stage": popstats.extinction_stage(ind["extinction_index"]),
        "sex_ratio_20_39": rnd(ind["sex_ratio_20_39"], 1),
        "pyramid": {"male": p["male"], "female": p["female"]},
    }
    return out


def land_stats_fn(sgg_codes_all, old_names):
    """국가토지피복통계(시군구별 중분류 면적, ha) -> 도시·시도·전국 '땅' 구역 값.

    시군구 합으로 낸다. 현재 코드가 빈 행(개편 전 분할 시군구)은 현재 시군구로 나누지 않는다. 다만 그 개편 전 단위의 후신 시군구
    (crosswalk.SPLITS)가 모두 한 도시·시도 안에 들면 그 도시·시도 합에는 통째로 더하고 '개편 전 구역 기준 합'으로 표시한다.
    그래도 통계 행이 없는 소속 시군구가 남으면 null 과 이유를 둔다. 빈 값은 0 으로 바꾸지 않는다.
    old_names: 개편 전 시군구 코드 -> 주민등록 과거 원자료의 이름('인천광역시 중구'). 통계 행(시도, 시군구 이름)을 개편 전 코드에 맞추는 데 쓴다.
    """
    from lib import terrain as TR
    by, nat, blank, year, srcs = TR.read_me_stats()
    missing_all = sorted(c for c in sgg_codes_all if c not in by)
    old_units = {}   # 통계의 빈 코드 행 (시도, 이름) -> (개편 전 코드, 후신 현재 코드)
    for k in blank:
        hit = [pc for pc, nm in old_names.items() if nm == f"{k[0]} {k[1]}"]
        if len(hit) == 1:
            old_units[k] = (hit[0], crosswalk.SPLITS[hit[0]])
    meta = {"year": int(year), "source": "기후에너지환경부 국가 토지피복 통계 (" + year + "년 기준, 공공데이터포털 15163128, 공공누리 제1유형)",
            "source_id": srcs, "items": {k: v for k, v in TR.STATS_ITEMS.items()},
            "blank_rows": [{"sido": k[0], "name": k[1], "total_ha": v.get("총합계")} for k, v in sorted(blank.items())],
            "codes_without_row": missing_all,
            "old_units": {f"{k[0]} {k[1]}": {"old_code": v[0], "successors": v[1]} for k, v in sorted(old_units.items())},
            "rule": ("시군구 행을 더해 도시·시도 값을 낸다. 산림 = 활엽수림 + 침엽수림 + 혼효림, 시가화 = 주거·공업·상업·문화체육휴양·교통·공공시설지역. "
                     "비율은 같은 행들의 총합계 대비. 개편 전 시군구 단위로만 공표된 행(현재 코드가 빈 행 "
                     f"{len(blank)}개: " + ", ".join(f"{k[0]} {k[1]}" for k in sorted(blank)) + ")은 현재 시군구(자치구·일반구)로 나누지 않는다. "
                     "그 개편 전 단위의 후신 시군구가 모두 한 도시·시도 안에 들면 그 도시·시도 합에는 통째로 더하고 '개편 전 구역 기준 합'으로 표시한다"
                     "(후신 대응은 행정구역 코드 대응표, 개편 전 이름은 주민등록 과거 원자료). 그래도 통계 행이 없는 소속 시군구가 남으면 값을 비운다. "
                     "전국은 통계의 전국 행.")}

    def items_of(rows_):
        tot = rows_.get("총합계")
        out = {}
        for nm, parts in TR.STATS_ITEMS.items():
            vs = [rows_.get(p_) for p_ in parts]
            ha = None if any(v is None for v in vs) else sum(vs)
            out[nm] = {"ha": rnd(ha, 0), "pct": rnd(100 * ha / tot, 1) if ha is not None and tot else None}
        return {"total_ha": rnd(tot, 0), "by": out}

    def for_codes(codes):
        cs = set(codes)
        use_old = [k for k, (_, succ) in sorted(old_units.items()) if set(succ) <= cs and not any(c in by for c in succ)]
        covered = {c for k in use_old for c in old_units[k][1]}
        miss = [c for c in codes if c not in by and c not in covered]
        if miss:
            return {"year": int(year), "value": None, "missing": miss,
                    "reason": "소속 시군구 " + ", ".join(miss) + " 의 통계 행이 없음 (개편 전 시군구 단위로만 공표되고 그 단위가 이 지역 밖으로 걸침) — 일부만 더하지 않음"}
        acc = {}
        for rows_ in [by[c] for c in codes if c in by] + [blank[k] for k in use_old]:
            for k, v in rows_.items():
                acc[k] = None if (v is None or acc.get(k, 0) is None) else acc.get(k, 0) + v
        out = {"year": int(year), "value": items_of(acc)}
        if use_old:
            out["old_units"] = [f"{k[0]} {k[1]}" for k in use_old]
            out["note"] = ("개편 전 구역 기준 합: " + ", ".join(f"{k[0]} {k[1]}(→ " + "·".join(old_units[k][1]) + ")" for k in use_old)
                           + " 은 개편 전 단위로만 공표돼 통째로 더했다 (자치구·일반구로는 나누지 않음)")
        return out

    return meta, for_codes, (lambda: {"year": int(year), "value": items_of(nat)})


def main():
    world = load_json(site("world.json"))
    npz = np.load(build("world_samples.npz"))
    samp, centers = npz["samp"], npz["centers"]
    owner = np.array(world["owner"])
    county = np.array(world["county"])
    counties, states = world["counties"], world["states"]
    sgg_codes = [c["code"] for c in counties]
    cur_set = set(sgg_codes)
    cols = world["grid"]["cols"]
    dongs = load_json(build("dongs.json"))

    # ---------------- 최신 시점 ----------------
    ym, f_sgg, f_emd, f_nat = popstats.latest_files()
    vintage = f"{ym[:4]}-{ym[4:]}"
    _, recs = jumin.read(f_sgg)
    leaf, parents = jumin.leaf_sgg(recs)
    sgg_pop = {r["code"][:5]: r for r in leaf}
    if set(sgg_pop) != cur_set:
        raise ValueError(f"인구 시군구 코드와 경계 코드가 다름: {sorted(set(sgg_pop) ^ cur_set)}")
    _, nat_recs = jumin.read(f_nat)
    nation_row = next(r for r in nat_recs if jumin.is_nation(r["code"]))
    sido_rows = {r["code"][:2]: r for r in nat_recs if jumin.is_sido(r["code"])}
    log(f"기준 {vintage}: 시군구 {len(sgg_pop)}개, 전국 {nation_row['total']:,}명")

    # 읍면동
    dong_rec, emd_report, emd_status = None, [], "없음 (시군구 자료로 진행)"
    if f_emd:
        dong_rec, emd_report = popstats.dong_population(f_emd, dongs)
        chk = {}  # 동 인구를 시군구별로 더하면 시군구 행과 같아야 한다
        for d in dongs:
            chk[d["sgg"]] = chk.get(d["sgg"], 0) + dong_rec[d["code"]]["total"]
        bad = {s: (chk.get(s), sgg_pop[s]["total"]) for s in sgg_pop if chk.get(s, 0) != sgg_pop[s]["total"]}
        if bad:
            raise ValueError(f"읍면동 합 != 시군구 행: {bad}")
        emd_status = (f"읍면동 자료 사용: 경계 행정동 {len(dongs)}개에 배정, 출장소 등 경계에 없는 행 "
                      f"{sum(1 for r in emd_report if r['total'])}개({sum(r['total'] for r in emd_report):,}명)는 상위 읍면에 더함")
    log(f"읍면동: {emd_status}")

    # ---------------- 과거 연도 ----------------
    years = popstats.year_files()
    past = {}
    past_codes_all = set()
    for y, path in sorted(years.items()):
        _, rr = jumin.read(path)
        lf, _ = jumin.leaf_sgg(rr)
        cur_names = {c["code"]: f"{c['name']}" for c in counties}
        byc = {}
        for r in lf:
            pc = r["code"][:5]
            outs = crosswalk.to_current(pc, cur_set)   # 대응표에 없으면 CrosswalkError
            if pc not in crosswalk.SPLITS:
                crosswalk.check_names(r["name"], [cur_names[o] for o in outs])
            byc[pc] = r
            past_codes_all.add(pc)
        past[y] = byc
        nat_y = next((r for r in jumin.read(path.replace("_sgg_", "_nation_"))[1] if jumin.is_nation(r["code"])), None)
        s = sum(r["total"] for r in lf)
        if nat_y and nat_y["total"] != s:
            raise ValueError(f"{y}-12 시군구 합 {s} != 전국 {nat_y['total']}")
    unit = crosswalk.comparable_units(cur_set, past_codes_all)

    def unit_series(cur_list):
        """현재 시군구 목록의 연도별 인구. 비교 단위를 다 덮지 못하면 None."""
        units = {unit[c] for c in cur_list}
        members = {c for c in cur_set if unit[c] in units}
        if not members <= set(cur_list):
            return None
        out = {}
        for y, byc in past.items():
            tot = 0
            for pc, r in byc.items():
                outs = crosswalk.to_current(pc, cur_set)
                if unit[outs[0]] in units:
                    tot += r["total"]
            out[str(y)] = tot
        out[vintage] = sum(sgg_pop[c]["total"] for c in cur_list)
        return out

    def growth(series):
        if not series or "2020" not in series or "2025" not in series or not series["2020"]:
            return None
        return 100 * (series["2025"] / series["2020"] - 1)

    def growth_latest(series):
        if not series or "2020" not in series or not series["2020"]:
            return None
        return 100 * (series[vintage] / series["2020"] - 1)

    # 시군구별 (렌즈용): 비교 단위로 계산
    sgg_stats = {}
    for c in sgg_codes:
        u = unit[c]
        mem = sorted(x for x in cur_set if unit[x] == u)
        ser = unit_series(mem)
        ind = popstats.indicators(sgg_pop[c])
        sgg_stats[c] = {"pop": sgg_pop[c]["total"], "series_unit": mem, "series": ser,
                        "growth_latest": growth_latest(ser), "growth_5y": growth(ser),
                        **{k: ind[k] for k in ("mean_est", "under15", "over65", "extinction_index", "sex_ratio_20_39")}}

    # ---------------- 도시 ----------------
    cities, how = define_cities(counties, states)
    sgg_city = {}
    for i, g in enumerate(cities):
        for s in g["sgg"]:
            if s in sgg_city:
                raise ValueError(f"시군구 {s} 가 두 도시에 속함")
            sgg_city[s] = i
    if set(sgg_city) != cur_set:
        raise ValueError("도시에 속하지 않은 시군구가 있음")
    cidx = {c["code"]: k for k, c in enumerate(counties)}

    # 동 대표점 + 인구 (읍면동 가중 중심)
    dong_pop = {d["code"]: (dong_rec[d["code"]]["total"] if dong_rec else 0) for d in dongs}
    cities.sort(key=lambda g: -sum(sgg_pop[s]["total"] for s in g["sgg"]))

    # ---------------- 청사 (5b §2.3) ----------------
    from lib.official import part_label
    offices, off_fail, specials, _res = read_offices(world, cities)
    city_key = {s: (g["sido"], g["name"]) for g in cities for s in g["sgg"]}
    cname_of = {c["code"]: c["name"] for c in counties}
    special_sidos = {"12"} if specials else set()   # 특별법이 청사를 정한 시도: 종전 시도청 표 대신 특별법의 청사를 쓴다
    city_offices = {}
    for o in offices:
        if o["kind"] != "시도청":
            continue
        key = city_key[o["sgg"][0]]
        o["city_key"] = key
        if o["sido"] in special_sidos:
            o["role"] = "종전 시도청 (통합 전 공표본)"
            continue
        o["role"] = "시도청" if o["main"] else "시도 별도 청사"
        city_offices.setdefault(key, []).append(o)
    sp_out = []
    for sp in specials:
        base = re.sub(r"청사$", "", sp["name"])
        match = None
        for o in offices:
            if o["kind"] != "시도청" or o["sido"] not in special_sidos:
                continue
            stem = re.sub(r"(시|군|구)$", "", cname_of[o["sgg"][0]])
            if part_label(o["name"]) == base or stem == base:
                match = o
                break
        e = dict(sp, sido="12", base=base, law=SPECIAL_ACT)
        if match:
            e.update(sgg=match["sgg"], city_key=match["city_key"], precision="county",
                     located_by=f"청사 이름의 지역 '{base}' = 종전 시도청 '{match['name']}'(주소 {match['address']})")
            city_offices.setdefault(match["city_key"], []).append({"name": sp["name"], "role": "통합특별시 청사", "kind": sp["kind"],
                                                                  "address": match["address"], "sgg": match["sgg"],
                                                                  "precision": "county", "law": SPECIAL_ACT})
        else:
            e.update(sgg=None, city_key=None, precision=None,
                     located_by=f"특별법은 청사 이름만 정하고 주소가 없으며, '{base}' 와 이름이 맞는 종전 시도청 주소도 없어 지도에 놓지 않음")
        sp_out.append(e)
    sgg_offices = [o for o in offices if o["kind"] != "시도청"]
    off_mismatch = [o["name"] for o in sgg_offices if not o.get("name_matches")]
    log(f"청사: 원표 {len(offices) + sum(1 for f_ in off_fail if not f_.get("placed"))}건, 주소 대응 {len(offices)}, 실패 {len(off_fail)} {off_fail}; "
        f"시군구청 이름·주소 시군구 불일치 {len(off_mismatch)} {off_mismatch}; 통합특별시 청사 {[(e['name'], e['sgg']) for e in sp_out]}")
    old_names = {}
    for y, byc in sorted(past.items()):
        for pc, r in byc.items():
            if pc in crosswalk.SPLITS:
                old_names.setdefault(pc, r["name"])
    lmeta, land_of, land_nat = land_stats_fn(sgg_codes, old_names)
    out_cities = []
    for i, g in enumerate(cities):
        kset = {cidx[s] for s in g["sgg"]}
        foot = [int(k) for k in np.nonzero(np.isin(county, list(kset)))[0]]
        p = popstats.merge([sgg_pop[s] for s in g["sgg"]])
        ser = unit_series(g["sgg"])
        if ser is None:
            raise ValueError(f"{g['name']}: 비교 단위가 도시 경계를 넘음")
        items = [(d["rx"], d["ry"], dong_pop[d["code"]]) for d in dongs if d["sgg"] in g["sgg"]]
        ctr = weighted_center(items) if dong_rec else None
        center_rule = "읍면동 인구 가중 중심"
        if ctr is None:
            P = centers[foot]
            ctr = (float(P[:, 0].mean()), float(P[:, 1].mean()))
            center_rule = "넓이 중심"
        # 그 점이 자기 영토 밖이면 가장 가까운 자기 칸 중심으로
        P = centers[foot]
        d2 = ((P - ctr) ** 2).sum(1)
        k = int(np.argmin(d2))
        R = world["grid"]["radius"]
        inside = d2[k] <= (R * 0.87) ** 2
        if not inside:
            ctr = (float(P[k, 0]), float(P[k, 1]))
            center_rule += " → 영토 밖이라 가까운 칸으로"
        cap = "없음"
        offs = city_offices.get((g["sido"], g["name"]), [])
        if g["name"] == NATIONAL_CAPITAL and g["sido"] == "11":
            cap = "수도"
        elif any(o["role"] in ("시도청", "시도 별도 청사") for o in offs):
            cap = "도청소재지"
        elif any(o["role"] == "통합특별시 청사" for o in offs):
            cap = "통합청사"
        own_offices = [{"name": o["name"], "kind": o["kind"], "address": o["address"], "sgg": o["sgg"]}
                       for o in sgg_offices if set(o["sgg"]) <= set(g["sgg"])]
        c = {
            "id": i, "name": g["name"], "full": g["full"], **({"scope": g["scope"], "scope_label": g["scope_label"]} if g.get("scope") else {}), "sido": g["sido"], "kind": g["kind"], "capital": cap,
            "x": round(ctr[0], 1), "y": round(ctr[1], 1), "cell": foot[k], "footprint": foot, "sgg": g["sgg"],
            **pop_fields(p, ser, growth(ser)),
            "growth_latest": rnd(growth_latest(ser), 2),
            "center_rule": center_rule,
            "sido_offices": [{k: o.get(k) for k in ("name", "role", "kind", "address", "sgg", "precision", "law")} for o in offs],
            "offices": own_offices,
            "land_stats": land_of(g["sgg"]),
        }
        out_cities.append(c)
    log(f"도시 {len(out_cities)}개")

    # 순위와 닮은 도시
    def getv(c, path):
        v = c
        for p_ in path:
            v = v.get(p_) if isinstance(v, dict) else None
        return v

    rank_defs = {"population": (("population",), True), "growth": (("growth_5y",), True),
                 "over65": (("age", "over65"), True), "extinction": (("extinction_index",), False)}
    for rk, (path, desc) in rank_defs.items():
        vals = [(getv(c, path), c["id"]) for c in out_cities if getv(c, path) is not None]
        vals.sort(key=lambda t: (-t[0] if desc else t[0], t[1]))
        pos = {cid: n + 1 for n, (_, cid) in enumerate(vals)}
        for c in out_cities:
            c.setdefault("ranks", {})[rk] = pos.get(c["id"])
    lp = np.array([math.log10(max(c["population"], 1)) for c in out_cities])
    o65 = np.array([c["age"]["over65"] or 0 for c in out_cities])
    Z = np.column_stack([(lp - lp.mean()) / lp.std(), (o65 - o65.mean()) / o65.std()])
    for k, c in enumerate(out_cities):
        d = ((Z - Z[k]) ** 2).sum(1)
        d[k] = np.inf
        c["peers"] = [int(j) for j in np.argsort(d, kind="stable")[:5]]
    n_rank = len(out_cities)

    # ---------------- 시도·전국 ----------------
    labels = load_json(build("labels.json"))
    out_states = []
    for s in states:
        sc = s["code"]
        mem = [c for c in sgg_codes if c[:2] == sc]
        p = popstats.merge([sgg_pop[c] for c in mem])
        if sc in sido_rows and sido_rows[sc]["total"] != p["total"]:
            raise ValueError(f"{s['name']}: 시군구 합 {p['total']} != 시도 행 {sido_rows[sc]['total']}")
        ser = unit_series(mem)
        st = {"code": sc, "name": s["name"], "short": s["short"], **pop_fields(p, ser, growth(ser)),
              "growth_latest": rnd(growth_latest(ser), 2),
              "cities": [c["id"] for c in out_cities if c["sido"] == sc],
              "label": {k: labels[sc][k] for k in ("x", "y", "angle", "size")},
              "cells": int((owner == states.index(s)).sum()),
              "offices": [{"name": o["name"], "role": o["role"], "address": o["address"], "sgg": o["sgg"],
                           "city": next((c["id"] for c in out_cities if (c["sido"], c["name"]) == o["city_key"]), None)}
                          for o in offices if o["kind"] == "시도청" and o["sido"] == sc],
              "special_offices": [{k: e[k] for k in ("name", "kind", "sgg", "precision", "located_by", "law")} |
                                  {"city": next((c["id"] for c in out_cities if (c["sido"], c["name"]) == e["city_key"]), None)}
                                  for e in sp_out if e["sido"] == sc] or None,
              "land_stats": land_of(mem)}
        out_states.append(st)
    allp = popstats.merge([sgg_pop[c] for c in sgg_codes])
    nser = unit_series(sgg_codes)
    nation = {"name": "대한민국", **pop_fields(allp, nser, growth(nser)), "growth_latest": rnd(growth_latest(nser), 2),
              "national_row": nation_row["total"], "cities": len(out_cities), "sgg": len(sgg_codes),
              "states": len(states), "land_stats": land_nat()}
    no_land = [c["name"] for c in out_cities if c["land_stats"]["value"] is None] + [s_["short"] for s_ in out_states if s_["land_stats"]["value"] is None]
    old_used = [c["name"] for c in out_cities if c["land_stats"].get("old_units")] + [s_["short"] for s_ in out_states if s_["land_stats"].get("old_units")]
    log(f"땅 통계(국가토지피복통계 {lmeta['year']}): 현재 코드가 빈 행 {len(lmeta['blank_rows'])}개, 개편 전 코드 대응 {lmeta['old_units']}, "
        f"통계 행이 없는 현재 시군구 {lmeta['codes_without_row']}, 개편 전 구역 기준 합 {old_used}, 값을 비운 도시·시도 {no_land}")

    # 상위 자료
    save_json(site("cities.json"), out_cities)
    save_json(site("states.json"), out_states)
    save_json(site("nation.json"), {"vintage": vintage, "year": int(ym[:4]), "series_years": sorted(nser),
                                    "nation": nation, "land_stats_meta": lmeta,
                                    "offices": {"count": len(offices) + sum(1 for f_ in off_fail if not f_.get("placed")), "resolved": len(offices), "failed": off_fail,
                                                "name_mismatch": off_mismatch, "special": sp_out, "law": SPECIAL_ACT},
                                    "notes": {
                                        "capital": ("도청 소재지는 행정안전부 「2026년 지방자치단체 행정구역 및 인구 현황」(2025-12-31 기준) 사무소 소재지 표의 "
                                                    "시도청 주소에서 읽었다 (주소 → 시군구, county 정밀도, 외부 지오코딩 없음). 한 시도에 청사가 여럿이면 원표 표기대로 "
                                                    "모두 싣는다(경기도 본청·북부청사, 대구 산격·동인청사). 전남광주통합특별시는 " + SPECIAL_ACT +
                                                    "가 종전 전남동부청사·무안청사·광주청사를 균형 있게 활용·운영하도록 정해, 청사 3곳을 모두 적고 수도(주 청사) 표시를 하나로 "
                                                    "정하지 않는다. 특별법에는 주소가 없어 청사 이름의 지역(무안·광주)을 종전 시도청 주소에 맞췄고, 전남동부청사는 "
                                                    "주소 자료가 없어 지도에 놓지 않았다. 수도(서울) 표시는 수작업 값이다."),
                                        "special_city": "특례시 표시는 수작업 표(수원·고양·용인·화성·창원)다.",
                                        "gwangju": "전남광주통합특별시 안의 광주 자치구는 이름(동구·서구 …)만으로 판별할 수 없어 "
                                                   f"시군구 코드 범위 {GWANGJU_RANGE[0]}–{GWANGJU_RANGE[1]} 로 묶었다.",
                                        "growth": "growth_5y 는 2020-12 → 2025-12, growth_latest 는 2020-12 → "
                                                  f"{vintage}. 나뉜 구(부천·화성·인천 개편)는 비교 단위로 묶어 계산했다.",
                                        "age": "평균·중위 연령은 5세 계급 중간값(100세 이상은 102.5세)으로 낸 추정치다.",
                                        "ranks": f"순위는 도시 {n_rank}곳 중. 소멸위험 순위 1 = 지수가 가장 낮음(가장 위험).",
                                    }})
    save_json(build("sgg_stats.json"), {"vintage": vintage, "sgg": sgg_stats,
                                        "emd_report": emd_report,
                                        "emd_status": emd_status}, compact=False)
    with open(build("cities_check.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "도시", "전체 이름", "시도", "종류", "소재지", "인구", "칸 수", "시군구 코드", "시군구 이름", "규칙"])
        nm = {c["code"]: c["name"] for c in counties}
        for c in out_cities:
            w.writerow([c["id"], c["name"], c["full"], c["sido"], c["kind"], c["capital"], c["population"],
                        len(c["footprint"]), " ".join(c["sgg"]), " / ".join(nm[s] for s in c["sgg"]),
                        "; ".join(sorted({how[s] for s in c["sgg"]}))])
    log(f"cities_check.csv, 도시 {len(out_cities)}개, 시도 {len(out_states)}개")


if __name__ == "__main__":
    sys.exit(main())

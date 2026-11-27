"""세계 만들기: 투영, 헥스 격자, 칸 속성(소유·지형·물·기복·피복), 행정구역 목록, 강·호수·갯벌 -> site/data/world.json

중간 산출물 data/build/world_samples.npz : 칸 × 표본점 37개가 떨어진 행정동 번호 (렌즈·집계가 다시 쓴다)
           data/build/dongs.json        : 행정동 목록 (코드, 시군구, 이름, 넓이, 대표점)
           data/build/terrain_cache.npz : 칸별 피복 비율(cover_share)·칸에 나눈 도엽 면적·도엽×칸 무게, 피복 출처, 갯벌 비율 (렌즈·검증이 다시 쓴다)
           data/build/landcover_compare.json: 칸 비율 vs 국가 토지피복 통계 (전국·시군구)
           data/build/land_baseline.json: 5b 지형 보강 전 육지 칸·소유 시군구 (지형 보강이 이것을 바꾸지 않았는지 검사)

지형 보강 입력(읽기만): data/raw/layers5/files/p2-15150509.csv(기후에너지환경부 세분류 토지피복지도 도엽 통계, 두 판 공용 — lib/cover_sheets.py),
data/raw/layers5/files/p2-15163128.csv(국가 토지피복 통계, 대조용), data/build/layers 의 landcover.tif(ESA WorldCover — 도엽 통계가 닿지 않는 칸 보완용 대체 자료),
rivers.geojson(WAMIS 국가·지방하천), lakes.geojson(OpenStreetMap 수면 대체 자료), tidal_flats.geojson(해양수산부 2011).
기후에너지환경부 토지피복지도 WMS 그림(data/raw/landcover_me)은 어느 판에서도 읽지 않는다.
"""
import collections
import io
import json
import math
import os
import re
import sys
import zipfile

import numpy as np
import shapefile
import shapely
from pyproj import Transformer
from shapely.geometry import box, shape

from lib import cover_sheets as CS
from lib import profile as PRF
from lib import terrain as TR
from lib.common import build, load_json, raw, rnd, save_json, site
from lib.hexgrid import Grid

R_M = 2800.0           # 헥스 외접원 반지름 (m)
R_U = 25.0             # 같은 반지름의 화면 단위
MPU = R_M / R_U        # 1 화면 단위 = 112 m
MARGIN = 20000.0       # 지도 범위 여백 (m)
LON0, LAT0, LON1, LAT1 = 124.5, 33.0, 132.0, 38.95
TARGET = (0.35, 0.40, 0.25)  # 평지:구릉:산 목표 비율
FOREIGN = {"PRK": "북한", "CHN": "중국", "JPN": "일본"}
# 5b 지형 기준값 (분포를 보고 정한 값, 규칙 문장에 그대로 적는다)
LOCAL_RIVER_KM = 20.0      # 지방하천은 같은 이름끼리 이어 붙인 선의 길이가 이 값 이상이면 그린다 (확대했을 때만)
RIVER_SIMPLIFY_M = {"국가하천": 120.0, "지방하천": 200.0}
MAIN_STEM = re.compile(r"^[1-5]000010$")   # 하천코드: 대권역 번호(1–5) + 000010 = 대권역 본류 (한강·낙동강·금강·섬진강·영산강)
LAKE_DRAW_KM2 = 1.0        # 이 넓이 이상 수면은 칸 위에 폴리곤으로 그린다
LAKE_SIMPLIFY_M = 100.0
LAKE_LABEL_KM2 = 15.0      # 이름 있는 수면 가운데 이 넓이 이상은 확대 시 이름표
TIDAL_TILE = 0.30          # 바다·연안 칸 넓이 중 갯벌 비율이 이 값 이상이면 갯벌 타일

TO5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)


def log(*a):
    print("[world]", *a, flush=True)


def BIAS_SENTENCE(cmp_, year):
    """칸 비율의 알려진 치우침을 계산한 숫자로 적은 문장 (연감·렌즈 설명·출처 비고·패널이 같은 문장을 쓴다)."""
    n, tol = cmp_["nation"], cmp_["tolerance"]
    ks = CS.COMPARE_KEYS
    worst_nat = max(abs(n[k]["diff_pp"]) for k, _ in ks)
    small = [r for r in cmp_["counties"] if 0 < r["cells"] < tol["county_min_cells"]]
    w = max(((abs(r[k]["diff_pp"]), r[k]["diff_pp"], nm, r["name"]) for r in small for k, nm in ks), default=None)
    big = cmp_["summary"]
    s = (f"도엽(약 6 km²) 단위 공식 통계를 칸에 나눈 값이라 전국 칸 평균은 국가 토지피복 통계({year}년 기준)와 거의 같다: "
         + ", ".join(f"{nm} {n[k]['cells_pct']:.1f}% (통계 {n[k]['stats_pct']:.1f}%)" for k, nm in ks)
         + f" — 차이는 {worst_nat:.1f}%p 이하. 칸 {tol['county_min_cells']}개 이상인 시군구 {big['forest']['big_n']}곳에서는 시군구 칸 평균과 통계의 차이가 "
         + "대부분(90%) " + "·".join(f"{nm} {big[k]['big_p90_pp']:.1f}%p" for k, nm in ks) + " 안이다.")
    if w:
        s += (f" 칸이 그보다 적은 작은 시군구는 칸 경계와 시군구 경계가 달라 크게 어긋날 수 있다(가장 큰 차이: {w[3]} {w[2]} {w[1]:+.1f}%p). "
              "시군구 합계는 패널의 통계 값을 본다.")
    return s


def cover_records(ctx):
    """world.json 의 피복 기록: 규칙 문장(tables.cover), cover_meta. ctx 는 build_world 의 피복 계산 결과."""
    c = ctx
    en = c["esa_names"]
    by_major = {k: [nm for nm, kk in CS.CLASS_MAP if CS.MAJOR_OF.get(kk) == k] for k in TR.COVER_KEYS}
    ix = c["index"]
    sp = ", ".join(f"{k}(남 {-a:g}′{'·서 ' + format(-b, 'g') + '′' if b else ''})" if a < 0 else f"{k}(북 {a:g}′)" for k, (a, b) in CS.SPECIAL_MIN.items())
    method = ("도엽마다 해양수·갯벌을 뺀 세분류 면적을 도엽과 칸이 겹치는 대한민국 행정경계(행정동) 안 넓이에 비례해 칸에 나누고, "
              "행정경계와 겹치지 않는 도엽(바다 가운데 작은 섬 등)은 도엽과 칸이 겹치는 넓이에 비례해 나눈다. "
              "칸 비율은 칸에 모인 면적 ÷ 칸에 모인 면적 합이고, 도엽 통계가 하나도 닿지 않는 육지 칸만 ESA WorldCover 로 채운다.")
    cmap = [{"class": nm, "key": kk, "name": CS.LEAF_KO[kk], "major": CS.MAJOR_OF.get(kk)} for nm, kk in CS.CLASS_MAP]
    grp = {}
    for nm, kk in CS.CLASS_MAP:
        grp.setdefault(kk, []).append(nm)
    map_rule = "; ".join(f"{'·'.join(v)} → {CS.LEAF_KO[k]}" + (f" ({k})" if k not in CS.EXCLUDED else "") for k, v in grp.items()) + \
        ". 대분류: 숲 = 활엽수림 + 침엽수림 + 혼효림, 농경지 = 논 + 밭 + 시설재배지 + 과수원 + 기타재배지(목장양식장 포함)."
    nat = c["compare"]["nation"]
    tables = [
        {"id": 0, "key": None, "name": "없음", "rule": ("대한민국 육지 칸이 아니거나(북한·일본·중국·바다 칸에는 피복을 두지 않는다) 도엽 통계도 ESA 보완 자료도 "
                                                      f"칸 안에 없음 (육지 {len(c['no_cover'])}칸)")},
        *[{"id": k + 1, "key": key, "name": TR.COVER_KO[key],
           "rule": ("세분류 " + "·".join(by_major[key]) + " · 보완 칸은 ESA WorldCover "
                    + ", ".join(f"{code} {en[code]}" for code, kk in TR.ESA_TO_COVER.items() if kk == key) + f" → 칸 {c['cover_dist'][key]}개")}
          for k, key in enumerate(TR.COVER_KEYS)],
        {"id": "note", "name": "피복의 근거",
         "rule": (f"{CS.SOURCE_NAME}. {c['sheets']['rule']} "
                  f"도엽번호 8자리는 국토지리정보원 1:5,000 도엽 체계로 읽는다: 위도 정수 2자리, 경도 정수 끝자리(4–9 → 124–129°, 0–2 → 130–132°), "
                  "1:50,000 번호 01–16(1°×1° 안 15′×15′, 북서에서 행 우선), 1:5,000 번호 001–100(15′×15′ 안 1.5′×1.5′, 북서에서 행 우선), 경위도는 세계측지계(GRS80). "
                  f"섬 때문에 도곽을 옮긴 1:50,000 도엽 {len(CS.SPECIAL_MIN)}개는 옮긴 만큼 더한다: {sp}. "
                  f"검산: 도엽마다 세분류 41개 면적 합을 이 테두리의 타원체 넓이와 견주면 {ix['sheets']:,}개 가운데 {ix['within_1e-4']:,}개가 0.01% 안에서 같다"
                  f"(중앙값 차이 {100 * ix['median_abs_rel']:.4f}%); 크게 모자란 {ix['short_over_10pct']}개는 휴전선·해안에서 잘린 도엽이다. "
                  f"{method} 결과: 도엽 통계 칸 {c['src']['me']}칸, ESA 보완 {c['src']['esa']}칸"
                  + (" — " + ", ".join(f"{county_name(c['sggnm'][k])} {v}" for k, v in c["esa_sgg"].most_common()) if c["esa_sgg"] else "")
                  + f". 전국 칸 평균 비율: " + ", ".join(f"{TR.SHARE_KO[k]} {c['share_w'][k] * 100:.1f}%" for k in TR.COVER_KEYS) + ". " + c["bias"])},
        {"id": "map", "name": "세분류 41개 → 칸 피복 열", "rule": map_rule},
        {"id": "crop", "name": "농경지 세분 (crop_kind)",
         "rule": ("cover 가 농경지인 칸에만 붙인다. 도엽 통계 칸은 칸 비율 논·밭·과수원·시설재배지 가운데 가장 큰 것(같은 수면 이 순서, 기타재배지는 후보에서 뺀다; "
                  "넷 다 0 이면 null), crop_src 'me'. ESA 보완 칸은 농경지 종류가 없어 null. 결과: "
                  + ", ".join(f"{'도엽 통계' if s == 'me' else '구분 없음'}·{TR.SHARE_KO.get(k, '농경지')} {v}칸"
                              for (s, k), v in sorted(c["ck_dist"].items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1])))) + ".")},
        {"id": "forest", "name": "숲 세분 (forest_kind)",
         "rule": ("cover 가 숲이고 도엽 통계 칸에만 붙인다: 칸 비율 활엽수림·침엽수림·혼효림 가운데 가장 큰 것(같은 수면 이 순서). "
                  "ESA 보완 칸은 숲 종류가 없어 null. 결과: " + ", ".join(f"{TR.SHARE_KO[k]} {c['fk_dist'].get(k, 0)}칸" for k in TR.FOREST_KINDS)
                  + f", ESA 보완 숲 칸(종류 없음) {c['esa_forest']}칸.")},
    ]
    st = c["stats"]
    meta = {"source": CS.SOURCE_NAME, "source_key": CS.SOURCE_KEY, "label": f"기후에너지환경부 세분류 토지피복지도 도엽 통계 ({c['sheets_year']}년 기준)",
            "fallback": "ESA WorldCover 2021 v200 (CC BY 4.0, 도엽 통계가 닿지 않는 칸만, 대체 자료)", "method": method,
            "table_title": f"피복 (기후에너지환경부 세분류 토지피복지도 도엽 통계 {c['sheets_year']}년 기준 · 두 판 공용)",
            "legend": (f"피복: {CS.SOURCE_NAME}의 도엽(1:5,000, 약 6 km²)별 세분류 면적을 칸에 나눈 값. 숲은 활엽·침엽·혼효, 농경지는 논·밭·과수원·시설재배지로 나뉜다. "
                       + (f"도엽 통계가 닿지 않는 {c['src']['esa']}칸만 대체 자료 ESA WorldCover 2021 (CC BY 4.0)." if c["src"]["esa"] else "")),
            "summary": (f"도엽 통계 칸 {c['src']['me']}개의 칸 평균 비율: 숲 {c['share_w']['forest'] * 100:.1f}% (활엽 {c['share_w']['broadleaf'] * 100:.1f} · "
                        f"침엽 {c['share_w']['conifer'] * 100:.1f} · 혼효 {c['share_w']['mixed'] * 100:.1f}), 농경지 {c['share_w']['crop'] * 100:.1f}% "
                        f"(논 {c['share_w']['paddy'] * 100:.1f} · 밭 {c['share_w']['field'] * 100:.1f} · 과수원 {c['share_w']['orchard'] * 100:.1f} · "
                        f"시설재배지 {c['share_w']['greenhouse'] * 100:.1f}), 시가지 {c['share_w']['built'] * 100:.1f}%, 초지 {c['share_w']['grass'] * 100:.1f}%, "
                        f"습지 {c['share_w']['wetland'] * 100:.1f}%, 나지 {c['share_w']['bare'] * 100:.1f}%, 수면 {c['share_w']['water'] * 100:.1f}% — 분모는 칸에 나눈 "
                        "세분류 면적 합(해양수·갯벌 제외)."),
            "bias_note": c["bias"], "weighted_share": c["share_w"], "forest_weighted": c["share_w"]["forest"],
            "dist": c["cover_dist"], "src": c["src"], "esa_cells": c["esa_list"], "esa_counties": dict(c["esa_sgg"].most_common()),
            "no_cover_cells": c["no_cover"], "crop": {f"{s}|{k}": v for (s, k), v in c["ck_dist"].items()}, "forest": dict(c["fk_dist"]),
            "sheets": {k: v for k, v in c["sheets"].items()}, "index_check": {k: v for k, v in ix.items() if k != "rel"},
            "special_offsets_min": {k: list(v) for k, v in CS.SPECIAL_MIN.items()}, "alloc": c["alloc"], "class_map": cmap,
            "stats": {"source": CS.STATS_NAME, "source_key": CS.STATS_SOURCE_KEY, "year": st["year"], "file": st["rec"]["file"], "sha256": st["rec"]["sha256"],
                      "units": st["units"], "unmatched": st["miss"]},
            "compare": {"nation": nat, "summary": c["compare"]["summary"], "tolerance": c["compare"]["tolerance"],
                        "rule": ("칸 쪽은 대한민국 육지 칸(피복이 있는 칸)의 칸 평균 비율(칸 넓이가 같아 넓이 가중과 같다), 통계 쪽은 해양수·갯벌을 뺀 합 대비 비율. "
                                 "시군구별 표는 data/build/landcover_compare.json.")}}
    return tables, meta


def project_geom(g):
    return shapely.transform(g, lambda xy: np.column_stack(TO5179.transform(xy[:, 0], xy[:, 1])))


def read_ne(name):
    z = zipfile.ZipFile(raw("naturalearth", f"ne_10m_{name}.zip"))
    base = [n for n in z.namelist() if n.endswith(".shp")][0][:-4]
    r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                         shx=io.BytesIO(z.read(base + ".shx")), encoding="utf-8")
    flds = [f[0] for f in r.fields[1:]]
    for sr in r.iterShapeRecords():
        yield shape(sr.shape.__geo_interface__), dict(zip(flds, sr.record))


def short_sido(name):
    """시도 짧은 이름: 규칙으로 만든다 (목록을 손으로 적지 않는다)."""
    m = re.fullmatch(r"(충청|전라|경상)(남|북)도", name)
    if m:
        return m.group(1)[0] + m.group(2)
    for suf in ("통합특별시", "특별자치시", "특별자치도", "특별시", "광역시", "도"):
        if name.endswith(suf):
            return name[: -len(suf)]
    return name


def county_name(sggnm):
    m = re.fullmatch(r"(.+시)(.+구)", sggnm)
    return f"{m.group(1)} {m.group(2)}" if m else sggnm


def main():
    # ---------------- 격자 ----------------
    lons = np.concatenate([np.linspace(LON0, LON1, 200), np.full(200, LON1), np.linspace(LON1, LON0, 200), np.full(200, LON0)])
    lats = np.concatenate([np.full(200, LAT0), np.linspace(LAT0, LAT1, 200), np.full(200, LAT1), np.linspace(LAT1, LAT0, 200)])
    ex, ny = TO5179.transform(lons, lats)
    x0, x1 = ex.min() - MARGIN, ex.max() + MARGIN
    y0, y1 = ny.min() - MARGIN, ny.max() + MARGIN   # y0 남쪽, y1 북쪽
    wu, hu = (x1 - x0) / MPU, (y1 - y0) / MPU
    W = math.sqrt(3) * R_U
    cols = math.ceil(wu / W - 0.5)
    rows = math.ceil((hu - 2 * R_U) / (1.5 * R_U)) + 1
    G = Grid(cols, rows, R_U)
    N = G.n
    origin = (round(x0, 1), round(y1, 1))   # 좌상단 (EPSG:5179 E, N)
    log(f"격자 {cols} 열 × {rows} 행 = {N} 칸, 원점 {origin}")

    def u2m(ux, uy):
        return origin[0] + np.asarray(ux) * MPU, origin[1] - np.asarray(uy) * MPU

    def m2u(e, n):
        return (np.asarray(e) - origin[0]) / MPU, (origin[1] - np.asarray(n)) / MPU

    centers = np.array([G.center(i) for i in range(N)])  # 화면 단위
    offs = np.array(G.sample_offsets())                  # 37 × 2
    S = len(offs)
    spx = (centers[:, None, 0] + offs[None, :, 0]).ravel()
    spy = (centers[:, None, 1] + offs[None, :, 1]).ravel()
    sme, smn = u2m(spx, spy)

    # ---------------- 행정동 ----------------
    log("행정동 경계 읽는 중")
    gj = load_json(raw("boundary", "HangJeongDong_ver20261001.geojson"))
    feats = gj["features"]
    dong_geoms = []
    dongs = []
    sido_name, sggnm = {}, {}
    for f in feats:
        p = f["properties"]
        for k in ("adm_cd2", "sgg", "sido", "sidonm", "sggnm", "adm_nm"):
            if not isinstance(p.get(k), str):
                raise ValueError(f"행정동 속성 형식 오류: {p}")
        if not (re.fullmatch(r"\d{10}", p["adm_cd2"]) and p["adm_cd2"][:5] == p["sgg"] and p["sgg"][:2] == p["sido"]):
            raise ValueError(f"행정동 코드 불일치: {p}")
        sido_name[p["sido"]] = p["sidonm"]
        sggnm[p["sgg"]] = p["sggnm"]
        dong_geoms.append(shape(f["geometry"]))
        dongs.append({"code": p["adm_cd2"], "sgg": p["sgg"], "sido": p["sido"], "name": p["adm_nm"]})
    del gj, feats
    dong_geoms = project_geom(np.array(dong_geoms, dtype=object))
    dong_geoms = shapely.make_valid(dong_geoms)
    areas = shapely.area(dong_geoms)
    simp = shapely.simplify(dong_geoms, 15.0, preserve_topology=True)
    sidos = sorted({d["sido"] for d in dongs})
    sggs = sorted({d["sgg"] for d in dongs})
    sgg_sido = {d["sgg"]: d["sido"] for d in dongs}
    log(f"시도 {len(sidos)}개, 시군구 {len(sggs)}개, 행정동 {len(dongs)}개")
    if (len(sidos), len(sggs)) != (16, 256):
        log("주의: 시도·시군구 수가 설계서(16, 256)와 다름")
    sido_idx = {c: i for i, c in enumerate(sidos)}
    sgg_idx = {c: i for i, c in enumerate(sggs)}
    dong_sido = np.array([sido_idx[d["sido"]] for d in dongs])
    dong_sgg = np.array([sgg_idx[d["sgg"]] for d in dongs])

    log(f"표본점 {len(sme):,}개 판정 중 (STRtree)")
    pts = shapely.points(sme, smn)
    tree = shapely.STRtree(simp)
    pi, gi = tree.query(pts, predicate="intersects")
    samp = np.full(len(pts), -1, dtype=np.int32)
    samp[pi[::-1]] = gi[::-1]  # 경계 위 점은 번호가 작은 동으로
    samp = samp.reshape(N, S)

    # 외국 땅
    mapbox_m = box(x0, y0, x1, y1)
    fgeoms = []
    for g, rec in read_ne("admin_0_countries"):
        if rec.get("ADM0_A3") in FOREIGN:
            pg = project_geom(g.intersection(box(120, 30, 136, 42)))
            pg = pg.intersection(mapbox_m)
            if not pg.is_empty:
                fgeoms.append(pg)
                log(f"외국 땅: {FOREIGN[rec['ADM0_A3']]}")
    ftree = shapely.STRtree(fgeoms)
    fpi, _ = ftree.query(pts, predicate="intersects")
    in_foreign = np.zeros(len(pts), bool)
    in_foreign[fpi] = True
    in_foreign = in_foreign.reshape(N, S) & (samp < 0)

    kr = samp >= 0
    n_kr = kr.sum(1)
    n_fg = in_foreign.sum(1)
    land_frac = n_kr / S

    owner = np.full(N, -1, np.int32)
    county = np.full(N, -1, np.int32)
    foreign = np.zeros(N, np.int8)
    half = S // 2 + 1  # 19
    is_kr = n_kr >= half
    # 휴전선 부근: 대한민국 땅과 북한 땅을 합쳐 과반이면 바다로 두지 않는다 (둘 중 많은 쪽)
    mixed = ~is_kr & (n_kr + n_fg >= half)
    is_kr |= mixed & (n_kr >= n_fg)
    is_fg = ~is_kr & ((n_fg >= half) | (mixed & (n_fg > n_kr)))
    foreign[is_fg] = 1
    n_mixed = int(mixed.sum())

    def assign(i):
        ds = samp[i][samp[i] >= 0]
        sid = np.bincount(dong_sido[ds], minlength=len(sidos))
        o = int(sid.argmax())
        sg = np.bincount(dong_sgg[ds][dong_sido[ds] == o], minlength=len(sggs))
        return o, int(sg.argmax())

    for i in np.nonzero(is_kr)[0]:
        owner[i], county[i] = assign(i)

    # ---------------- 작은 섬 예외 ----------------
    # 행정동을 녹여 붙인 '땅덩어리' 단위로 판정한다 (해안의 자투리 조각을 섬으로 오인하지 않게)
    log("땅덩어리(섬) 만드는 중")
    mass = shapely.union_all(shapely.buffer(simp, 2.0))
    part_geoms = np.array([p for p in getattr(mass, "geoms", [mass]) if p.area > 0], dtype=object)
    mrp = shapely.point_on_surface(part_geoms)
    mdi, mgi = tree.query(mrp, predicate="intersects")
    mass_dong = np.full(len(part_geoms), -1, np.int64)
    mass_dong[mdi[::-1]] = mgi[::-1]
    for k in np.nonzero(mass_dong < 0)[0]:  # 대표점이 경계 틈에 떨어진 경우 가장 가까운 동
        mass_dong[k] = int(tree.query_nearest(mrp[k])[0])
    parts = [(int(mass_dong[k]), part_geoms[k]) for k in range(len(part_geoms))]
    log(f"땅덩어리 {len(parts)}개")
    ptree = shapely.STRtree(part_geoms)
    ppi, pgi = ptree.query(pts, predicate="intersects")
    part_of = np.full(len(pts), -1, np.int64)
    part_of[ppi[::-1]] = pgi[::-1]
    part_of = part_of.reshape(N, S)
    # 조각마다 표본점이 든 칸
    part_cells = {}
    for c, k in zip(*np.nonzero(part_of >= 0)):
        part_cells.setdefault(int(part_of[c, k]), []).append(int(c))
    # 표본점이 하나도 없는 조각은 대표점이 든 칸
    rp = shapely.point_on_surface(part_geoms)
    rpx, rpy = m2u(shapely.get_x(rp), shapely.get_y(rp))
    rp_cell = G.point_to_cell_np(rpx, rpy)
    land = owner >= 0
    # 조각 → 사라진 섬 후보 (어느 육지 칸에도 표본점이 없는 조각)
    cand = {}  # 칸 -> [조각]
    for k, (di, part) in enumerate(parts):
        cells = part_cells.get(k) or [int(rp_cell[k])]
        if any(land[c] for c in cells):
            continue
        cnt = {}
        for c in cells:
            cnt[c] = cnt.get(c, 0) + 1
        best = max(cnt, key=lambda c: (cnt[c], -c))
        cand.setdefault(best, []).append(k)
    # 거리 판정용: 기존 육지 칸까지 칸 거리
    def hex_dist_to_land(c, maxd=4):
        seen, frontier = {c}, [c]
        for d in range(1, maxd + 1):
            nxt = []
            for f in frontier:
                for nb in G.neighbors(f):
                    if nb not in seen:
                        if land[nb]:
                            return d
                        seen.add(nb)
                        nxt.append(nb)
            frontier = nxt
        return maxd + 1
    ISLAND_AREA = 0.5e6   # 0.5 km² 이상 섬(무리)
    ISOLATED = 3          # 가장 가까운 육지 칸까지 3칸 이상이면 0.1 km² 까지
    ISOLATED_AREA = 0.1e6
    promoted = []
    # 넓은 섬부터, 이미 육지(살린 섬 포함)와 맞닿지 않은 칸만 살린다: '칸 주변에 다른 육지 칸이 없는 섬'
    order = sorted(cand.items(), key=lambda kv: -sum(parts[k][1].area for k in kv[1]))
    for c, ks in order:
        a = sum(parts[k][1].area for k in ks)
        dist = hex_dist_to_land(c)
        if dist >= 2 and (a >= ISLAND_AREA or (dist >= ISOLATED and a >= ISOLATED_AREA)):
            di = max(ks, key=lambda k: parts[k][1].area)
            di = parts[di][0]
            owner[c] = dong_sido[di]
            county[c] = dong_sgg[di]
            foreign[c] = 0
            land[c] = True
            promoted.append({"cell": int(c), "dong": dongs[di]["name"], "area_km2": round(a / 1e6, 3),
                             "dist": int(dist)})
    land = owner >= 0
    log(f"작은 섬 예외로 살린 칸 {len(promoted)}개")
    for p in promoted:
        log("   ", p)

    # ---------------- 모든 시군구가 칸을 갖게 ----------------
    missing_before = [sggs[j] for j in range(len(sggs)) if not (county == j).any()]
    fixes = []
    sgg_of_samp = np.where(samp >= 0, dong_sgg[np.clip(samp, 0, None)], -1)
    def cand_cells(j, visited):
        cnt = (sgg_of_samp == j).sum(1)
        return [(int(c), int(cnt[c])) for c in np.argsort(-cnt, kind="stable") if cnt[c] > 0 and int(c) not in visited]

    def find_path(j, visited, depth):
        """j 가 받을 칸을 찾는다. 상대가 칸을 잃게 되면 상대도 다른 칸을 받도록 사슬로 찾는다 (깊이 제한)."""
        cs = cand_cells(j, visited)
        for c, n in cs:
            prev = county[c]
            if prev < 0 or (county == prev).sum() >= 2:
                return [(c, j, n)]
        if depth == 0:
            return None
        for c, n in cs:
            sub = find_path(county[c], visited | {c}, depth - 1)
            if sub:
                return sub + [(c, j, n)]
        return None

    for code in missing_before:
        j = sgg_idx[code]
        path = find_path(j, set(), 3)
        if not path:
            log(f"보정 실패: {code} {sggnm[code]} 후보 {cand_cells(j, set())[:4]}")
            continue
        for c, jj, n in path:
            prev = county[c]
            owner[c] = sido_idx[sgg_sido[sggs[jj]]]
            county[c] = jj
            foreign[c] = 0
            fixes.append({"sgg": sggs[jj], "cell": int(c), "points": n, "from": sggs[prev] if prev >= 0 else None})
    land = owner >= 0
    log(f"칸이 없던 시군구 {len(missing_before)}개 -> 보정 {len(fixes)}건: {fixes}")

    # ---------------- 5b: 지형 보강 전 육지 칸·소유 시군구 대조 ----------------
    # 지형 보강은 칸의 피복·물 속성만 바꾼다. 보강 전 world.json(처음 한 번 스냅샷)과 육지 칸·소유 시도·시군구가 같아야 한다.
    base_path = build("land_baseline.json")
    if not os.path.exists(base_path) and os.path.exists(site("world.json")):
        old = load_json(site("world.json"))
        save_json(base_path, {"made_from": "5b 지형 보강 전 site/data/world.json (" + str(old.get("version")) + ")",
                              "grid": old["grid"], "hex_km2": old["hex_km2"],
                              "counties": [c["code"] for c in old["counties"]],
                              "owner": old["owner"], "county": old["county"]})
        log("보강 전 육지 칸 스냅샷을 만들었다: data/build/land_baseline.json")
    if os.path.exists(base_path):
        bl = load_json(base_path)
        same = (bl["grid"]["cols"] == cols and bl["grid"]["rows"] == rows and bl["counties"] == sggs
                and bl["owner"] == owner.tolist() and bl["county"] == county.tolist())
        if not same:
            nd = sum(1 for a, b in zip(bl["owner"], owner.tolist()) if a != b)
            raise ValueError(f"육지 칸·소유 시군구가 보강 전과 다름 (소유가 다른 칸 {nd}개) — 지형 보강은 이것을 바꾸면 안 된다")
        log(f"육지 칸·소유 시군구가 보강 전과 같음 (육지 {int(land.sum())}칸)")

    # ---------------- 표고 ----------------
    log("SRTM30+ 읽는 중")
    z = np.loadtxt(raw("terrain", "srtm30plus_korea.csv"), delimiter=",", skiprows=2)
    if z.shape[1] != 3 or not (np.isfinite(z).all()):
        raise ValueError("SRTM CSV 형식 오류")
    ze, zn = TO5179.transform(z[:, 1], z[:, 0])
    zux, zuy = m2u(ze, zn)
    zc = G.point_to_cell_np(zux, zuy)
    ok = zc >= 0
    zc, zv = zc[ok], z[ok, 2]
    is_landcell = (owner >= 0) | (foreign == 1)
    pos = zv >= 0
    use = np.where(is_landcell[zc], pos, True)
    cnt = np.bincount(zc[use], minlength=N).astype(float)
    s1 = np.bincount(zc[use], zv[use], minlength=N)
    s2 = np.bincount(zc[use], zv[use] ** 2, minlength=N)
    with np.errstate(invalid="ignore", divide="ignore"):
        elev = s1 / cnt
        sd = np.sqrt(np.maximum(s2 / cnt - elev ** 2, 0))
    # 육지인데 0 m 이상 표본이 없는 칸 (아주 작은 섬, SRTM 범위 밖 북한 땅): 표고 '자료 없음', 기복은 평지로 둔다
    nos = is_landcell & (cnt == 0)
    elev[nos] = np.nan
    sd[nos] = np.nan
    log(f"표고 자료가 없는 육지 칸 {int(nos.sum())}개 (대한민국 {int((nos & (owner >= 0)).sum())})")
    allc = np.bincount(zc, minlength=N)
    alls = np.bincount(zc, zv, minlength=N)
    sea_mean = np.where(allc > 0, alls / np.maximum(allc, 1), np.nan)
    # SRTM30+ 범위(124–132°E, 33–39°N) 밖 바다 칸은 수심 '자료 없음'(null). 물 분류만 이웃 칸에서 물려받는다.
    no_data = np.isnan(sea_mean) & ~is_landcell
    n_nodata = int(no_data.sum())
    elev = np.where(is_landcell, elev, sea_mean)
    log(f"표본 수/칸: 중앙값 {np.median(allc[allc > 0]):.0f}")

    # ---------------- 물 ----------------
    water = np.zeros(N, np.int8)
    adj_land = np.zeros(N, bool)
    for i in range(N):
        if not is_landcell[i]:
            adj_land[i] = any(is_landcell[nb] for nb in G.neighbors(i))
    sea = ~is_landcell
    deep = sea & (sea_mean < -200) & ~adj_land
    water[sea] = 2
    water[deep] = 1
    # 수심 자료가 없는 칸: 육지 옆이면 연안, 아니면 가장 가까운(이웃을 따라 퍼뜨린) 자료 있는 칸의 분류
    known = ~no_data
    for i in np.nonzero(no_data & adj_land)[0]:
        known[i] = True  # water 는 이미 2(연안)
    for _ in range(200):
        todo = np.nonzero(~known)[0]
        if len(todo) == 0:
            break
        upd = {}
        for i in todo:
            ks = [water[j] for j in G.neighbors(i) if known[j] and not is_landcell[j]]
            if ks:
                upd[i] = max(set(ks), key=ks.count)
        for i, v in upd.items():
            water[i] = v
            known[i] = True
    log(f"SRTM 범위 밖이라 수심 자료가 없는 바다 칸 {n_nodata}개 (물 분류만 이웃에서 물려받음)")
    # 호수·저수지: OpenStreetMap 수면(대체 자료). 대한민국 육지 칸의 표본점 37개 중 과반(19개)이 수면 안이면 water=3.
    # 소유 시도·시군구와 넓이 집계는 그대로 둔다 (육지 칸 수에 그대로 든다).
    log("호수·저수지 (lakes.geojson) 읽는 중")
    lk_geom, lk_recs, _ = TR.read_vector("lakes.geojson")
    lk_geom = shapely.make_valid(lk_geom)
    lk_area = shapely.area(lk_geom)
    ltree = shapely.STRtree(lk_geom)
    lpi, lgi = ltree.query(pts, predicate="intersects")
    inl = np.zeros(len(pts), bool)
    inl[lpi] = True
    lake_pts = inl.reshape(N, S).sum(1)
    lk = (lake_pts >= half) & (owner >= 0)
    water[lk] = 3
    n_lake_cells = int(lk.sum())
    # 어느 수면이 호수 칸을 만들었는지 (칸의 수면 표본점이 가장 많이 든 수면)
    lake_of_cell = {}
    pc = collections.Counter()
    for p_, g_ in zip(lpi, lgi):
        c_ = int(p_ // S)
        if lk[c_]:
            pc[(c_, int(g_))] += 1
    for (c_, g_), n_ in sorted(pc.items(), key=lambda kv: (kv[0][0], -kv[1], kv[0][1])):
        lake_of_cell.setdefault(c_, g_)

    def clean_name(nm):
        nm = (nm or "").strip()
        return re.sub(r"\s*\([A-Za-z][A-Za-z\s\-']*\)$", "", nm)  # 'OO호 (Romanized)' 의 로마자 덧붙임만 뗀다

    lake_draw, lake_labels = [], []
    seen_label = {}
    for k in np.argsort(-lk_area, kind="stable"):
        a = float(lk_area[k])
        if a < LAKE_DRAW_KM2 * 1e6:
            break
        g = lk_geom[k].simplify(LAKE_SIMPLIFY_M, preserve_topology=True).intersection(mapbox_m)
        rings = []
        for poly in getattr(g, "geoms", [g]):
            if poly.is_empty or poly.geom_type != "Polygon":
                continue
            for ring in [poly.exterior, *poly.interiors]:
                xs, ys = m2u(*np.array(ring.coords).T)
                if len(xs) >= 4:
                    rings.append([v for xy in zip(xs, ys) for v in (round(float(xy[0]), 1), round(float(xy[1]), 1))])
        nm = clean_name(lk_recs[k].get("name"))
        if rings:
            lake_draw.append({"name": nm or None, "area_km2": round(a / 1e6, 2), "rings": rings})
        if nm and a >= LAKE_LABEL_KM2 * 1e6 and nm not in seen_label:
            rp_ = lk_geom[k].point_on_surface()
            lx, ly = m2u(rp_.x, rp_.y)
            seen_label[nm] = True
            lake_labels.append({"name": nm, "x": round(float(lx), 1), "y": round(float(ly), 1), "area_km2": round(a / 1e6, 1),
                                "kind": lk_recs[k].get("kind")})
    lake_cell_area = {}
    for c_, g_ in lake_of_cell.items():
        nm = clean_name(lk_recs[g_].get("name")) or "(이름 없음)"
        lake_cell_area[nm] = lake_cell_area.get(nm, 0) + 1
    log(f"수면 {len(lk_geom)}면 (0.1 km² 이상), 호수 칸 {n_lake_cells}개 "
        f"({n_lake_cells * 1.5 * math.sqrt(3) * (R_M / 1000) ** 2:,.0f} km²), 그릴 폴리곤 {len(lake_draw)}면, 이름표 {len(lake_labels)}개")
    log(f"   호수 칸을 만든 수면: {dict(sorted(lake_cell_area.items(), key=lambda kv: -kv[1]))}")

    # ---------------- 기복 ----------------
    ksd = sd[land]
    ksd = ksd[~np.isnan(ksd)]  # 표고 자료 없는 칸은 기준값 계산에서 뺀다
    t1 = float(np.quantile(ksd, TARGET[0]))
    t2 = float(np.quantile(ksd, TARGET[0] + TARGET[1]))
    T1, T2 = int(round(t1 / 5) * 5), int(round(t2 / 5) * 5)
    PEAK = 1000
    relief = np.zeros(N, np.int8)
    lc = is_landcell
    relief[lc & (sd >= T1)] = 1
    relief[lc & (sd >= T2)] = 2
    relief[lc & (elev >= PEAK)] = 3
    dist = [int(((relief == k) & land).sum()) for k in range(4)]
    nl = int(land.sum())
    pct = [round(100 * d / nl, 1) for d in dist]
    draft = [int(((sd[land] < 60)).sum()), int(((sd[land] >= 60) & (sd[land] < 180)).sum()), int((sd[land] >= 180).sum())]
    log(f"기복 기준값: 구릉 {T1} m, 산 {T2} m, 고봉 평균 {PEAK} m. 분포 {dist} ({pct} %)")
    log(f"초안 기준(60/180 m) 분포였다면 {draft}")

    counties = [{"code": c, "name": county_name(sggnm[c]), "sido": sgg_sido[c]} for c in sggs]
    states_l = [{"code": c, "name": sido_name[c], "short": short_sido(sido_name[c])} for c in sidos]
    land_idx = np.nonzero(land)[0]

    # ---------------- 토지피복 (두 판 공용): 기후에너지환경부 세분류 토지피복지도 도엽 통계 (lib/cover_sheets.py) ----------------
    # 도엽마다 해양수·갯벌을 뺀 세분류 면적을, 도엽과 칸이 겹치는 대한민국 행정경계(행정동) 안 넓이에 비례해 칸에 나눈다.
    # 행정경계와 겹치지 않는 도엽은 도엽 넓이에 비례해 나눈다. 도엽 통계가 하나도 닿지 않는 육지 칸만 ESA WorldCover 로 채우고 'esa' 로 적는다.
    # 기후에너지환경부 WMS 그림(data/raw/landcover_me)은 어느 판에서도 읽지 않는다.
    log("토지피복: 세분류 토지피복지도 도엽 통계(15150509) 읽는 중")
    hex_km2_ = 1.5 * math.sqrt(3) * (R_M / 1000) ** 2
    sh_codes, sh_A, sh_rec = CS.read_sheets()
    sh_idx = CS.index_check(sh_codes, sh_A)
    log(f"   {sh_rec['rule']}")
    log(f"   도엽 테두리 검산(면적 합 ÷ GRS80 테두리 넓이 − 1): 중앙값 {sh_idx['median_abs_rel']:.1e}, 95백분위 {sh_idx['p95_abs_rel']:.1e}, "
        f"1e-4 안 {sh_idx['within_1e-4']:,}/{sh_idx['sheets']:,}, 10% 넘게 모자란 도엽(접경·해안에서 잘린 도엽) {sh_idx['short_over_10pct']}")
    if sh_idx["median_abs_rel"] > 1e-4 or sh_idx["within_1e-3"] < 0.95 * sh_idx["sheets"]:
        raise ValueError(f"도엽 테두리 해석이 면적 합과 맞지 않음: {sh_idx}")
    sh_leaf, sh_excl = CS.leaf_matrix(sh_A)
    sh_poly = CS.sheet_polygons(sh_codes, TO5179)
    alloc_cells = np.nonzero(foreign == 0)[0]          # 대한민국 땅·바다 칸 (외국 땅 칸에는 나누지 않는다)
    hex_polys = []
    for i in alloc_cells:
        cxu, cyu = centers[i]
        xs_ = [cxu + R_U * math.cos(math.radians(60 * k - 30)) for k in range(6)]
        ys_ = [cyu + R_U * math.sin(math.radians(60 * k - 30)) for k in range(6)]
        ex_, ny_ = u2m(xs_, ys_)
        hex_polys.append(shapely.Polygon(list(zip(ex_, ny_))))
    hex_polys = np.array(hex_polys, dtype=object)
    a_si, a_ci, a_w, a_mode, a_land = CS.allocate(sh_poly, hex_polys, alloc_cells, simp)
    L_ = len(CS.LEAVES)
    alloc = np.zeros((N, L_))
    np.add.at(alloc, a_ci, a_w[:, None] * sh_leaf[a_si])
    alloc_tot = alloc.sum(1)
    sheet_cells = land & (alloc_tot > 0)
    w_sum = np.zeros(len(sh_codes))
    np.add.at(w_sum, a_si, a_w)
    on_land_w = np.zeros(len(sh_codes))
    np.add.at(on_land_w, a_si, np.where(land[a_ci], a_w, 0.0))
    leaf_in_land = float((sh_leaf * on_land_w[:, None]).sum())
    alloc_rec = {"pairs": int(len(a_si)), "sheets_by_land": int((a_mode == 0).sum()), "sheets_by_area": int((a_mode == 1).sum()),
                 "sheets_no_cell": int((w_sum <= 0).sum()), "leaf_km2": round(float(sh_leaf.sum()) / 1e6, 1),
                 "leaf_in_land_cells_km2": round(leaf_in_land / 1e6, 1), "excluded_km2": round(float(sh_excl.sum()) / 1e6, 1)}
    log(f"   도엽 × 칸 {alloc_rec['pairs']:,}쌍, 행정경계로 나눈 도엽 {alloc_rec['sheets_by_land']:,}, 도엽 넓이로 나눈 도엽 {alloc_rec['sheets_by_area']}, "
        f"칸에 닿지 않은 도엽 {alloc_rec['sheets_no_cell']}; 나눈 면적 {alloc_rec['leaf_km2']:,} km² 가운데 대한민국 육지 칸 {alloc_rec['leaf_in_land_cells_km2']:,} km²")

    # ESA WorldCover (도엽 통계가 닿지 않는 육지 칸 보완): 250 m 최빈값 셀을 칸별로 센다
    lc, lc_meta, lc_tags = TR.read_raster("landcover.tif")
    esa_names = TR.esa_classes_from_tags(lc_tags)
    nod = lc_meta["nodata"] if lc_meta["nodata"] is not None else 0
    lut = np.full(256, -1, np.int16)
    for code, key in TR.ESA_TO_COVER.items():
        lut[code] = TR.COVER_KEYS.index(key)
    rr_, cc_ = np.nonzero(lc != nod)
    vals = lc[rr_, cc_]
    if (lut[vals] < 0).any():
        raise ValueError(f"landcover.tif 에 분류표 밖 값: {sorted(set(vals[lut[vals] < 0].tolist()))}")
    pe, pn = TR.raster_centers(lc_meta, rr_, cc_)
    pcell = G.point_to_cell_np(*m2u(pe, pn))
    okp = pcell >= 0
    K = len(TR.COVER_KEYS)
    esa_cnt = np.zeros((N, K), np.int32)
    np.add.at(esa_cnt, (pcell[okp], lut[vals[okp]]), 1)
    esa_cnt[~land] = 0
    esa_n = esa_cnt.sum(1)
    esa_use = land & ~sheet_cells & (esa_n > 0)
    del lc, rr_, cc_, vals, pe, pn, pcell

    SK = CS.SHARE_KEYS
    q_ = {k: CS.LEAVES.index(k) for k in CS.LEAVES}
    cover_share = np.full((N, len(SK)), np.nan)
    t_ = np.where(alloc_tot > 0, alloc_tot, 1.0)
    for k in SK:
        if k == "forest":
            v_ = alloc[:, [q_["broadleaf"], q_["conifer"], q_["mixed"]]].sum(1)
        elif k == "crop":
            v_ = alloc[:, [q_[x] for x in ("paddy", "field", "orchard", "greenhouse", "crop_other")]].sum(1)
        else:
            v_ = alloc[:, q_[k]]
        cover_share[sheet_cells, SK.index(k)] = (v_ / t_)[sheet_cells]
    for k, key in enumerate(TR.COVER_KEYS):
        cover_share[esa_use, SK.index(key)] = esa_cnt[esa_use, k] / esa_n[esa_use]
    major = cover_share[:, [SK.index(k) for k in TR.COVER_KEYS]]
    cover_id = np.zeros(N, np.int8)            # 0 = 없음, 1.. = COVER_KEYS 순서 + 1 (같은 비율이면 앞쪽: 숲·농경지·시가지·초지·습지·나지·수면)
    has_cov = sheet_cells | esa_use
    cover_id[has_cov] = np.argmax(np.nan_to_num(major[has_cov], nan=-1), axis=1) + 1
    cover_src = np.zeros(N, np.int8)           # 0 없음, 1 도엽 통계(me), 2 esa
    cover_src[sheet_cells] = 1
    cover_src[esa_use] = 2
    no_cover = [int(i) for i in land_idx if not has_cov[i]]
    cover_dist = {TR.COVER_KEYS[k]: int((cover_id == k + 1).sum()) for k in range(K)}
    esa_list = [int(i) for i in np.nonzero(esa_use)[0]]
    src_dist = {"me": int(sheet_cells.sum()), "esa": len(esa_list), "없음": len(no_cover)}
    esa_sgg = collections.Counter(sggs[county[i]] for i in esa_list)
    log(f"   cover_src {src_dist}; ESA 보완 칸 {esa_list} ({', '.join(f'{county_name(sggnm[c])} {n}' for c, n in esa_sgg.most_common())}); 대표 피복 {cover_dist}")

    # 농경지·숲 세분 (대표 피복이 농경지·숲인 도엽 통계 칸만, 같은 수면 앞쪽)
    CK, FK = TR.CROP_KINDS, TR.FOREST_KINDS
    crop_kind, crop_src, forest_kind = {}, {}, {}
    crop_i, forest_i = TR.COVER_KEYS.index("crop") + 1, TR.COVER_KEYS.index("forest") + 1
    for i in land_idx:
        i = int(i)
        if cover_id[i] == crop_i:
            if cover_src[i] == 1:
                sub = [cover_share[i, SK.index(k)] for k in CK]
                crop_kind[i] = CK[int(np.argmax(sub))] if max(sub) > 0 else None
                crop_src[i] = "me" if crop_kind[i] else None
            else:
                crop_kind[i], crop_src[i] = None, None
        elif cover_id[i] == forest_i and cover_src[i] == 1:
            sub = [cover_share[i, SK.index(k)] for k in FK]
            forest_kind[i] = FK[int(np.argmax(sub))]
    ck_dist = collections.Counter((crop_src[i], crop_kind[i]) for i in crop_kind)
    fk_dist = collections.Counter(forest_kind.values())
    log(f"   농경지 칸 {len(crop_kind)}: {dict(ck_dist)}; 숲 칸 세분 {dict((TR.SHARE_KO[k], v) for k, v in fk_dist.items())}")

    # 국가 토지피복 통계(15163128, 공공누리 제1유형)와 대조: 전국·시군구 칸 평균 비율 vs 통계 비율 (화면의 치우침 문장, 검증 C7s 가 같은 값을 다시 낸다)
    st_rows, st_year, st_rec = CS.read_stats()
    st_units, st_miss = CS.stats_units(st_rows, {"states": states_l, "counties": counties})
    cmp_ = CS.compare(cover_share, land_idx, county, sggs, st_rows, st_units)
    share_w = {k: round(float(v), 4) for k, v in CS.cell_mean_shares(cover_share[land_idx][has_cov[land_idx]]).items()}
    log("   칸 평균 vs 국가 토지피복 통계 " + str(st_year) + ": " + ", ".join(f"{nm} {cmp_['nation'][k]['cells_pct']}% / {cmp_['nation'][k]['stats_pct']}%" for k, nm in CS.COMPARE_KEYS)
        + f"; 칸 {CS.TOL['county_min_cells']}개 이상 시군구 {cmp_['summary']['forest']['big_n']}곳 90백분위 "
        + ", ".join(f"{nm} {cmp_['summary'][k]['big_p90_pp']}%p" for k, nm in CS.COMPARE_KEYS) + f"; 통계 행 대응 못 함 {st_miss}")

    # ---------------- 5b: 갯벌 (해양수산부 2011년 1:25,000) ----------------
    log("갯벌 (tidal_flats.geojson) 읽는 중")
    tf_geom, tf_recs, _ = TR.read_vector("tidal_flats.geojson")
    tf_geom = shapely.buffer(shapely.make_valid(tf_geom), 0)
    tf_years = sorted({str(r.get("year")) for r in tf_recs})
    tf_area_raw = float(shapely.area(tf_geom).sum())
    tf_tree = shapely.STRtree(tf_geom)
    cand = np.nonzero(foreign == 0)[0]
    hexes_m = []
    for i in cand:
        cxu, cyu = centers[i]
        xs_ = [cxu + R_U * math.cos(math.radians(60 * k - 30)) for k in range(6)]
        ys_ = [cyu + R_U * math.sin(math.radians(60 * k - 30)) for k in range(6)]
        ex_, ny_ = u2m(xs_, ys_)
        hexes_m.append(shapely.Polygon(list(zip(ex_, ny_))))
    hexes_m = np.array(hexes_m, dtype=object)
    hi_, ti_ = tf_tree.query(hexes_m, predicate="intersects")
    inter = shapely.area(shapely.intersection(hexes_m[hi_], tf_geom[ti_]))
    tidal_m2 = np.zeros(N)
    np.add.at(tidal_m2, cand[hi_], inter)
    hex_m2 = 1.5 * math.sqrt(3) * R_M ** 2
    tidal_share = np.minimum(1.0, tidal_m2 / hex_m2)
    sea_cell = (owner < 0) & (foreign == 0)
    tidal_tile = sea_cell & (tidal_share >= TIDAL_TILE)
    water[tidal_tile] = 4
    # 바다 칸의 시도: 칸 거리로 가장 가까운 대한민국 육지 칸의 시도 (같은 거리면 번호가 작은 육지 칸에서 퍼진 쪽)
    near_sido = np.where(land, owner, -1).astype(np.int32)
    frontier = [int(i) for i in land_idx]
    while frontier:
        nxt = []
        for a_ in frontier:
            for nb in G.neighbors(a_):
                if near_sido[nb] < 0 and foreign[nb] == 0 and not land[nb]:
                    near_sido[nb] = near_sido[a_]
                    nxt.append(nb)
        frontier = nxt
    tidal_by_sido = {}
    for i in np.nonzero(tidal_m2 > 0)[0]:
        nsd = near_sido[i]
        if nsd < 0:
            continue
        e_ = tidal_by_sido.setdefault(sidos[nsd], {"tile_cells": 0, "area_km2": 0.0, "land_cells_touched": 0})
        e_["area_km2"] += float(tidal_m2[i]) / 1e6
        if tidal_tile[i]:
            e_["tile_cells"] += 1
        if land[i]:
            e_["land_cells_touched"] += 1
    for v in tidal_by_sido.values():
        v["area_km2"] = round(v["area_km2"], 1)
    tf_in_cells = float(tidal_m2.sum())
    log(f"   갯벌 폴리곤 {len(tf_geom)}면, 넓이 합 {tf_area_raw / 1e6:,.1f} km² (칸에 든 넓이 {tf_in_cells / 1e6:,.1f} km²), "
        f"갯벌 타일 {int(tidal_tile.sum())}칸, 비율만 저장한 해안 육지 칸 {int((land & (tidal_share > 0)).sum())}, 시도별 {tidal_by_sido}")

    # ---------------- 강 (WAMIS 하천 유로선) ----------------
    log("강 (rivers.geojson) 읽는 중")
    rv_geom, rv_recs, _ = TR.read_vector("rivers.geojson")
    groups = collections.OrderedDict()
    for g, rec in zip(rv_geom, rv_recs):
        grade = rec.get("grade")
        if grade not in RIVER_SIMPLIFY_M:
            raise ValueError(f"하천 등급을 모름: {grade!r}")
        groups.setdefault((grade, (rec.get("name") or "").strip()), []).append((g, rec))
    rivers, river_labels = [], []
    n_nat_raw = sum(1 for r in rv_recs if r.get("grade") == "국가하천")
    n_local_drop = 0
    main_found = []
    for (grade, nm), members in groups.items():
        merged = shapely.line_merge(shapely.multilinestrings([m[0] for m in members])) if len(members) > 1 else members[0][0]
        codes = sorted(str(m[1].get("rivcd")) for m in members)
        is_main = grade == "국가하천" and any(MAIN_STEM.match(c) for c in codes)
        for line in getattr(merged, "geoms", [merged]):
            if line.is_empty:
                continue
            km = line.length / 1000
            if grade == "지방하천" and km < LOCAL_RIVER_KM:
                n_local_drop += 1
                continue
            simp = line.simplify(RIVER_SIMPLIFY_M[grade])
            if not mapbox_m.contains(simp):   # 자르기(overlay)는 자기 교차점에서 선을 끊으므로 범위를 벗어날 때만, 자른 뒤 다시 잇는다
                simp = shapely.line_merge(simp.intersection(mapbox_m))
            for part in getattr(simp, "geoms", [simp]):
                if part.is_empty or part.geom_type != "LineString":
                    continue
                xs, ys = m2u(*np.array(part.coords).T)
                rivers.append({"name": nm, "grade": grade, "tier": 1 if grade == "국가하천" else 2, "len_km": round(km, 1),
                               "main": bool(is_main),
                               "pts": [v for xy in zip(xs, ys) for v in (round(float(xy[0]), 1), round(float(xy[1]), 1))]})
            if is_main:
                main_found.append(nm)
                # 이름표: 선 길이의 1/6, 1/2, 5/6 지점 가운데 대한민국 육지 칸 위인 곳, 방향은 앞뒤 2 km 의 기울기
                for f_ in (1 / 6, 1 / 2, 5 / 6):
                    p0 = line.interpolate(f_, normalized=True)
                    pa = line.interpolate(max(0.0, line.project(p0) - 2000))
                    pb = line.interpolate(min(line.length, line.project(p0) + 2000))
                    lx, ly = m2u(p0.x, p0.y)
                    ci = G.point_to_cell(float(lx), float(ly))
                    if ci < 0 or not land[ci]:
                        continue
                    ax, ay = m2u(pa.x, pa.y)
                    bx, by = m2u(pb.x, pb.y)
                    ang = math.degrees(math.atan2(float(by - ay), float(bx - ax)))
                    if ang > 90:
                        ang -= 180
                    if ang < -90:
                        ang += 180
                    river_labels.append({"name": nm, "x": round(float(lx), 1), "y": round(float(ly), 1), "angle": round(ang, 1)})
    n_pts_r = sum(len(r["pts"]) // 2 for r in rivers)
    log(f"   강 선 등급별: {dict(collections.Counter(r['grade'] for r in rivers))}")
    log(f"강 선 {len(rivers)}개 ({n_pts_r:,}점): 국가하천 원자료 {n_nat_raw}건 -> 이름 {len({r['name'] for r in rivers if r['tier'] == 1})}개, "
        f"지방하천 {LOCAL_RIVER_KM:.0f} km 이상 {len({(r['name'], r['len_km']) for r in rivers if r['tier'] == 2})}선 "
        f"(짧아서 뺀 선 {n_local_drop}). 대권역 본류: {main_found}, 이름표 {len(river_labels)}개")

    # ---------------- 시도 이름표 ----------------
    labels = {}
    for si, sc in enumerate(sidos):
        cells = set(np.nonzero(owner == si)[0].tolist())
        best = []
        seen = set()
        for c in cells:
            if c in seen:
                continue
            comp, stack = [], [c]
            seen.add(c)
            while stack:
                a = stack.pop()
                comp.append(a)
                for nb in G.neighbors(a):
                    if nb in cells and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
            if len(comp) > len(best):
                best = comp
        P = centers[best]
        cx, cy = P.mean(0)
        ang = 0.0
        if len(best) >= 6:
            cov = np.cov((P - [cx, cy]).T)
            w_, v_ = np.linalg.eigh(cov)
            vx, vy = v_[:, 1]
            ang = math.degrees(math.atan2(vy, vx))
            if ang > 90:
                ang -= 180
            if ang < -90:
                ang += 180
            # 세로로 긴 지역은 글자를 세우지 않고 수평에 가깝게 둔다
            ang = max(-25.0, min(25.0, ang)) if abs(ang) <= 60 else 0.0
        # 위치: 덩어리 안에서 바깥(다른 시도·바다)까지 칸 거리가 가장 먼 칸들 가운데 무게중심에 가장 가까운 칸.
        # 경기처럼 가운데가 빈(서울을 둘러싼) 모양에서도 이름이 자기 땅 위에 놓인다.
        bset = set(best)
        depth = {}
        frontier = [c for c in best if any(nb not in bset for nb in G.neighbors(c)) or len(G.neighbors(c)) < 6]
        for c in frontier:
            depth[c] = 0
        while frontier:
            nxt = []
            for a in frontier:
                for nb in G.neighbors(a):
                    if nb in bset and nb not in depth:
                        depth[nb] = depth[a] + 1
                        nxt.append(nb)
            frontier = nxt
        dmax = max(depth.values())
        # 가장 깊은 칸부터 한 단계 얕은 칸까지 후보로 두고, 무게중심과 가까운 쪽을 고른다
        cand_c = [c for c in best if depth[c] >= max(0, dmax - 1)]
        k = min(cand_c, key=lambda c: ((centers[c] - [cx, cy]) ** 2).sum() / (1 + depth[c]) ** 2)
        cx, cy = centers[k]
        thick = (2 * depth[k] + 1) * W  # 그 자리에서 쓸 수 있는 폭
        name = short_sido(sido_name[sc])
        extent = math.sqrt(len(best)) * W
        size = max(40.0, min(420.0, extent / max(2.0, len(name) * 1.15), 1.6 * thick / max(2.0, len(name) * 1.15)))
        labels[sc] = {"x": round(float(cx), 1), "y": round(float(cy), 1), "angle": round(ang, 1),
                      "size": round(size, 1), "cells": len(best)}

    # ---------------- 저장 ----------------
    hex_km2 = 1.5 * math.sqrt(3) * (R_M / 1000) ** 2
    nl = int(land.sum())
    bias = BIAS_SENTENCE(cmp_, st_year)
    cov_tables, cov_meta = cover_records({
        "esa_names": esa_names, "index": sh_idx, "sheets": {k: v for k, v in sh_rec.items()}, "sheets_year": max(int(y) for y in sh_rec["chosen_base_year"]),
        "no_cover": no_cover, "cover_dist": cover_dist, "src": src_dist, "esa_sgg": esa_sgg, "esa_list": esa_list, "sggnm": sggnm,
        "share_w": share_w, "bias": bias, "ck_dist": ck_dist, "fk_dist": fk_dist,
        "esa_forest": int(((cover_id == forest_i) & (cover_src == 2)).sum()), "compare": cmp_, "alloc": alloc_rec,
        "stats": {"year": st_year, "rec": st_rec, "units": len(st_units), "miss": st_miss}})
    tables = {
        "water": [
            {"id": 0, "name": "육지", "rule": "대한민국 땅이거나 외국 땅인 칸"},
            {"id": 1, "name": "먼바다", "rule": "칸 안 SRTM30+ 평균 수심 200 m 초과이고 육지 칸과 맞닿지 않음"},
            {"id": 2, "name": "연안", "rule": "나머지 바다 (평균 수심 200 m 이내이거나 육지 칸 옆)"},
            {"id": 3, "name": "호수", "rule": (f"대한민국 육지 칸 가운데 표본점 {S}개 중 {half}개 이상이 수면(OpenStreetMap natural=water, 하천·수로·유수지 "
                                              f"표기 제외, 0.1 km² 이상 {len(lk_geom):,}면 — 대체 자료, © OpenStreetMap 기여자, ODbL 1.0) 안인 칸. "
                                              f"{n_lake_cells}칸. 호수 칸도 소유 시도·시군구와 육지 넓이 집계는 그대로 둔다. "
                                              f"그보다 작아 칸이 되지 못하는 수면 가운데 {LAKE_DRAW_KM2:g} km² 이상은 칸 위에 폴리곤으로 그린다"
                                              f"({LAKE_SIMPLIFY_M:.0f} m 허용 오차로 단순화, 호수 칸이 된 수면도 칸 밖으로 뻗은 부분이 보이게 함께 그림). "
                                              f"이름이 있고 {LAKE_LABEL_KM2:g} km² 이상인 수면 {len(lake_labels)}곳은 확대하면 이름표를 단다(이름은 OSM name 필드, "
                                              "로마자 괄호 덧붙임만 뗌).")},
            {"id": 4, "name": "갯벌", "rule": (f"바다·연안 칸 넓이 중 갯벌(해양수산부 1:25,000 연안정보도 갯벌, {', '.join(tf_years)}년 제작, "
                                              f"{len(tf_geom):,}면) 비율이 {TIDAL_TILE * 100:.0f}% 이상인 칸 {int(tidal_tile.sum())}칸. 비율은 칸 육각형과 "
                                              "폴리곤의 교차 넓이로 잰다. 해안 육지 칸은 비율만 저장하고 타일은 바꾸지 않는다. 시도는 칸 거리로 가장 가까운 "
                                              "대한민국 육지 칸의 시도로 정했다(같은 거리면 번호가 작은 육지 칸 쪽).")},
        ],
        "relief": [
            {"id": 0, "name": "평지", "rule": f"칸 안 표고 표준편차 {T1} m 미만"},
            {"id": 1, "name": "구릉", "rule": f"표준편차 {T1} m 이상 {T2} m 미만"},
            {"id": 2, "name": "산", "rule": f"표준편차 {T2} m 이상"},
            {"id": 3, "name": "고봉", "rule": f"칸 평균 표고 {PEAK} m 이상 (표준편차와 무관)"},
            {"id": "note", "name": "기준값의 근거",
             "rule": (f"초안 기준(60 m / 180 m)으로는 대한민국 육지 {nl}칸이 평지:구릉:산 = "
                      f"{draft[0]}:{draft[1]}:{draft[2]} 로 나뉘었다. 목표 35:40:25 에 맞추려고 육지 칸 표준편차의 "
                      f"35·75 백분위({t1:.1f} m, {t2:.1f} m)를 5 m 단위로 반올림해 {T1} m, {T2} m 로 정했다. "
                      f"결과 평지 {dist[0]} · 구릉 {dist[1]} · 산 {dist[2]} · 고봉 {dist[3]} 칸 "
                      f"({pct[0]}·{pct[1]}·{pct[2]}·{pct[3]} %). 표고는 SRTM30+(30초, 약 0.9 km) 표본이라 "
                      "실제 기복보다 작게 잡힌다.")},
        ],
        "cover": cov_tables,
        "notes": [
            f"투영 EPSG:5179. 헥스 외접원 반지름 {R_M:.0f} m = {R_U:.0f} 화면 단위 (1 단위 = {MPU:.0f} m). 칸 넓이 {hex_km2:.2f} km².",
            f"지도 범위: 경도 {LON0}–{LON1}°, 위도 {LAT0}–{LAT1}° 를 투영한 사각형에 여백 {MARGIN / 1000:.0f} km. 격자 {cols}×{rows}.",
            f"칸마다 표본점 {S}개(중심 + 육각 고리 3겹, 이웃 칸 표본점과 빈틈·겹침 없이 맞물림)를 찍어 행정동 경계(2026-10-01판)와 맞춘다.",
            f"육지: 표본점 {half}개 이상이 대한민국 행정동 안. 소유 시도는 가장 많은 점이 속한 시도, 시군구는 그 시도 안에서 가장 많은 점이 속한 시군구.",
            f"휴전선 부근 등 대한민국 땅과 외국 땅이 섞인 칸은 둘을 합쳐 {half}개 이상이면 바다로 두지 않고 점이 많은 쪽에 준다 ({n_mixed}칸이 해당).",
            "외국 땅: 대한민국 땅이 아닌 칸 중 Natural Earth 1:10m 국가 경계(북한·중국·일본) 안의 점이 과반. 지형만 그리고 통계는 싣지 않는다.",
            (f"작은 섬 예외: 행정동을 녹여 붙인 땅덩어리 가운데 어느 육지 칸에도 표본점이 들지 않아 과반 규칙으로 사라지는 섬은, "
             f"넓은 것부터 차례로, 그 칸이 다른 육지 칸(먼저 살린 섬 포함)과 맞닿지 않고 섬 넓이 합이 {ISLAND_AREA / 1e6:.1f} km² 이상"
             f"(가장 가까운 육지 칸에서 {ISOLATED}칸 이상 떨어진 외딴 섬은 {ISOLATED_AREA / 1e6:.1f} km² 이상)이면 표본점 1개 이상으로 "
             f"그 칸을 육지로 둔다. 섬별 인구 자료가 없어 '유인도' 조건 대신 넓이·거리로 판정했다. {len(promoted)}칸 적용: "
             + ", ".join(f"{p['dong']}({p['area_km2']} km²)" for p in promoted) + "."),
            ("칸이 없는 시군구 보정: " + ("해당 없음." if not missing_before else
             f"{len(missing_before)}개 시군구({', '.join(county_name(s) for s in missing_before)})가 칸을 갖지 못해, 그 시군구 표본점이 가장 많은 칸을 넘겨주었다 (넘겨주는 쪽이 칸을 잃지 않는 범위에서).")),
            (f"강: WAMIS 하천 유로선(국가하천 {n_nat_raw}건, 지방하천 {len(rv_recs) - n_nat_raw:,}건)으로 Natural Earth 강을 교체했다. "
             "등급과 이름이 같은 선은 끝점이 맞닿으면 하나로 이어 붙인다(떨어진 같은 이름 하천은 따로 둔다). 국가하천은 전부 전국 화면부터 그린다. "
             f"지방하천은 길이 분포(중앙값 6.8 km, 90백분위 18.2 km, 20 km 이상 324건)를 보고 이어 붙인 선이 {LOCAL_RIVER_KM:.0f} km 이상인 것만 "
             f"확대했을 때 그린다. 선은 EPSG:5179 에서 국가하천 {RIVER_SIMPLIFY_M['국가하천']:.0f} m·지방하천 {RIVER_SIMPLIFY_M['지방하천']:.0f} m "
             "허용 오차로 단순화했다. 하천코드가 '대권역 번호 + 000010'(대권역 본류)인 국가하천 — " + "·".join(main_found)
             + " — 은 확대하면 이름(원자료 name 필드)을 강 위에 적는다. 북한 구간은 원자료에 있는 만큼만 그린다. WAMIS 유로선의 공공누리 유형은 확인하지 못했다."),
            (f"표고: SRTM30+ 칸 안 표본의 평균. 육지 칸은 0 m 이상 표본만 쓴다. 바다 칸은 평균 수심(음수). "
             f"SRTM30+ 받은 범위(124–132°E, 33–39°N) 밖 바다 {n_nodata}칸은 수심이 '자료 없음'이고, 물 분류만 이웃 칸에서 물려받았다. "
             f"0 m 이상 표본이 없는 육지 {int(nos.sum())}칸(작은 섬, 39°N 북쪽 북한 땅)은 표고 '자료 없음', 기복은 평지로 둔다."),
        ],
    }
    # 칸별 피복 비율: 육지 칸(owner >= 0)만 칸 번호 오름차순으로, 정수 % (정확한 값은 data/build/terrain_cache.npz)
    cs_pct = {key: [None if np.isnan(cover_share[i, k]) else int(round(100 * cover_share[i, k])) for i in land_idx]
              for k, key in enumerate(SK)}
    ck_cells = sorted(crop_kind)
    fk_cells = sorted(forest_kind)
    CK_SRC = ["me"]
    tidal_cells = [int(i) for i in np.nonzero(tidal_share > 0)[0]]
    world = {
        "version": "phase5c-" + "20261001",
        "grid": {"radius": R_U, "cols": cols, "rows": rows, "layout": "pointy-top, odd-r offset"},
        "width": round(G.width, 1), "height": round(G.height, 1),
        "meters_per_unit": MPU, "origin_5179": list(origin),
        "hex_km2": round(hex_km2, 3),
        "owner": owner.tolist(), "county": county.tolist(),
        "land_frac": [rnd(v, 2) for v in land_frac],
        "foreign": foreign.tolist(),
        "elev": [rnd(v, 0) for v in elev],
        "elev_sd": [rnd(v, 0) if is_landcell[i] else None for i, v in enumerate(sd)],
        "water": water.tolist(), "relief": relief.tolist(), "cover": cover_id.tolist(),
        "cover_keys": TR.COVER_KEYS,
        "cover_share": {"cells": "대한민국 육지 칸(owner >= 0)을 칸 번호 오름차순으로 (land_cells 와 같은 순서)", "unit": "%",
                        "keys": SK, "names": {k: TR.SHARE_KO[k] for k in SK},
                        "rule": ("분모는 칸에 나눈 도엽 세분류 면적 합(해양수·갯벌 제외). forest = broadleaf + conifer + mixed, crop = 논·밭·시설재배지·과수원·기타재배지 합(기타재배지는 열이 따로 없다), "
                                 "built = 시가화건조지역 세분류 14개 합. 대분류 7개 합이 100%다. ESA 보완 칸(cover_src 'esa')은 대분류 7개만 있고 세부 열은 null."),
                        "land_cells": [int(i) for i in land_idx], **cs_pct},
        "cover_src": {"kinds": ["me", "esa"], "names": [cov_meta["label"], "ESA WorldCover 2021 (도엽 통계가 닿지 않는 칸, 대체 자료)"],
                      "cells": "cover_share.land_cells 순서", "src": [int(cover_src[i]) - 1 if cover_src[i] else None for i in land_idx]},
        "crop_kind": {"kinds": [TR.SHARE_KO[k] for k in CK], "keys": CK, "srcs": CK_SRC, "cells": ck_cells,
                      "kind": [CK.index(crop_kind[i]) if crop_kind[i] else None for i in ck_cells],
                      "src": [CK_SRC.index(crop_src[i]) if crop_src[i] else None for i in ck_cells]},
        "forest_kind": {"kinds": [TR.SHARE_KO[k] for k in FK], "keys": FK, "cells": fk_cells,
                        "kind": [FK.index(forest_kind[i]) for i in fk_cells]},
        "tidal": {"cells": tidal_cells, "share": [round(float(tidal_share[i]), 3) for i in tidal_cells],
                  "tile_threshold": TIDAL_TILE, "year": ", ".join(tf_years), "by_sido": tidal_by_sido,
                  "polygons": len(tf_geom), "polygon_area_km2": round(tf_area_raw / 1e6, 1),
                  "area_in_cells_km2": round(tf_in_cells / 1e6, 1)},
        "tables": tables,
        "states": states_l,
        "counties": counties,
        "rivers": rivers,
        "river_labels": river_labels,
        "river_meta": {"national_raw": n_nat_raw, "local_raw": len(rv_recs) - n_nat_raw,
                       "national": sorted({(str(r.get("rivcd")), r.get("name")) for r in rv_recs if r.get("grade") == "국가하천"}),
                       "local_min_km": LOCAL_RIVER_KM, "main_stems": main_found},
        "lakes": lake_draw,
        "lake_labels": lake_labels,
        "lake_meta": {"polygons": len(lk_geom), "lake_cells": n_lake_cells, "lake_cells_by_name": lake_cell_area,
                      "draw_min_km2": LAKE_DRAW_KM2, "label_min_km2": LAKE_LABEL_KM2},
        "cover_meta": cov_meta,
    }
    world["build_profile"] = PRF.PROFILE   # 판 이름: --skip-world 빌드가 다른 판의 world.json 을 쓰지 않게 한다
    size = save_json(site("world.json"), world)
    log(f"world.json {size / 1e6:.2f} MB, 육지 {nl}칸 × {hex_km2:.2f} = {nl * hex_km2:,.0f} km²")
    for k_ in ("rivers", "lakes", "cover_share", "cover_src", "crop_kind", "forest_kind", "tidal"):
        if k_ not in world:
            continue
        log(f"   {k_}: {len(json.dumps(world[k_], ensure_ascii=False, separators=(',', ':'))) / 1e3:.0f} KB")

    # 중간 산출물
    np.savez_compressed(build("world_samples.npz"), samp=samp, owner=owner, county=county,
                        centers=centers, offs=offs)
    np.savez_compressed(build("terrain_cache.npz"), profile=np.array(PRF.PROFILE), cover_keys=np.array(TR.COVER_KEYS), share_keys=np.array(SK),
                        leaf_keys=np.array(CS.LEAVES), cover_share=cover_share, alloc=alloc, esa_cnt=esa_cnt,
                        sheet_codes=np.array(sh_codes), alloc_sheet=a_si, alloc_cell=a_ci, alloc_w=a_w, alloc_mode=a_mode,
                        cover_src=cover_src, cover_id=cover_id, land=land, land_frac=land_frac, hex_km2=hex_km2,
                        tidal_share=tidal_share, tidal_m2=tidal_m2, lake_points=lake_pts)
    save_json(build("landcover_compare.json"), {"rule": cov_meta["compare"]["rule"], "year": st_year, "nation": cmp_["nation"],
                                                "summary": cmp_["summary"], "tolerance": cmp_["tolerance"], "counties": cmp_["counties"],
                                                "unmatched": st_miss}, compact=False)
    dong_rp = shapely.point_on_surface(dong_geoms)
    dux, duy = m2u(shapely.get_x(dong_rp), shapely.get_y(dong_rp))
    dcx, dcy = m2u(shapely.get_x(shapely.centroid(dong_geoms)), shapely.get_y(shapely.centroid(dong_geoms)))
    for k, d in enumerate(dongs):
        d.update(area_km2=round(float(areas[k]) / 1e6, 4), rx=round(float(dux[k]), 2), ry=round(float(duy[k]), 2),
                 cx=round(float(dcx[k]), 2), cy=round(float(dcy[k]), 2), rp_cell=int(G.point_to_cell(dux[k], duy[k])),
                 samples=int((samp == k).sum()))
    save_json(build("dongs.json"), dongs)
    save_json(build("labels.json"), labels)
    save_json(build("world_log.json"), {"promoted_islands": promoted, "missing_before": missing_before,
                                         "fixes": fixes, "relief": {"T1": T1, "T2": T2, "dist": dist, "draft": draft},
                                         "mixed_cells": n_mixed}, compact=False)


if __name__ == "__main__":
    sys.exit(main())

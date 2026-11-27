"""지형 입력 읽기: data/build/layers 의 정리표(래스터·GeoJSON·CSV), 모두 읽기만.

원자료 정리표는 신뢰할 수 없는 입력으로 다룬다: 필드 값은 데이터로만 쓰고, 형식이 다르면 빌드 오류로 멈춘다.
"""
import json
import os

import numpy as np
import shapely
from pyproj import Transformer

from .common import BUILD

LAYERS = os.path.join(BUILD, "layers")
TO5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

# ESA WorldCover 2021 v200 분류 코드 -> 타일 피복 분류 (cover_share 의 열 이름). 래스터 태그의 분류표와 대조한다.
ESA_TO_COVER = {
    10: "forest",   # Tree cover
    20: "grass",    # Shrubland (관목) — 숲이 아닌 낮은 식생으로 묶는다
    30: "grass",    # Grassland
    40: "crop",     # Cropland (논·밭 구분 없음)
    50: "built",    # Built-up
    60: "bare",     # Bare / sparse vegetation
    70: "bare",     # Snow and ice
    80: "water",    # Permanent water bodies
    90: "wetland",  # Herbaceous wetland
    95: "wetland",  # Mangroves
    100: "grass",   # Moss and lichen
}
ESA_NAMES_EXPECTED = {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
                      60: "Bare/sparse vegetation", 70: "Snow and ice", 80: "Permanent water bodies",
                      90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen"}
# 대분류 (칸의 대표 피복 cover 의 번호 = 이 순서 + 1). 같은 비율이면 앞쪽이 이긴다.
COVER_KEYS = ["forest", "crop", "built", "grass", "wetland", "bare", "water"]
COVER_KO = {"forest": "숲", "crop": "농경지", "built": "시가지", "grass": "초지", "wetland": "습지",
            "bare": "나지", "water": "수면"}

# ---------------- 국가토지피복통계 정리표 (패널 '땅' 구역) ----------------
# 칸 피복은 lib/cover_sheets.py (세분류 토지피복지도 도엽 통계, 두 판 공용). 기후에너지환경부 WMS 그림을 읽던 함수는 없앴다 — 어느 판에서도 쓰지 않는다.
ME_STATS = "landcover_stats_open.csv"  # build_landstats_open.py (공공데이터포털 15163128, 공공누리 제1유형)
SHARE_KO = {**COVER_KO, "broadleaf": "활엽수림", "conifer": "침엽수림", "mixed": "혼효림", "paddy": "논", "field": "밭",
            "orchard": "과수원", "greenhouse": "시설재배지"}
CROP_KINDS = ["paddy", "field", "orchard", "greenhouse"]       # crop_kind 후보 (기타재배지 250 은 넣지 않음)
FOREST_KINDS = ["broadleaf", "conifer", "mixed"]
# 국가토지피복통계 중분류 이름 -> 패널 항목
STATS_ITEMS = {"논": ["논"], "밭": ["밭"], "과수원": ["과수원"], "시설재배지": ["시설재배지"],
               "산림": ["활엽수림", "침엽수림", "혼효림"],
               "시가화": ["주거지역", "공업지역", "상업지역", "문화·체육·휴양지역", "교통지역", "공공시설지역"]}


def layer_path(name):
    return os.path.join(LAYERS, name)


def read_raster(name):
    """-> (배열, 셀 중심 E 배열 함수, 태그, 메타). 좌표계는 EPSG:5179 여야 한다."""
    import rasterio
    with rasterio.open(layer_path(name)) as r:
        if r.crs is None or r.crs.to_epsg() != 5179:
            raise ValueError(f"{name}: 좌표계가 EPSG:5179 가 아님 ({r.crs})")
        if r.count != 1:
            raise ValueError(f"{name}: 밴드 수 {r.count}")
        a = r.read(1)
        t = r.transform
        if abs(t.b) > 1e-9 or abs(t.d) > 1e-9:
            raise ValueError(f"{name}: 회전된 격자")
        meta = {"transform": (t.a, t.b, t.c, t.d, t.e, t.f), "width": r.width, "height": r.height,
                "nodata": r.nodata, "res_m": abs(t.a)}
        tags = r.tags()
    return a, meta, tags


def raster_centers(meta, rows, cols):
    a, _, c, _, e, f = meta["transform"]
    return c + (cols + 0.5) * a, f + (rows + 0.5) * e


def read_vector(name):
    """GeoJSON -> (EPSG:5179 도형 배열, 속성 dict 목록, 원래 좌표계)."""
    import pyogrio.raw as R
    meta, _, geom, fields = R.read(layer_path(name))
    crs = meta.get("crs") or ""
    if "4326" not in str(crs):
        raise ValueError(f"{name}: 좌표계가 EPSG:4326 이 아님 ({crs})")
    g = shapely.from_wkb(geom)
    g = shapely.transform(g, lambda xy: np.column_stack(TO5179.transform(xy[:, 0], xy[:, 1])))
    names = list(meta["fields"])
    recs = [dict(zip(names, (None if (isinstance(v, float) and v != v) else v for v in vals))) for vals in zip(*fields)] \
        if len(fields) else [{} for _ in range(len(g))]
    return g, recs, str(crs)


def read_me_stats():
    """국가토지피복통계 (시군구별 중분류 면적 ha) -> (현재 시군구 코드 -> {중분류: ha}, 전국 {중분류: ha}, 현재 코드가 빈 행 목록, 기준 연도).

    빈 값은 None 으로 둔다(0 으로 바꾸지 않음). 현재 코드가 빈 행(개편 전 분할 시군구)은 어느 현재 시군구에도 더하지 않는다.
    """
    import csv
    with open(layer_path(ME_STATS), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    by, nat, blank, years, srcs = {}, {}, {}, set(), set()
    for r in rows:
        v = (r["value"] or "").strip()
        val = float(v) if v else None
        if r["unit"].strip() != "ha":
            raise ValueError(f"{ME_STATS}: 단위가 ha 가 아님 {r}")
        years.add(r["year"].strip())
        srcs.add(r["source_id"].strip())
        code = r["sgg_code_now"].strip()
        if r["sgg_name_raw"].strip() == "전국" and r["sido_now"].strip() == "전국":
            nat[r["indicator"].strip()] = val
        elif code:
            by.setdefault(code, {})[r["indicator"].strip()] = val
        else:
            blank.setdefault((r["sido_now"].strip(), r["sgg_name_raw"].strip()), {})[r["indicator"].strip()] = val
    if len(years) != 1:
        raise ValueError(f"{ME_STATS}: 기준 연도가 여럿 {years}")
    return by, nat, blank, years.pop(), sorted(srcs)


def esa_classes_from_tags(tags):
    cl = json.loads(tags.get("classification", "{}"))
    got = {int(k): v for k, v in cl.items()}
    if got != ESA_NAMES_EXPECTED:
        raise ValueError(f"landcover.tif 분류표가 ESA WorldCover v200 과 다름: {got}")
    return got

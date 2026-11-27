"""칸 토지피복 (두 판 공용): 기후에너지환경부 「세분류 토지피복지도 도엽단위 현행화 통계」(공공데이터포털 15150509, 공공누리 제1유형).

원자료 data/raw/layers5/files/p2-15150509.csv 는 1:5,000 도엽마다 세분류 41개 면적(㎡)을 적은 표다. 이 모듈은
  ① 도엽번호 -> 도엽 테두리(경위도, 국토지리정보원 1:5,000 도엽 체계 — 아래 sheet_box)
  ② 도엽 세분류 면적 -> 육각 칸 (도엽과 칸이 겹친 땅 넓이에 비례해 나눔)
  ③ 41개 세분류 -> 칸 피복 열(cover_share 의 열 이름)
을 맡는다. 원자료는 신뢰할 수 없는 입력으로 다룬다: 열 이름·도엽번호 꼴·숫자가 예상과 다르면 빌드 오류로 멈추고, 파일 sha256 을
수집 기록(data/raw/layers5/manifest.json)과 대조한다. 기후에너지환경부 WMS 그림(data/raw/landcover_me)은 읽지 않는다.
"""
import csv
import hashlib
import json
import math
import os
import re

import numpy as np

from .common import RAW

L5 = os.path.join(RAW, "layers5")
SHEET_FILE = ("files", "p2-15150509.csv")
SHEET_KEY = "p2-15150509"          # data/raw/layers5/manifest.json 의 기록 이름
SOURCE_KEY = "data-15150509"       # sources.json 의 출처 key
STATS_FILE = ("files", "p2-15163128.csv")
STATS_KEY = "p2-15163128"
STATS_SOURCE_KEY = "data-15163128"
SOURCE_NAME = "기후에너지환경부 세분류 토지피복지도 도엽단위 현행화 통계 (공공데이터포털 15150509, 공공누리 제1유형)"
STATS_NAME = "기후에너지환경부 국가 토지피복 통계 (공공데이터포털 15163128, 공공누리 제1유형)"

# 세분류 41개 (원자료 열 순서) -> 칸 피복 세부 열. 'sea'(해양수)·'tidal'(갯벌)은 칸에 나누지 않는다(칸 비율의 분모에서도 뺀다):
# 도엽의 갯벌은 대부분 행정경계 밖 바다 쪽이라(도엽 합 약 2,247 km², 행정경계로 자른 국가 토지피복 통계의 갯벌은 약 35 km²) 땅 칸에 얹으면 습지가 부푼다.
# 갯벌은 칸 위에 해양수산부 갯벌 자료(world.tidal)로 따로 그린다.
# 대분류 묶음은 환경부 토지피복 분류체계(대분류 7·중분류 22·세분류 41)를 따른다: 시가화건조지역 14개 -> built,
# 농업지역 8개 -> 논·밭·시설재배지·과수원·기타재배지(목장양식장 포함), 산림지역 3개 -> 활엽·침엽·혼효, 초지 4개 -> grass,
# 습지 3개 가운데 내륙습지·염전 -> wetland (갯벌 -> tidal, 나누지 않음), 나지 6개 -> bare, 수역 3개 -> 내륙수 water · 해양수 sea.
CLASS_MAP = [
    ("단독주거시설", "built"), ("공동주거시설", "built"), ("공업시설", "built"), ("상업업무시설", "built"), ("혼합지역", "built"),
    ("문화체육휴양시설", "built"), ("공항", "built"), ("항만", "built"), ("철도", "built"), ("도로", "built"),
    ("기타교통통신시설", "built"), ("환경기초시설", "built"), ("교육행정시설", "built"), ("기타공공시설", "built"),
    ("경지정리가된논", "paddy"), ("경지정리가안된논", "paddy"), ("경지정리가된밭", "field"), ("경지정리가안된밭", "field"),
    ("시설재배지", "greenhouse"), ("과수원", "orchard"), ("목장양식장", "crop_other"), ("기타재배지", "crop_other"),
    ("활엽수림", "broadleaf"), ("침엽수림", "conifer"), ("혼효림", "mixed"),
    ("자연초지", "grass"), ("골프장", "grass"), ("묘지", "grass"), ("기타초지", "grass"),
    ("내륙습지", "wetland"), ("갯벌", "tidal"), ("염전", "wetland"),
    ("해변", "bare"), ("강기슭", "bare"), ("암벽바위", "bare"), ("채광지역", "bare"), ("운동장", "bare"), ("기타나지", "bare"),
    ("하천", "water"), ("호소", "water"), ("해양수", "sea"),
]
CLASSES = [c for c, _ in CLASS_MAP]
HEAD = ["도엽번호", "제작연도", "기준년도", "데이터기준일"]
LEAVES = ["broadleaf", "conifer", "mixed", "paddy", "field", "orchard", "greenhouse", "crop_other", "built", "grass", "wetland", "bare", "water"]
# cover_share 의 열 (WMS 시절의 unclassified 열은 없다 — 도엽 통계에는 그림에 안 그려진 픽셀이 없다)
SHARE_KEYS = ["forest", "broadleaf", "conifer", "mixed", "crop", "paddy", "field", "orchard", "greenhouse", "built", "grass", "wetland", "bare", "water"]
MAJOR_OF = {"broadleaf": "forest", "conifer": "forest", "mixed": "forest", "paddy": "crop", "field": "crop", "orchard": "crop",
            "greenhouse": "crop", "crop_other": "crop", "built": "built", "grass": "grass", "wetland": "wetland", "bare": "bare", "water": "water"}
MAJOR_KO = {"forest": "산림지역", "crop": "농업지역", "built": "시가화건조지역", "grass": "초지", "wetland": "습지", "bare": "나지", "water": "수역"}
LEAF_KO = {"broadleaf": "활엽수림", "conifer": "침엽수림", "mixed": "혼효림", "paddy": "논", "field": "밭", "orchard": "과수원",
           "greenhouse": "시설재배지", "crop_other": "기타재배지(목장양식장 포함)", "built": "시가화건조지역", "grass": "초지",
           "wetland": "습지(내륙습지·염전)", "bare": "나지", "water": "내륙수(하천·호소)", "sea": "해양수 (칸에 나누지 않음)",
           "tidal": "갯벌 (칸에 나누지 않음 — 칸 위 갯벌은 해양수산부 갯벌 자료)"}
EXCLUDED = ("sea", "tidal")

# 도엽 테두리. 국토지리정보원 도엽 체계: 8자리 = 위도 정수 2자리 + 경도 정수 끝자리(4–9 -> 124–129°, 0–2 -> 130–132°)
# + 1:50,000 번호 01–16(1°×1° 안 15′×15′, 북서에서 행 우선) + 1:5,000 번호 001–100(15′×15′ 안 1.5′×1.5′, 북서에서 행 우선).
# 경위도는 세계측지계(GRS80) 그대로다. 아래 1:50,000 도엽은 섬 때문에 도곽을 옮긴 특별도곽이라 옮긴 만큼 더한다(분 단위).
# 옮긴 값은 원자료로 정했다: 도엽의 세분류 면적 합이 옮긴 테두리의 넓이와 맞고, 해양수를 뺀 몫이 행정경계와 겹친 몫과 맞는 값.
SPECIAL_MIN = {"33605": (-6.0, 0.0), "33606": (-6.0, 0.0), "33607": (-6.0, 0.0), "33608": (-6.0, 0.0),
               "33609": (-6.0, -5.0), "33610": (-6.0, -5.0), "33611": (-6.0, -5.0), "33612": (-6.0, -5.0), "33614": (-6.0, -5.0),
               "37012": (4.5, 0.0)}
CODE_RE = re.compile(r"^(3[3-8])([0-24-9])(0[1-9]|1[0-6])(0\d\d|100)$")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def manifest_entry(key):
    m = json.load(open(os.path.join(L5, "manifest.json"), encoding="utf-8"))
    if key not in m:
        raise ValueError(f"layers5 manifest 에 {key} 기록이 없음")
    return m[key]


def read_checked(rel, key):
    """원자료 파일 바이트 (수집 기록의 sha256·바이트와 같아야 한다)."""
    e = manifest_entry(key)
    p = os.path.join(L5, *rel)
    b = open(p, "rb").read()
    if len(b) != e["bytes"] or sha256_bytes(b) != e["sha256"]:
        raise ValueError(f"{p}: 파일이 수집 기록(manifest {key})과 다름")
    if e.get("file") != "/".join(rel):
        raise ValueError(f"manifest {key} 의 file 이 {e.get('file')} — {'/'.join(rel)} 가 아님")
    return b, e


def sheet_box(code):
    """도엽번호 -> (경도0, 위도0, 경도1, 위도1). 꼴이 다르면 ValueError."""
    m = CODE_RE.match(code)
    if not m:
        raise ValueError(f"도엽번호 꼴이 다름: {code!r}")
    lat_d, lon_d, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    if not 1 <= b <= 100:
        raise ValueError(f"1:5,000 번호가 1–100 밖: {code}")
    lon_deg = 120 + lon_d if lon_d >= 4 else 130 + lon_d
    top = lat_d + 1 - ((a - 1) // 4) * 0.25 - ((b - 1) // 10) * 0.025
    left = lon_deg + ((a - 1) % 4) * 0.25 + ((b - 1) % 10) * 0.025
    dlat, dlon = SPECIAL_MIN.get(code[:5], (0.0, 0.0))
    top += dlat / 60.0
    left += dlon / 60.0
    return left, top - 0.025, left + 0.025, top


def read_sheets():
    """-> (도엽번호 목록, 면적 배열 M × 41 (㎡), 기록). 도엽마다 기준년도가 가장 늦은 행을 쓴다."""
    b, e = read_checked(SHEET_FILE, SHEET_KEY)
    t = b.decode("utf-8-sig")
    rows = list(csv.reader(t.splitlines()))
    if not rows or rows[0] != HEAD + CLASSES:
        raise ValueError(f"15150509 열이 예상과 다름: {rows[0] if rows else None}")
    data = rows[1:]
    by = {}
    years = {}
    for r in data:
        if len(r) != len(HEAD) + len(CLASSES):
            raise ValueError(f"15150509 행 길이 {len(r)}: {r[:4]}")
        code, made, base, day = (x.strip() for x in r[:4])
        sheet_box(code)
        mm = re.fullmatch(r"(\d{4})년", base)
        mk = re.fullmatch(r"(\d{4})년", made)
        if not mm or not mk or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or not day.startswith(mm.group(1)):
            raise ValueError(f"15150509 연도 꼴이 다름: {r[:4]}")
        vals = []
        for x in r[4:]:
            v = float(x)
            if not math.isfinite(v) or v < 0:
                raise ValueError(f"15150509 면적 값이 음수·비수: {code} {x!r}")
            vals.append(v)
        y = int(mm.group(1))
        key = (code, y)
        if key in years:
            raise ValueError(f"15150509 같은 도엽·기준년도 행이 둘: {key}")
        years[key] = (int(mk.group(1)), day)
        if code not in by or y > by[code][0]:
            by[code] = (y, vals)
    codes = sorted(by)
    A = np.array([by[c][1] for c in codes], dtype=np.float64)
    from collections import Counter
    n_rows_sheet = Counter(c for c, _ in years)
    chosen = Counter(by[c][0] for c in codes)
    base_years = Counter(y for _, y in years)
    rec = {"rows": len(data), "sheets": len(codes), "rows_per_sheet": dict(Counter(n_rows_sheet.values())),
           "base_years": {str(k): v for k, v in sorted(base_years.items())}, "chosen_base_year": {str(k): v for k, v in sorted(chosen.items())},
           "made_years": {f"{y}년 기준": sorted({str(v[0]) + '년' for (c, yy), v in years.items() if yy == y}) for y in sorted(base_years)},
           "sha256": e["sha256"], "bytes": e["bytes"], "file": "layers5/" + e["file"]}
    latest = max(base_years)
    rec["rule"] = (f"원자료 {len(data):,}행은 도엽 {len(codes):,}개의 기준년도별 행이다(한 도엽에 "
                   + ", ".join(f"{v:,}개 도엽은 {k}행" for k, v in sorted(rec["rows_per_sheet"].items(), key=lambda kv: -kv[0])) + "; 기준년도 "
                   + ", ".join(f"{k}년 {v:,}행" for k, v in rec["base_years"].items()) + "). "
                   f"도엽마다 기준년도가 가장 늦은 행 하나를 쓴다 — 이 파일에서는 모든 도엽이 {latest}년 기준 행({', '.join(rec['made_years'][f'{latest}년 기준'])} 제작)을 쓴다.")
    return codes, A, rec


def index_check(codes, A):
    """도엽 테두리 검산: 세분류 41개 면적 합 ÷ 테두리의 타원체(GRS80) 넓이. 테두리 해석이 맞으면 대부분 1 에 아주 가깝다."""
    from pyproj import Geod
    g = Geod(ellps="GRS80")
    tot = A.sum(1)
    rel = np.empty(len(codes))
    for k, c in enumerate(codes):
        x0, y0, x1, y1 = sheet_box(c)
        a, _ = g.polygon_area_perimeter([x0, x1, x1, x0], [y0, y0, y1, y1])
        rel[k] = tot[k] / abs(a) - 1
    ab = np.abs(rel)
    return {"sheets": len(codes), "median_abs_rel": float(np.median(ab)), "p95_abs_rel": float(np.percentile(ab, 95)),
            "within_1e-4": int((ab < 1e-4).sum()), "within_1e-3": int((ab < 1e-3).sum()),
            "short_over_10pct": int((rel < -0.1).sum()), "rel": rel}


def leaf_matrix(A):
    """M × 41 -> M × len(LEAVES) (㎡), 나누지 않는 열(해양수·갯벌) 합."""
    out = np.zeros((A.shape[0], len(LEAVES)))
    sea = np.zeros(A.shape[0])
    for j, (_, key) in enumerate(CLASS_MAP):
        if key in EXCLUDED:
            sea += A[:, j]
        else:
            out[:, LEAVES.index(key)] += A[:, j]
    return out, sea


def sheet_polygons(codes, to5179, dens=8):
    """도엽 테두리 -> EPSG:5179 다각형 (변마다 dens 점으로 나눠 투영)."""
    import shapely
    polys = []
    t = np.linspace(0, 1, dens + 1)[:-1]
    for c in codes:
        x0, y0, x1, y1 = sheet_box(c)
        xs = np.concatenate([x0 + (x1 - x0) * t, np.full(dens, x1), x1 - (x1 - x0) * t, np.full(dens, x0)])
        ys = np.concatenate([np.full(dens, y0), y0 + (y1 - y0) * t, np.full(dens, y1), y1 - (y1 - y0) * t])
        e, n = to5179.transform(xs, ys)
        polys.append(shapely.Polygon(np.column_stack([e, n])))
    return np.array(polys, dtype=object)


def allocate(sheet_polys, hex_polys, hex_cells, land_geoms):
    """도엽 -> 칸 나눔 무게.

    도엽마다 (도엽 ∩ 칸 ∩ 대한민국 행정경계) 넓이 ÷ (도엽 ∩ 행정경계) 넓이. 도엽이 행정경계와 겹치지 않으면 (도엽 ∩ 칸) ÷ 도엽 넓이.
    -> (도엽 번호 배열, 칸 번호 배열, 무게 배열, 도엽별 나눔 방식 0 = 행정경계 / 1 = 도엽 넓이, 도엽별 행정경계 겹침 넓이)
    hex_polys 는 hex_cells(칸 번호) 순서의 칸 육각형 (EPSG:5179). land_geoms 는 겹치지 않는 행정동 도형 (EPSG:5179).
    """
    import shapely
    htree = shapely.STRtree(hex_polys)
    si, hi = htree.query(sheet_polys, predicate="intersects")
    pieces = shapely.intersection(sheet_polys[si], hex_polys[hi])
    piece_area = shapely.area(pieces)
    ltree = shapely.STRtree(land_geoms)
    pi, gi = ltree.query(pieces, predicate="intersects")
    land_piece = np.zeros(len(pieces))
    if len(pi):
        np.add.at(land_piece, pi, shapely.area(shapely.intersection(pieces[pi], land_geoms[gi])))
    M = len(sheet_polys)
    sheet_land = np.zeros(M)
    np.add.at(sheet_land, si, land_piece)
    sheet_area = shapely.area(sheet_polys)
    mode = np.where(sheet_land > 0, 0, 1).astype(np.int8)
    w = np.where(mode[si] == 0, land_piece / np.where(sheet_land[si] > 0, sheet_land[si], 1), piece_area / sheet_area[si])
    keep = w > 0
    return si[keep].astype(np.int32), np.asarray(hex_cells)[hi[keep]].astype(np.int32), w[keep], mode, sheet_land


def read_stats():
    """국가 토지피복 통계(15163128) 의 가장 늦은 기준년도 '면적(㎡)' 행 -> ({'전국'|'시도 이름'|'시도 시군구': {세분류: ㎡}}, 연도, 기록)."""
    b, e = read_checked(STATS_FILE, STATS_KEY)
    rows = list(csv.reader(b.decode("utf-8-sig").splitlines()))
    h = rows[0]
    want = [c.replace(" ", "") for c in CLASSES]
    got = [c.replace(" ", "") for c in h[6:6 + len(CLASSES)]]
    if h[:6] != ["지역구분", "기준년도", "데이터기준일", "지역명", "통계구분", "학습데이터활용면적"] or got != want:
        raise ValueError(f"15163128 열이 예상과 다름: {h}")
    years = sorted({r[1] for r in rows[1:]})
    y = years[-1]
    out = {}
    for r in rows[1:]:
        if r[1] != y or r[4] != "면적(㎡)":
            continue
        if r[0] not in ("전국", "시도", "시군구"):
            raise ValueError(f"15163128 지역구분 {r[0]!r}")
        vals = {}
        for c, x in zip(CLASSES, r[6:6 + len(CLASSES)]):
            v = float(x)
            if not math.isfinite(v) or v < 0:
                raise ValueError(f"15163128 값 {r[3]} {c} {x!r}")
            vals[c] = v
        out[(r[0], r[3].strip())] = vals
    return out, int(y[:4]), {"sha256": e["sha256"], "bytes": e["bytes"], "file": "layers5/" + e["file"], "years": years}


def group_stats(vals):
    """세분류 ㎡ -> 칸 열 ㎡ (+ 해양수 sea·갯벌 tidal)."""
    g = {k: 0.0 for k in LEAVES + list(EXCLUDED)}
    for c, key in CLASS_MAP:
        g[key] += vals[c]
    return g


def shares_from_leaves(leaf):
    """칸 열 ㎡ (dict 또는 배열 묶음) -> 분모(해양수·갯벌 뺀 합)와 대분류·세부 비율 dict."""
    tot = sum(leaf[k] for k in LEAVES)
    out = {"total": tot}
    for k in ("broadleaf", "conifer", "mixed", "paddy", "field", "orchard", "greenhouse", "built", "grass", "wetland", "bare", "water"):
        out[k] = leaf[k] / tot if tot else float("nan")
    out["forest"] = (leaf["broadleaf"] + leaf["conifer"] + leaf["mixed"]) / tot if tot else float("nan")
    out["crop"] = sum(leaf[k] for k in ("paddy", "field", "orchard", "greenhouse", "crop_other")) / tot if tot else float("nan")
    return out


def stats_units(stats, world_like):
    """국가 토지피복 통계의 시군구 행 -> [(행 이름, 현재 시군구 코드 묶음, 칸 열 ㎡)], 대응 못 한 행 이름.

    이름은 pipeline/lib/address.py 의 주소 규칙(현재·옛 시도 이름, 인천 개편 전 구 -> 나뉜 뒤 구 묶음)으로 읽는다(도시 목록 없이).
    일반구를 두게 된 시의 시 행(예: 화성시)은 그 시 이름으로 시작하는 현재 시군구 전부를 한 묶음으로 둔다.
    옛 행 여럿이 같은 현재 시군구에 걸치면 그 행들을 더해 한 묶음으로 견준다.
    """
    from .address import AddressResolver, nospace
    R = AddressResolver(world_like, [])
    out, miss = [], []
    for (kind, nm), vals in sorted(stats.items()):
        if kind != "시군구":
            continue
        r = R.resolve(nm)
        codes = sorted(r["codes"]) if r else None
        if codes is None:
            sd, rest = R.sido_of(nm) or (None, "")
            kids = sorted(c["code"] for c in world_like["counties"] if sd and c["sido"] == sd and rest.endswith("시")
                          and nospace(c["name"]).startswith(rest) and len(nospace(c["name"])) > len(rest))
            codes = kids or None
        if not codes:
            miss.append(nm)
            continue
        out.append((nm, tuple(codes), group_stats(vals)))
    # 개편으로 옛 행 여럿이 같은 현재 시군구에 걸치면(인천 중구·동구 -> 제물포구) 한 묶음으로 합친다
    merged = True
    while merged:
        merged = False
        for a in range(len(out)):
            for b in range(a + 1, len(out)):
                if set(out[a][1]) & set(out[b][1]):
                    g = {k: out[a][2][k] + out[b][2][k] for k in out[a][2]}
                    out[a] = (out[a][0] + " + " + out[b][0], tuple(sorted(set(out[a][1]) | set(out[b][1]))), g)
                    del out[b]
                    merged = True
                    break
            if merged:
                break
    return out, miss


COMPARE_KEYS = (("forest", "산림"), ("paddy", "논"), ("field", "밭"), ("built", "시가화"))
# 판정 기준 (validate.py C7s 가 쓴다). 2024년 기준 도엽 통계를 이 규칙으로 나눴을 때 실제로 나온 차이를 보고 정했다(값은 docs/PLAN_NEXT.md):
# 전국 차이는 네 항목 모두 0.2%p 아래였고, 칸 10개 이상 시군구의 90백분위는 숲 2.2·논 0.9·밭 0.6·시가화 0.9%p, 가장 큰 차이는 숲 8.0·논 7.6·밭 2.0·시가화 2.9%p.
# 칸 10개 미만 시군구는 칸과 시군구 경계가 달라 차이가 크다(서울 자치구 한 칸에 시가화 -26%p) — 출력만 한다.
TOL = {"nation_pp": 0.5, "county_min_cells": 10,
       "county_p90_pp": {"forest": 3.0, "paddy": 1.5, "field": 1.0, "built": 1.5},
       "county_max_pp": {"forest": 10.0, "paddy": 10.0, "field": 3.0, "built": 4.0}}


def cell_mean_shares(share_rows):
    """칸 비율 행렬(칸 × SHARE_KEYS, NaN 허용) -> 칸 평균 비율 dict (칸 넓이가 같아 칸 평균 = 칸 넓이 가중)."""
    m = np.nanmean(share_rows, axis=0) if len(share_rows) else np.full(len(SHARE_KEYS), np.nan)
    return dict(zip(SHARE_KEYS, m.tolist()))


def compare(share, land_idx, county, county_codes, stats, units):
    """칸 비율(칸 × SHARE_KEYS) vs 국가 토지피복 통계: 전국과 시군구 묶음별 네 항목 비율(%)의 차이(%p).

    칸 쪽은 대한민국 육지 칸(피복이 있는 칸)의 칸 평균, 통계 쪽은 (해양수·갯벌을 뺀 합) 대비 비율.
    """
    q = {k: SHARE_KEYS.index(k) for k, _ in COMPARE_KEYS}
    li = np.asarray(land_idx)
    ok = li[~np.isnan(share[li, 0])]
    cm = cell_mean_shares(share[ok])
    sn = shares_from_leaves(group_stats(stats[("전국", "전국")]))
    nat = {k: {"cells_pct": round(100 * cm[k], 2), "stats_pct": round(100 * sn[k], 2), "diff_pp": round(100 * (cm[k] - sn[k]), 2)} for k, _ in COMPARE_KEYS}
    code_idx = {c: j for j, c in enumerate(county_codes)}
    rows = []
    for nm, codes, g in units:
        js = {code_idx[c] for c in codes if c in code_idx}
        cells = [int(i) for i in ok if county[i] in js]
        if not cells:
            rows.append({"name": nm, "codes": list(codes), "cells": 0})
            continue
        a = cell_mean_shares(share[cells])
        b = shares_from_leaves(g)
        rows.append({"name": nm, "codes": list(codes), "cells": len(cells),
                     **{k: {"cells_pct": round(100 * a[k], 2), "stats_pct": round(100 * b[k], 2), "diff_pp": round(100 * (a[k] - b[k]), 2)} for k, _ in COMPARE_KEYS}})
    big = [r for r in rows if r["cells"] >= TOL["county_min_cells"]]
    summ = {}
    for k, _ in COMPARE_KEYS:
        d = np.array([abs(r[k]["diff_pp"]) for r in big]) if big else np.array([np.nan])
        da = np.array([abs(r[k]["diff_pp"]) for r in rows if r["cells"]])
        summ[k] = {"big_n": len(big), "big_median_pp": round(float(np.median(d)), 2), "big_p90_pp": round(float(np.percentile(d, 90)), 2),
                   "big_max_pp": round(float(d.max()), 2), "all_median_pp": round(float(np.median(da)), 2), "all_p90_pp": round(float(np.percentile(da, 90)), 2)}
    return {"nation": nat, "counties": rows, "summary": summ, "tolerance": TOL}

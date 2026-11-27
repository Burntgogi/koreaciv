"""문제 1(인천국제공항) 및 문제 2(토지피복) 후보 해법 종합 실증·비교 스크립트.

실행: python -I tools/research5/verify_all.py
결과: tools/research5/results.json 저장 및 콘솔 요약 출력.
기존 site/, pipeline/, data/build/ 파일은 읽기만 하고 일절 수정하지 않는다.
"""
import site
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.extend([str(Path(__file__).resolve().parents[2] / "pipeline"), site.getusersitepackages()])

import collections
import csv
import io
import json
import math
import time
import zipfile

import numpy as np
import pyogrio
import rasterio
from rasterio.features import geometry_mask, rasterize
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject, transform_geom
import shapefile
import shapely
from shapely.geometry import Polygon, box, shape
from pyproj import Geod, Transformer

from lib.hexgrid import Grid
from lib import terrain as TR

ROOT = Path(__file__).resolve().parents[2]
RAW5 = ROOT / "data/raw/layers5"
OUT_JSON = Path(__file__).resolve().parent / "results.json"

TO5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
TO4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
GEOD = Geod(ellps="WGS84")


def read_text_auto(path):
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="ignore")


def verify_problem1(world):
    """문제 1: 인천국제공항 후보 출처별 좌표·주소·거리(m)·육지 칸 번호·실적 대조."""
    print("=== [실증 1] 인천국제공항 후보 출처 좌표·주소·거리 비교 ===", flush=True)
    G = Grid(world["grid"]["cols"], world["grid"]["rows"], world["grid"]["radius"])
    ox, oy = world["origin_5179"]
    mpu = world["meters_per_unit"]
    counties = world["counties"]
    owner = world["owner"]
    county = world["county"]

    def cell_info(lon, lat):
        e, n = TO5179.transform(lon, lat)
        ux, uy = (e - ox) / mpu, (oy - n) / mpu
        c = G.point_to_cell(float(ux), float(uy))
        cx, cy = G.center(c)
        dist_u = math.hypot(ux - cx, uy - cy)
        sgg = counties[county[c]] if c >= 0 and owner[c] >= 0 else None
        return c, round(dist_u, 2), sgg, (e, n)

    # 기준점: 전체판 AIP ARP
    aip_lon, aip_lat = 126.4391667, 37.4625000
    aip_cell, aip_du, aip_sgg, (aip_e, aip_n) = cell_info(aip_lon, aip_lat)

    # 1. Wikidata Q20932
    wd = json.loads((RAW5 / "files/wikidata-Q20932.json").read_text(encoding="utf-8"))["entities"]["Q20932"]
    wd_coord = wd["claims"]["P625"][0]["mainsnak"]["datavalue"]["value"]
    wd_lon, wd_lat = float(wd_coord["longitude"]), float(wd_coord["latitude"])
    wd_addrs = [c["mainsnak"]["datavalue"]["value"]["text"] for c in wd["claims"].get("P6375", [])
                if c["mainsnak"]["datavalue"]["value"].get("language") == "ko"]

    # 2. 국가철도공단 공항철도 역위치(15041331) + 주소데이터(15041094) + 자기부상 역위치(15041332)
    arex_pos = {r["역명"].strip(): (float(r["경도"]), float(r["위도"]))
                for r in csv.DictReader(io.StringIO(read_text_auto(RAW5 / "files/p1-15041331.csv")))}
    arex_addr = {r["역명"].strip(): r["도로명주소"].strip()
                 for r in csv.DictReader(io.StringIO(read_text_auto(RAW5 / "files/p1-15041094.csv")))}
    mag_pos = {r["역명"].strip(): (float(r["경도"]), float(r["위도"]))
               for r in csv.DictReader(io.StringIO(read_text_auto(RAW5 / "files/p1-15041332.csv")))}
    t1_lon, t1_lat = arex_pos["인천공항1터미널"]
    t2_lon, t2_lat = arex_pos["인천공항2터미널"]
    mid_lon, mid_lat = (t1_lon + t2_lon) / 2.0, (t1_lat + t2_lat) / 2.0
    mag_t1_lon, mag_t1_lat = mag_pos["인천공항1터미널"]

    # 3. 기후에너지환경부 세분류 토지피복지도 도엽단위 현행화 통계 (15150509) '공항' 면적
    rows_0509 = [r for r in csv.DictReader(io.StringIO(read_text_auto(RAW5 / "files/p2-15150509.csv")))
                 if r["제작연도"] == "2025년" and r["도엽번호"].strip().startswith("37610") and float(r["공항"] or 0) > 0]
    w_lon = w_lat = w_ha = 0.0
    max_sheet = None
    for r in rows_0509:
        c = r["도엽번호"].strip()
        ha = float(r["공항"]) / 10000.0
        xx, yyy = int(c[3:5]), int(c[5:8])
        r50, c50 = (xx - 1) // 4, (xx - 1) % 4
        r5, c5 = (yyy - 1) // 10, (yyy - 1) % 10
        lon_c = 126.0 + c50 * 0.25 + (c5 + 0.5) * 0.025
        lat_c = 38.0 - r50 * 0.25 - (r5 + 0.5) * 0.025
        w_lon += lon_c * ha
        w_lat += lat_c * ha
        w_ha += ha
        if max_sheet is None or ha > max_sheet[1]:
            max_sheet = (c, ha, lon_c, lat_c)
    lcm_w_lon, lcm_w_lat = w_lon / w_ha, w_lat / w_ha

    # 4. Natural Earth ne_10m_airports
    with zipfile.ZipFile(RAW5 / "files/ne_10m_airports.zip") as z:
        base = [n for n in z.namelist() if n.endswith(".shp")][0][:-4]
        r = shapefile.Reader(shp=io.BytesIO(z.read(base + ".shp")), dbf=io.BytesIO(z.read(base + ".dbf")),
                             shx=io.BytesIO(z.read(base + ".shx")), encoding="utf-8")
        flds = [f[0] for f in r.fields[1:]]
        for sr in r.iterShapeRecords():
            rec = dict(zip(flds, sr.record))
            if rec.get("iata_code") == "ICN":
                ne_lon, ne_lat = sr.shape.points[0]
                break

    # 5. OurAirports airports.csv
    for r in csv.DictReader(io.StringIO(read_text_auto(RAW5 / "files/ourairports-airports.csv"))):
        if r.get("ident") == "RKSI":
            oa_lon, oa_lat = float(r["longitude_deg"]), float(r["latitude_deg"])
            break

    # 6. GeoNames KR.zip
    gn_records = {}
    with zipfile.ZipFile(RAW5 / "files/geonames-KR.zip") as zg:
        for line in zg.read("KR.txt").decode("utf-8").splitlines():
            cols = line.split("\t")
            if len(cols) > 14 and cols[0] in ("6300433", "12689633"):
                gn_records[cols[0]] = (float(cols[5]), float(cols[4]), cols[1])

    # 7. OpenStreetMap WAY 316419197 (사전 추출 확인된 값)
    osm_pos_lon, osm_pos_lat = 126.4417093, 37.4634593
    osm_cen_lon, osm_cen_lat = 126.4406244, 37.4645544

    # 8. 행정동 운서1동 대표점 & 영종구 인구중심
    dongs = json.loads((ROOT / "data/build/dongs.json").read_text(encoding="utf-8"))
    unseo1 = next(d for d in dongs if d["code"] == "2815554000")
    unseo_lon, unseo_lat = TO4326.transform(ox + unseo1["rx"] * mpu, oy - unseo1["ry"] * mpu)

    candidates = [
        ("incheon-aip (기준: 전체판 AIP ARP)", aip_lon, aip_lat, "47, Gonghang-ro 424beon-gil, Yeongjong-gu, Incheon", "사전 허락·협의 필요 (공개판 제외)"),
        ("wikidata-q20932 (Wikidata P625/P6375)", wd_lon, wd_lat, wd_addrs[0] if wd_addrs else "22382 인천시 중구 공항로 272", "CC0 1.0 (퍼블릭 도메인)"),
        ("osm-rksi-pos (OSM WAY 316419197 대표점)", osm_pos_lon, osm_pos_lat, "인천광역시 중구 운서동 공항로 272 (22382)", "ODbL 1.0"),
        ("osm-rksi-centroid (OSM WAY 316419197 무게중심)", osm_cen_lon, osm_cen_lat, "인천광역시 중구 운서동 공항로 272 (22382)", "ODbL 1.0"),
        ("data-15150509-max (환경부 세분류 공항 최대도엽 37610018 중심)", max_sheet[2], max_sheet[3], "도엽 37610018 (공항 34.48 ha)", "공공누리 제1유형"),
        ("data-15041331-mid (국가철도공단 공항철도 T1·T2역 중점)", mid_lon, mid_lat, f"{arex_addr['인천공항1터미널']} / {arex_addr['인천공항2터미널']}", "이용허락범위 제한 없음"),
        ("data-15041331-t2 (국가철도공단 공항철도 인천공항2터미널역)", t2_lon, t2_lat, arex_addr["인천공항2터미널"], "이용허락범위 제한 없음"),
        ("data-15150509-weighted (환경부 세분류 공항 9개 도엽 가중중심)", lcm_w_lon, lcm_w_lat, "도엽 37610007~029 (공항 114.86 ha)", "공공누리 제1유형"),
        ("geonames-12689633 (GeoNames 인천국제공항)", gn_records["12689633"][0], gn_records["12689633"][1], "KR.txt 12689633 AIRP", "CC BY 4.0"),
        ("admdong-unseo1 (행정동 경계 운서1동 대표점)", unseo_lon, unseo_lat, "인천광역시 영종구 운서1동 (2815554000)", "CC BY 4.0 (SGIS 제1유형)"),
        ("ourairports-rksi (OurAirports RKSI)", oa_lon, oa_lat, "Incheon International Airport (KR-28)", "Public Domain"),
        ("ne-10m-airports (Natural Earth ICN)", ne_lon, ne_lat, "Incheon Int'l (terminal)", "Public Domain"),
        ("geonames-6300433 (GeoNames Incheon Intl Airport)", gn_records["6300433"][0], gn_records["6300433"][1], "KR.txt 6300433 AIRP", "CC BY 4.0"),
        ("data-15041331-t1 (국가철도공단 공항철도 인천공항1터미널역)", t1_lon, t1_lat, arex_addr["인천공항1터미널"], "이용허락범위 제한 없음"),
        ("data-15041332-t1 (국가철도공단 자기부상 인천공항1터미널역)", mag_t1_lon, mag_t1_lat, "인천국제공항공사 자기부상 인천공항1터미널", "이용허락범위 제한 없음"),
    ]

    table = []
    for label, lon, lat, addr, lic in candidates:
        c, du, sgg, (e, n) = cell_info(lon, lat)
        _, _, dist_geod = GEOD.inv(aip_lon, aip_lat, lon, lat)
        dist_5179 = math.hypot(e - aip_e, n - aip_n)
        row = {
            "source": label,
            "lon": round(lon, 7),
            "lat": round(lat, 7),
            "dist_geod_m": round(dist_geod, 1),
            "dist_5179_m": round(dist_5179, 1),
            "cell": int(c),
            "same_cell_as_aip": int(c) == int(aip_cell),
            "dist_to_cell_center_u": du,
            "sgg_code": sgg["code"] if sgg else None,
            "sgg_name": sgg["name"] if sgg else None,
            "address": addr,
            "license": lic,
        }
        table.append(row)
        print(f"  {label:52s} | ({lon:.5f}, {lat:.5f}) | Δ={dist_geod:6.1f} m | 칸 {c} ({'동일' if c==aip_cell else '인접'}) | {lic}", flush=True)

    # 여객·화물 실적 대조 (airportal-2025 vs datagokr_15002610)
    kac_rows = list(csv.DictReader(io.StringIO(read_text_auto(ROOT / "data/raw/datagokr/transport/15002610_한국공항공사_공항별_여객실적.csv"))))
    kac_icn_2025 = sum(
        int(r["여객성인도착"]) + int(r["여객성인출발"]) + int(r["여객유아도착"]) + int(r["여객유아출발"])
        for r in kac_rows if r["연도"] == "2025" and "인천" in r["공항"]
    )
    ap_tr = list(csv.DictReader(io.StringIO(read_text_auto(ROOT / "data/build/layers/airport_traffic.csv"))))
    airportal_pax = next(int(float(r["value"])) for r in ap_tr if "인천" in r["name"] and r["kind"] == "여객")
    airportal_cargo = next(int(float(r["value"])) for r in ap_tr if "인천" in r["name"] and r["kind"] == "화물")
    print(f"  [실적 대조] 항공정보포털(airportal-2025) 여객={airportal_pax:,}명, 화물={airportal_cargo:,}톤 vs 한국공항공사(15002610) 여객={kac_icn_2025:,}명 (차이 {airportal_pax - kac_icn_2025}명)", flush=True)

    return {
        "aip_cell": int(aip_cell),
        "candidates": table,
        "traffic_verify": {
            "airportal_2025_passengers": airportal_pax,
            "airportal_2025_cargo_t": airportal_cargo,
            "kac_15002610_2025_passengers": kac_icn_2025,
            "exact_match": airportal_pax == kac_icn_2025,
        }
    }


def decode_5k_box(code):
    """NGII 1:5,000 도엽번호(8자리) -> (lon0, lat0, lon1, lat1). 제주(33605~33612)·울릉(37012) 특별도곽 이동 반영."""
    code = code.strip()
    lat_deg, lon_d, xx, yyy = int(code[:2]), int(code[2]), int(code[3:5]), int(code[5:8])
    lon_deg = (120 + lon_d) if lon_d >= 4 else (130 + lon_d)
    r50, c50 = (xx - 1) // 4, (xx - 1) % 4
    r5, c5 = (yyy - 1) // 10, (yyy - 1) % 10
    lon0 = lon_deg + c50 * 0.25 + c5 * 0.025
    lat1 = (lat_deg + 1.0) - r50 * 0.25 - r5 * 0.025
    if code.startswith("336") and 5 <= xx <= 12:
        lat1 -= 0.10   # 제주 특별도곽 (-6분 = -0.10도)
    elif code.startswith("33614"):
        lat1 -= 0.10
        lon0 -= 0.075  # 마라도 특별도곽
    elif code.startswith("37012"):
        lat1 += 0.075  # 울릉 특별도곽 (+4.5분 = +0.075도)
    return lon0, lat1 - 0.025, lon0 + 0.025, lat1


def verify_problem2(world_pub, world_full):
    """문제 2: 토지피복 후보 해법별 전국 및 시험 구역(김제·익산, 인제, 서울, 연천·고성, 제주) 칸 비율 실증 비교."""
    print("\n=== [실증 2] 토지피복 후보 해법별 전국 및 시험 구역 실증 비교 ===", flush=True)
    G = Grid(world_pub["grid"]["cols"], world_pub["grid"]["rows"], world_pub["grid"]["radius"])
    N = G.n
    ox, oy = world_pub["origin_5179"]
    mpu = world_pub["meters_per_unit"]
    R_U = world_pub["grid"]["radius"]
    hex_km2 = world_pub["hex_km2"]
    owner = np.array(world_pub["owner"])
    county = np.array(world_pub["county"])
    land = owner >= 0
    land_idx = np.nonzero(land)[0]
    sggs = [c["code"] for c in world_pub["counties"]]
    sggnm = {c["code"]: c["name"] for c in world_pub["counties"]}
    sgg_sido = {c["code"]: c["sido"] for c in world_pub["counties"]}
    sido_name = {s["code"]: s["name"] for s in world_pub["states"]}

    def m2u(e, n):
        return (np.asarray(e) - ox) / mpu, (oy - np.asarray(n)) / mpu

    # 0. 공식 통계 로드: 공공데이터포털 제1유형 확인된 data-15164500 (2025년 제작/2024년 기준 세분류 시군구 면적 km²) 및 기존 landcover_stats_sgg.csv 대조
    stats_by, stats_nat, stats_blank, stats_year, _ = TR.read_me_stats()
    r_63128 = [r for r in csv.DictReader(io.StringIO(read_text_auto(RAW5 / "files/p2-15163128.csv")))
               if r["기준년도"] == "2024년" and r["통계구분"] == "면적(㎡)"]
    nat_63128 = next(r for r in r_63128 if r["지역구분"] == "전국")
    paddy_63128_ha = (float(nat_63128["경지정리가 된 논"]) + float(nat_63128["경지정리가 안 된 논"])) / 10000.0
    print(f"  [통계 검증] data-15163128(제1유형) 전국 논={paddy_63128_ha:,.1f} ha vs landcover_stats_sgg.csv 전국 논={stats_nat['논']:,.1f} ha", flush=True)

    # 1. 현재 공개판 (world_pub) 및 현재 전체판 (world_full) 칸별 비율 배열 복원 (N × KEYS)
    ALL_KEYS = ["forest", "broadleaf", "conifer", "mixed", "crop", "paddy", "field", "orchard", "greenhouse",
                "built", "grass", "wetland", "bare", "water"]

    def extract_world_shares(w_obj):
        cs = w_obj["cover_share"]
        lc = cs["land_cells"]
        out = {k: np.full(N, np.nan) for k in ALL_KEYS}
        for k in ALL_KEYS:
            if k in cs:
                vals = cs[k]
                for idx_pos, cell_id in enumerate(lc):
                    v = vals[idx_pos]
                    if v is not None:
                        out[k][cell_id] = v / 100.0
        return out

    sh_pub = extract_world_shares(world_pub)
    sh_full = extract_world_shares(world_full)

    # 2. 후보 A: ESA WorldCover 10 m 원자료 -> 50 m 격자(all_touched=False) 칸별 직접 집계 + 팜맵(전북·전남·경남 + 신규 제주 15104491) + KOSIS 논밭 비율
    print("  [후보 A] ESA WorldCover 10 m 원자료 -> 50 m 직접 집계 계산 중...", flush=True)
    t0 = time.time()
    boundary = json.loads((ROOT / "data/raw/boundary/HangJeongDong_ver20261001.geojson").read_text(encoding="utf-8"))
    geoms_5179 = [transform_geom("EPSG:4326", "EPSG:5179", f["geometry"]) for f in boundary["features"] if f["geometry"]]
    res50 = 50
    left, bottom, right, top = 746000.0, 1458500.0, 1388000.0, 2069000.0
    w50, h50 = int((right - left) // res50), int((top - bottom) // res50)
    tf50 = from_origin(left, top, res50, res50)
    esa50 = np.zeros((h50, w50), dtype=np.uint8)
    for tif in sorted((ROOT / "data/raw/layers/A1").glob("ESA_WorldCover_10m_*.tif")):
        with rasterio.open(tif) as src:
            part = np.zeros((h50, w50), dtype=np.uint8)
            reproject(rasterio.band(src, 1), part, src_nodata=0, dst_transform=tf50, dst_crs="EPSG:5179",
                      dst_nodata=0, resampling=Resampling.nearest, num_threads=4)
            use = (esa50 == 0) & (part != 0)
            esa50[use] = part[use]
    inside50 = geometry_mask(geoms_5179, (h50, w50), tf50, all_touched=False, invert=True)
    esa50[~inside50] = 0

    # 50 m 픽셀 -> 칸 번호 매핑 (행 블록 단위로 메모리 절약)
    lut_esa = np.full(256, -1, np.int16)
    for code, key in TR.ESA_TO_COVER.items():
        lut_esa[code] = TR.COVER_KEYS.index(key)
    K_maj = len(TR.COVER_KEYS)
    esa50_cnt = np.zeros((N, K_maj), np.int64)
    cols_idx = np.arange(w50)
    pe_row = left + (cols_idx + 0.5) * res50
    step_r = 500
    for r0 in range(0, h50, step_r):
        r1 = min(h50, r0 + step_r)
        sub = esa50[r0:r1]
        rr, cc = np.nonzero(sub > 0)
        if not len(rr):
            continue
        vals = sub[rr, cc]
        pe = pe_row[cc]
        pn = top - (r0 + rr + 0.5) * res50
        pcell = G.point_to_cell_np(*m2u(pe, pn))
        ok = (pcell >= 0) & land[np.clip(pcell, 0, N - 1)]
        np.add.at(esa50_cnt, (pcell[ok], lut_esa[vals[ok]]), 1)
    del esa50, inside50
    print(f"    ESA 50 m 직접 집계 완료 ({time.time() - t0:.1f}s), 총 육지 픽셀 {esa50_cnt.sum():,}", flush=True)

    # 팜맵: 기존 farmmap.tif (전북·전남·경남 54개 시군) + 신규 다운로드한 제주 팜맵 (p2-15104491.shp) 래스터화
    fm250, fm_meta, _ = TR.read_raster("farmmap.tif")
    jeju_zip = RAW5 / "files/p2-15104491.shp"
    if jeju_zip.exists():
        t_fm = time.time()
        with zipfile.ZipFile(jeju_zip) as zf:
            shp_names = sorted(n for n in zf.namelist() if n.endswith(".shp"))
        _, _, west, _, _, north = fm_meta["transform"]
        pixel = int(fm_meta["res_m"])
        width, height = fm_meta["width"], fm_meta["height"]
        classes_fm = {"01": 1, "02": 2, "03": 3, "04": 4}
        counts_j = np.zeros((4, height, width), dtype=np.uint16)
        factor = 5
        for ds in shp_names:
            vurl = f"/vsizip/{{{jeju_zip.resolve().as_posix()}}}/{ds}"
            meta_j, tbl_j = pyogrio.read_arrow(vurl, columns=["CLSF_CD"], encoding="CP949")
            geom_j = shapely.from_wkb(tbl_j["wkb_geometry"].to_pylist(), on_invalid="raise")
            cats_j = np.array(tbl_j["CLSF_CD"].to_pylist())
            wx, sy, ex, ny = pyogrio.read_info(vurl)["total_bounds"]
            x0 = max(0, math.floor((wx - west) / pixel))
            x1 = min(width, math.ceil((ex - west) / pixel))
            y0 = max(0, math.floor((north - ny) / pixel))
            y1 = min(height, math.ceil((north - sy) / pixel))
            if x1 <= x0 or y1 <= y0:
                continue
            f_shape = ((y1 - y0) * factor, (x1 - x0) * factor)
            f_tf = from_origin(west + x0 * pixel, north - y0 * pixel, pixel / factor, pixel / factor)
            for c_code, b_idx in classes_fm.items():
                sel = geom_j[cats_j == c_code]
                if sel.size:
                    g_r = rasterize(sel, out_shape=f_shape, transform=f_tf, default_value=1, dtype="uint8")
                    tot_r = g_r.reshape(y1 - y0, factor, x1 - x0, factor).sum(axis=(1, 3))
                    counts_j[b_idx - 1, y0:y1, x0:x1] += tot_r.astype(np.uint16)
        dom_j = (counts_j.argmax(axis=0) + 1).astype(np.uint8)
        dom_j[counts_j.max(axis=0) == 0] = 0
        fm250 = np.where(fm250 > 0, fm250, dom_j)
        print(f"    제주 팜맵(15104491) 병합 완료 ({time.time() - t_fm:.1f}s), 제주 팜맵 셀 {int((dom_j > 0).sum()):,}개", flush=True)

    # 팜맵 250 m 셀별 분류 집계 (칸별)
    rr_f, cc_f = np.nonzero(fm250 > 0)
    pe_f, pn_f = TR.raster_centers(fm_meta, rr_f, cc_f)
    pcell_f = G.point_to_cell_np(*m2u(pe_f, pn_f))
    ok_f = (pcell_f >= 0) & land[np.clip(pcell_f, 0, N - 1)]
    fm_cell_cnt = np.zeros((N, 5), np.int64)
    np.add.at(fm_cell_cnt, (pcell_f[ok_f], fm250[rr_f[ok_f], cc_f[ok_f]]), 1)

    from lib import cover_public as CP
    ratio_kosis, _ = CP.county_ratios(sggs, {k: v.replace(" ", "") for k, v in sggnm.items()}, sgg_sido, sido_name)

    sh_esa50 = {k: np.full(N, np.nan) for k in ALL_KEYS}
    esa50_tot = esa50_cnt.sum(1)
    has50 = land & (esa50_tot > 0)
    for k, key in enumerate(TR.COVER_KEYS):
        sh_esa50[key][has50] = esa50_cnt[has50, k] / esa50_tot[has50]
    for i in np.nonzero(has50)[0]:
        i = int(i)
        cr = sh_esa50["crop"][i]
        f_tot = fm_cell_cnt[i, 1:].sum()
        if f_tot > 0:
            sh_esa50["paddy"][i] = cr * (fm_cell_cnt[i, 1] / f_tot)
            sh_esa50["field"][i] = cr * (fm_cell_cnt[i, 2] / f_tot)
            sh_esa50["orchard"][i] = cr * (fm_cell_cnt[i, 3] / f_tot)
            sh_esa50["greenhouse"][i] = cr * (fm_cell_cnt[i, 4] / f_tot)
        else:
            r = ratio_kosis.get(sggs[county[i]])
            rp = r[0] if r else 0.5
            sh_esa50["paddy"][i] = cr * rp
            sh_esa50["field"][i] = cr * (1.0 - rp)

    # 3. 후보 B: 기후에너지환경부 1:5,000 세분류 도엽 통계 (data-15150509, 공공누리 제1유형) 공간 교차 배분
    print("  [후보 B] 기후에너지환경부 1:5,000 세분류 도엽 통계(15150509, 18,538도엽) 칸별 공간 교차 계산 중...", flush=True)
    t_b = time.time()
    rows_0509 = [r for r in csv.DictReader(io.StringIO(read_text_auto(RAW5 / "files/p2-15150509.csv")))
                 if r["제작연도"] == "2025년"]
    M_sheets = len(rows_0509)
    # 14개 키별 도엽 면적(ha) 행렬 (M_sheets × 14)
    sheet_mat = np.zeros((M_sheets, len(ALL_KEYS)), dtype=np.float64)
    sheet_boxes = []
    BUILT_COLS = ["단독주거시설", "공동주거시설", "공업시설", "상업업무시설", "혼합지역", "문화체육휴양시설",
                  "공항", "항만", "철도", "도로", "기타교통통신시설", "환경기초시설", "교육행정시설", "기타공공시설"]
    GRASS_COLS = ["자연초지", "골프장", "묘지", "기타초지"]
    WET_COLS = ["내륙습지", "갯벌", "염전"]
    BARE_COLS = ["해변", "강기슭", "암벽바위", "채광지역", "운동장", "기타나지"]
    WATER_COLS = ["하천", "호소"]

    for m, r in enumerate(rows_0509):
        b4326 = decode_5k_box(r["도엽번호"])
        lon0, lat0, lon1, lat1 = b4326
        ex, ny = TO5179.transform([lon0, lon1, lon1, lon0, lon0], [lat0, lat0, lat1, lat1, lat0])
        sheet_boxes.append(Polygon(list(zip(ex, ny))))
        bl = float(r["활엽수림"] or 0)
        co = float(r["침엽수림"] or 0)
        mx = float(r["혼효림"] or 0)
        pa = float(r["경지정리가된논"] or 0) + float(r["경지정리가안된논"] or 0)
        fi = float(r["경지정리가된밭"] or 0) + float(r["경지정리가안된밭"] or 0)
        orc = float(r["과수원"] or 0)
        gh = float(r["시설재배지"] or 0)
        cr_etc = float(r["목장양식장"] or 0) + float(r["기타재배지"] or 0)
        bu = sum(float(r[c] or 0) for c in BUILT_COLS)
        gr = sum(float(r[c] or 0) for c in GRASS_COLS)
        wt = sum(float(r[c] or 0) for c in WET_COLS)
        ba = sum(float(r[c] or 0) for c in BARE_COLS)
        wa = sum(float(r[c] or 0) for c in WATER_COLS)
        # ALL_KEYS = ["forest", "broadleaf", "conifer", "mixed", "crop", "paddy", "field", "orchard", "greenhouse", "built", "grass", "wetland", "bare", "water"]
        sheet_mat[m] = [bl + co + mx, bl, co, mx, pa + fi + orc + gh + cr_etc, pa, fi, orc, gh, bu, gr, wt, ba, wa]
    sheet_mat /= 10000.0  # ㎡ -> ha
    sheet_boxes = np.array(sheet_boxes, dtype=object)
    sheet_areas = shapely.area(sheet_boxes)

    hex_polys = np.empty(N, dtype=object)
    for i in land_idx:
        cx, cy = G.center(i)
        pts = [(ox + (cx + R_U * math.cos(math.radians(60 * k - 30))) * mpu,
                oy - (cy + R_U * math.sin(math.radians(60 * k - 30))) * mpu) for k in range(6)]
        hex_polys[i] = Polygon(pts)

    stree = shapely.STRtree(sheet_boxes)
    hi_q, si_q = stree.query(hex_polys[land_idx], predicate="intersects")
    inter_areas = shapely.area(shapely.intersection(hex_polys[land_idx[hi_q]], sheet_boxes[si_q]))
    weights = inter_areas / sheet_areas[si_q]

    cell_0509_ha = np.zeros((N, len(ALL_KEYS)), dtype=np.float64)
    np.add.at(cell_0509_ha, land_idx[hi_q], weights[:, None] * sheet_mat[si_q])

    # 분모: 7대분류 합 (forest + crop + built + grass + wetland + bare + water)
    MAJ_IDX = [ALL_KEYS.index(k) for k in ("forest", "crop", "built", "grass", "wetland", "bare", "water")]
    cell_0509_tot = cell_0509_ha[:, MAJ_IDX].sum(1)
    sh_0509 = {k: np.full(N, np.nan) for k in ALL_KEYS}
    ok_0509 = land & (cell_0509_tot > 1.0)  # 도엽 육지 면적 1 ha 이상
    for q_idx, k in enumerate(ALL_KEYS):
        sh_0509[k][ok_0509] = cell_0509_ha[ok_0509, q_idx] / cell_0509_tot[ok_0509]
    # 도엽 미교차 극소수 섬 칸(3칸)은 후보 A(ESA 50m)로 폴백
    fb_0509 = land & ~ok_0509
    for k in ALL_KEYS:
        sh_0509[k][fb_0509] = sh_esa50[k][fb_0509]
    print(f"    1:5,000 도엽 통계 공간 교차 완료 ({time.time() - t_b:.1f}s): 직접 덮임 {int(ok_0509.sum())}/{len(land_idx)}칸 (폴백 {int(fb_0509.sum())}칸)", flush=True)

    # 4. 후보 C: 1:5,000 도엽 통계(15150509) + ESA 50 m 다중해상도 결합 (Dasymetric: 칸 안 대분류 공간변이는 ESA 50m와 도엽 통계의 가중 조화, 세부 비율은 1:5,000 도엽 통계로 정밀 배분)
    sh_hybrid = {k: np.full(N, np.nan) for k in ALL_KEYS}
    # 각 시군구 내 도엽 통계 총량에 맞춰 ESA 50m + 도엽 통계 결합비를 시군구 총량으로 보정
    for k in ALL_KEYS:
        sh_hybrid[k] = sh_0509[k].copy()
    # 도엽 경계에 걸친 칸들의 공간 해상도를 높이기 위해, 각 시군구 안에서 (0.5 * sh_0509 + 0.5 * sh_esa50)의 대분류 분포를 시군구 도엽 합계로 보정(Raking)
    for sgg_c in sggs:
        c_idx = np.nonzero(land & (county == sggs.index(sgg_c)))[0]
        if len(c_idx) == 0:
            continue
        target_maj = np.array([np.nansum(sh_0509[k][c_idx]) for k in TR.COVER_KEYS])
        if target_maj.sum() <= 0:
            continue
        prior_maj = np.column_stack([0.6 * np.nan_to_num(sh_0509[k][c_idx]) + 0.4 * np.nan_to_num(sh_esa50[k][c_idx]) for k in TR.COVER_KEYS])
        # Iterative Proportional Fitting (IPF / Raking) 15회
        for _ in range(15):
            col_s = prior_maj.sum(0)
            col_s = np.where(col_s > 1e-9, col_s, 1.0)
            prior_maj *= (target_maj / col_s)[None, :]
            row_s = prior_maj.sum(1)
            row_s = np.where(row_s > 1e-9, row_s, 1.0)
            prior_maj /= row_s[:, None]
        for k_i, k in enumerate(TR.COVER_KEYS):
            sh_hybrid[k][c_idx] = prior_maj[:, k_i]
        # 세부 비율(활엽·침엽·혼효 및 논·밭·과수·시설)은 해당 칸의 1:5,000 도엽 구성비 그대로 적용
        f_tot_c = np.maximum(1e-9, sh_0509["forest"][c_idx])
        for fk in ("broadleaf", "conifer", "mixed"):
            sh_hybrid[fk][c_idx] = sh_hybrid["forest"][c_idx] * np.nan_to_num(sh_0509[fk][c_idx]) / f_tot_c
        c_tot_c = np.maximum(1e-9, sh_0509["crop"][c_idx])
        sub_sum_c = np.maximum(1e-9, sum(np.nan_to_num(sh_0509[ck][c_idx]) for ck in ("paddy", "field", "orchard", "greenhouse")))
        for ck in ("paddy", "field", "orchard", "greenhouse"):
            sh_hybrid[ck][c_idx] = sh_hybrid["crop"][c_idx] * np.nan_to_num(sh_0509[ck][c_idx]) / sub_sum_c

    # 5. 후보 D: ESA 50 m 직접 집계 + 제1유형 국가토지피복통계(data-15163128 / 15164500) 시군구 합계 보정(Raking)
    sh_raked = {k: sh_esa50[k].copy() for k in ALL_KEYS}
    ST_MAP = {
        "forest": ["활엽수림", "침엽수림", "혼효림"],
        "crop": ["논", "밭", "시설재배지", "과수원", "기타재배지"],
        "built": ["주거지역", "공업지역", "상업지역", "문화·체육·휴양지역", "교통지역", "공공시설지역"],
        "grass": ["자연초지", "인공초지"],
        "wetland": ["내륙습지", "연안습지"],
        "bare": ["자연나지", "인공나지"],
        "water": ["내륙수"],
    }
    for sgg_c in sggs:
        c_idx = np.nonzero(land & (county == sggs.index(sgg_c)))[0]
        if len(c_idx) == 0:
            continue
        st = stats_by.get(sgg_c)
        if not st:
            continue
        t_vec = np.array([sum(st.get(p, 0.0) or 0.0 for p in ST_MAP[k]) for k in TR.COVER_KEYS], dtype=np.float64)
        if t_vec.sum() <= 0:
            continue
        t_vec = t_vec / t_vec.sum() * len(c_idx)
        mat = np.column_stack([np.maximum(1e-4, np.nan_to_num(sh_esa50[k][c_idx])) for k in TR.COVER_KEYS])
        for _ in range(20):
            cs_ = np.where(mat.sum(0) > 1e-9, mat.sum(0), 1.0)
            mat *= (t_vec / cs_)[None, :]
            rs_ = np.where(mat.sum(1) > 1e-9, mat.sum(1), 1.0)
            mat /= rs_[:, None]
        for k_i, k in enumerate(TR.COVER_KEYS):
            sh_raked[k][c_idx] = mat[:, k_i]
        # 활엽·침엽·혼효 분할
        f_st = sum(st.get(p, 0.0) or 0.0 for p in ST_MAP["forest"])
        if f_st > 0:
            sh_raked["broadleaf"][c_idx] = sh_raked["forest"][c_idx] * ((st.get("활엽수림") or 0.0) / f_st)
            sh_raked["conifer"][c_idx] = sh_raked["forest"][c_idx] * ((st.get("침엽수림") or 0.0) / f_st)
            sh_raked["mixed"][c_idx] = sh_raked["forest"][c_idx] * ((st.get("혼효림") or 0.0) / f_st)
        # 논·밭·과수·시설 분할 (팜맵이 있는 칸은 팜맵 비율 우선 후 시군구 합 보정, 없는 칸은 시군구 통계 비율)
        c_st = sum(st.get(p, 0.0) or 0.0 for p in ("논", "밭", "과수원", "시설재배지"))
        if c_st > 0:
            for ck, kor in (("paddy", "논"), ("field", "밭"), ("orchard", "과수원"), ("greenhouse", "시설재배지")):
                sh_raked[ck][c_idx] = sh_raked["crop"][c_idx] * ((st.get(kor) or 0.0) / c_st)

    # 6. 후보 E: 국토교통부 지적기본통계집계(data-15063997, 이용허락범위 제한 없음) 시군구 지목 면적 + ESA 50 m 결합
    sh_cadastral = {k: sh_esa50[k].copy() for k in ALL_KEYS}
    cad_rows = list(csv.DictReader(io.StringIO(read_text_auto(RAW5 / "files/p2-15063997.csv"))))
    cad_by_name = {}
    for r in cad_rows:
        nm_key = r["행정구역"].replace(" ", "")
        jm = r["지목"]
        ar = float(r["면적"] or 0) / 10000.0  # ㎡ -> ha
        cad_by_name.setdefault(nm_key, {})[jm] = cad_by_name.get(nm_key, {}).get(jm, 0.0) + ar
    CAD_MAP = {
        "forest": ["임야"],
        "crop": ["답", "전", "과수원", "목장용지"],
        "built": ["대", "공장용지", "학교용지", "주차장", "주유소용지", "창고용지", "도로", "철도용지", "수도용지", "종교용지", "사적지", "유원지"],
        "grass": ["공원", "체육용지", "묘지"],
        "wetland": ["염전", "양어장", "광천지"],
        "bare": ["잡종지", "제방"],
        "water": ["하천", "구거", "유지"],
    }
    for sgg_c in sggs:
        c_idx = np.nonzero(land & (county == sggs.index(sgg_c)))[0]
        if len(c_idx) == 0:
            continue
        full_nm = (sido_name.get(sgg_sido.get(sgg_c, ""), "") + sggnm.get(sgg_c, "")).replace(" ", "")
        cad = cad_by_name.get(full_nm)
        if not cad:
            # 영종구·검단구 등 2026 신설구는 구 중구·서구 등으로 폴백하거나 건너뜀
            continue
        t_vec = np.array([sum(cad.get(p, 0.0) for p in CAD_MAP[k]) for k in TR.COVER_KEYS], dtype=np.float64)
        if t_vec.sum() <= 0:
            continue
        t_vec = t_vec / t_vec.sum() * len(c_idx)
        mat = np.column_stack([np.maximum(1e-4, np.nan_to_num(sh_esa50[k][c_idx])) for k in TR.COVER_KEYS])
        for _ in range(20):
            cs_ = np.where(mat.sum(0) > 1e-9, mat.sum(0), 1.0)
            mat *= (t_vec / cs_)[None, :]
            rs_ = np.where(mat.sum(1) > 1e-9, mat.sum(1), 1.0)
            mat /= rs_[:, None]
        for k_i, k in enumerate(TR.COVER_KEYS):
            sh_cadastral[k][c_idx] = mat[:, k_i]
        c_cad = sum(cad.get(p, 0.0) for p in ("답", "전", "과수원"))
        if c_cad > 0:
            sh_cadastral["paddy"][c_idx] = sh_cadastral["crop"][c_idx] * (cad.get("답", 0.0) / c_cad)
            sh_cadastral["field"][c_idx] = sh_cadastral["crop"][c_idx] * (cad.get("전", 0.0) / c_cad)
            sh_cadastral["orchard"][c_idx] = sh_cadastral["crop"][c_idx] * (cad.get("과수원", 0.0) / c_cad)
            sh_cadastral["greenhouse"][c_idx] = 0.0

    # 요약 집계 함수: 전국(비교 시군구 231곳 및 전체 5,027칸)과 시험 구역별 비교표 생성
    all_me_sgg = sorted(c for c in sggs if c in stats_by and all(world_full["cover_src"]["src"][pos] == 0 for pos, cid in enumerate(world_full["cover_share"]["land_cells"]) if sggs[county[cid]] == c))
    regions = [
        ("전국_비교시군구_231곳", [i for i in land_idx if sggs[county[i]] in set(all_me_sgg)], all_me_sgg),
        ("전국_전체_5027칸", list(land_idx), [c for c in sggs if c in stats_by]),
        ("평야_김제_익산", [i for i in land_idx if sggs[county[i]] in ("52210", "52140")], ["52210", "52140"]),
        ("산지_강원_인제군", [i for i in land_idx if sggs[county[i]] == "51810"], ["51810"]),
        ("대도시_서울특별시", [i for i in land_idx if sggs[county[i]].startswith("11")], [c for c in sggs if c.startswith("11") and c in stats_by]),
        ("접경_연천_고성군", [i for i in land_idx if sggs[county[i]] in ("41800", "51820")], ["41800", "51820"]),
        ("도서_제주특별자치도", [i for i in land_idx if sggs[county[i]].startswith("50")], ["50110", "50130"]),
    ]

    methods = [
        ("현재_공개판_ESA250m", sh_pub),
        ("현재_전체판_WMS50m", sh_full),
        ("후보A_ESA10m_50m직접+팜맵4도", sh_esa50),
        ("후보B_환경부1대5000도엽통계_15150509", sh_0509),
        ("후보C_1대5000도엽+ESA10m결합", sh_hybrid),
        ("후보D_ESA10m+제1유형통계보정", sh_raked),
        ("후보E_ESA10m+국토부지적통계15063997", sh_cadastral),
    ]

    report_regions = {}
    for reg_name, cells, st_codes in regions:
        cells = np.array(cells, dtype=int)
        # 공식 통계 비율 계산 (해양수 제외 총합계 기준)
        st_tot_ha = sum((stats_by[c]["총합계"] - (stats_by[c].get("해양수") or 0.0)) for c in st_codes)
        st_shares = {
            "forest": sum(sum(stats_by[c][p] for p in ("활엽수림", "침엽수림", "혼효림")) for c in st_codes) / st_tot_ha,
            "broadleaf": sum(stats_by[c]["활엽수림"] for c in st_codes) / st_tot_ha,
            "conifer": sum(stats_by[c]["침엽수림"] for c in st_codes) / st_tot_ha,
            "mixed": sum(stats_by[c]["혼효림"] for c in st_codes) / st_tot_ha,
            "crop": sum(sum(stats_by[c][p] for p in ("논", "밭", "과수원", "시설재배지", "기타재배지")) for c in st_codes) / st_tot_ha,
            "paddy": sum(stats_by[c]["논"] for c in st_codes) / st_tot_ha,
            "field": sum(stats_by[c]["밭"] for c in st_codes) / st_tot_ha,
            "orchard": sum(stats_by[c]["과수원"] for c in st_codes) / st_tot_ha,
            "greenhouse": sum(stats_by[c]["시설재배지"] for c in st_codes) / st_tot_ha,
            "built": sum(sum(stats_by[c][p] for p in ("주거지역", "공업지역", "상업지역", "문화·체육·휴양지역", "교통지역", "공공시설지역")) for c in st_codes) / st_tot_ha,
            "grass": sum(sum(stats_by[c][p] for p in ("자연초지", "인공초지")) for c in st_codes) / st_tot_ha,
            "wetland": sum(sum(stats_by[c][p] for p in ("내륙습지", "연안습지")) for c in st_codes) / st_tot_ha,
            "bare": sum(sum(stats_by[c][p] for p in ("자연나지", "인공나지")) for c in st_codes) / st_tot_ha,
            "water": sum(stats_by[c]["내륙수"] for c in st_codes) / st_tot_ha,
        }
        reg_out = {"n_cells": int(len(cells)), "stats_land_ha": round(st_tot_ha, 1),
                   "official_stats_pct": {k: round(100 * v, 2) for k, v in st_shares.items()}, "methods": {}}
        print(f"\n--- [{reg_name}] ({len(cells)}칸, 통계 육지 {st_tot_ha:,.0f} ha) ---", flush=True)
        print(f"  {'방법':36s} | {'숲':>6s}({'활':>5s}/{'침':>5s}/{'혼':>4s}) | {'농경지':>6s}({'논':>5s}/{'밭':>5s}/{'과수':>4s}/{'시설':>4s}) | {'시가화':>6s} | {'초지':>5s} | {'수역':>5s}", flush=True)
        s = reg_out["official_stats_pct"]
        print(f"  {'공식_국가토지피복통계(2024기준)':36s} | {s['forest']:5.1f}%({s['broadleaf']:4.1f}/{s['conifer']:4.1f}/{s['mixed']:4.1f}) | {s['crop']:5.1f}%({s['paddy']:4.1f}/{s['field']:4.1f}/{s['orchard']:4.1f}/{s['greenhouse']:4.1f}) | {s['built']:5.1f}% | {s['grass']:4.1f}% | {s['water']:4.1f}%", flush=True)

        for m_name, sh_dict in methods:
            m_pct = {}
            for k in ALL_KEYS:
                arr = sh_dict[k][cells]
                valid = arr[~np.isnan(arr)]
                m_pct[k] = round(100.0 * float(valid.mean()), 2) if len(valid) > 0 else None
            # 칸 넓이 × 비율 합(ha) 대비 공식 통계 상대 오차(%)
            rel_err = {}
            for k, kor_items in (("forest", ("활엽수림", "침엽수림", "혼효림")), ("paddy", ("논",)), ("field", ("밭",)), ("built", ("주거지역", "공업지역", "상업지역", "문화·체육·휴양지역", "교통지역", "공공시설지역"))):
                c_ha = float(np.nansum(sh_dict[k][cells])) * hex_km2 * 100.0
                s_ha = sum(sum(stats_by[c][p] for p in kor_items) for c in st_codes)
                rel_err[k] = round(100.0 * (c_ha / s_ha - 1.0), 1) if s_ha > 0 else None
            reg_out["methods"][m_name] = {"pct": m_pct, "area_vs_stats_err_pct": rel_err}
            f_s = f"{m_pct['forest']:5.1f}%" if m_pct['forest'] is not None else "  -  "
            bl_s = f"{m_pct['broadleaf']:4.1f}" if m_pct['broadleaf'] is not None else " -  "
            co_s = f"{m_pct['conifer']:4.1f}" if m_pct['conifer'] is not None else " -  "
            mx_s = f"{m_pct['mixed']:4.1f}" if m_pct['mixed'] is not None else " -  "
            cr_s = f"{m_pct['crop']:5.1f}%" if m_pct['crop'] is not None else "  -  "
            pa_s = f"{m_pct['paddy']:4.1f}" if m_pct['paddy'] is not None else " -  "
            fi_s = f"{m_pct['field']:4.1f}" if m_pct['field'] is not None else " -  "
            or_s = f"{m_pct['orchard']:4.1f}" if m_pct['orchard'] is not None else " -  "
            gh_s = f"{m_pct['greenhouse']:4.1f}" if m_pct['greenhouse'] is not None else " -  "
            bu_s = f"{m_pct['built']:5.1f}%" if m_pct['built'] is not None else "  -  "
            gr_s = f"{m_pct['grass']:4.1f}%" if m_pct['grass'] is not None else " -  "
            wa_s = f"{m_pct['water']:4.1f}%" if m_pct['water'] is not None else " -  "
            print(f"  {m_name:36s} | {f_s}({bl_s}/{co_s}/{mx_s}) | {cr_s}({pa_s}/{fi_s}/{or_s}/{gh_s}) | {bu_s} | {gr_s} | {wa_s}  [오차: 숲{rel_err['forest']:+.1f}%, 논{rel_err['paddy']:+.1f}%, 밭{rel_err['field']:+.1f}%, 시가{rel_err['built']:+.1f}%]", flush=True)
        report_regions[reg_name] = reg_out

    return report_regions


def main():
    world_pub = json.loads((ROOT / "site/data/world.json").read_text(encoding="utf-8"))
    world_full = json.loads((ROOT / "data/build/site_data_full/world.json").read_text(encoding="utf-8"))
    p1_res = verify_problem1(world_pub)
    p2_res = verify_problem2(world_pub, world_full)
    OUT_JSON.write_text(json.dumps({"problem1": p1_res, "problem2": p2_res}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n[완료] 실증 결과 저장: {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()

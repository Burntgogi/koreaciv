"""Collect official Ministry of Climate, Energy and Environment (기후에너지환경부)
mid-level land cover map (중분류 토지피복지도 2025년, EGIS:lv2_2025y) via public WMS
and 2025 (2024-basis) National Land Cover Statistics (국가토지피복통계),
and build the 250 m EPSG:5179 raster + class table + 시군구 statistics CSV.

Run with:
    python -I -B pipeline/collect_landcover_me.py
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import site
import sys
import time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlencode, urlparse

if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

import numpy as np
import openpyxl
import rasterio
import requests
from lib import netguard as NG  # noqa: E402  (감사 08·09: 허용 호스트·HTTPS·리디렉션·크기 상한·RAW 밖 경로)
from bs4 import BeautifulSoup
from PIL import Image
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom

from collect_econ_normalize import FIELDS as STAT_FIELDS, Regions
from lib import crosswalk

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/landcover_me"
OUT = ROOT / "data/build/layers"
REF_RASTER = OUT / "landcover.tif"
BOUNDARY = ROOT / "data/raw/boundary/HangJeongDong_ver20261001.geojson"

AID_BASE = "https://aid.mcee.go.kr"
WMS_BASE = "https://api.mcee.go.kr/geoserver/wms"
WMS_LAYER = "EGIS:lv2_2025y"
WMS_CRS = "EPSG:5179"
TILE_CELLS = 400       # 400 x 400 of 250 m cells = 100 km x 100 km
SUB_FACTOR = 5         # 50 m/px subsampling (5 x 5 = 25 subpixels per 250 m cell)
MIN_DELAY_SEC = 1.2    # >= 1.0 s sequential delay per host

PUBLISHER = "기후에너지환경부 환경공간정보서비스"
LICENSE_DATA = "공공누리 제1유형(출처표시; 단 Open API 이용약관 문서는 비상업·복제제한 조항 병존)"
LICENSE_STATS = "공공누리 제1유형(출처표시)"

# Mapping from 41 fine-level column names in 2025_stats_ntn_lcm.xlsx to 22 mid-level classes.
# Every fine-level column in the workbook must appear exactly once.
FINE_TO_MID = {
    "단독주거시설": (110, "주거지역"),
    "공동주거시설": (110, "주거지역"),
    "공업시설": (120, "공업지역"),
    "상업업무시설": (130, "상업지역"),
    "혼합지역": (130, "상업지역"),
    "문화체육휴양시설": (140, "문화·체육·휴양지역"),
    "공항": (150, "교통지역"),
    "항만": (150, "교통지역"),
    "철도": (150, "교통지역"),
    "도로": (150, "교통지역"),
    "기타교통통신시설": (150, "교통지역"),
    "환경기초시설": (160, "공공시설지역"),
    "교육행정시설": (160, "공공시설지역"),
    "기타공공시설": (160, "공공시설지역"),
    "경지정리가 된 논": (210, "논"),
    "경지정리가 안 된 논": (210, "논"),
    "경지정리가 된 밭": (220, "밭"),
    "경지정리가 안 된 밭": (220, "밭"),
    "시설재배지": (230, "시설재배지"),
    "과수원": (240, "과수원"),
    "목장양식장": (250, "기타재배지"),
    "기타재배지": (250, "기타재배지"),
    "활엽수림": (310, "활엽수림"),
    "침엽수림": (320, "침엽수림"),
    "혼효림": (330, "혼효림"),
    "자연초지": (410, "자연초지"),
    "골프장": (420, "인공초지"),
    "묘지": (420, "인공초지"),
    "기타초지": (420, "인공초지"),
    "내륙습지": (510, "내륙습지"),
    "갯벌": (520, "연안습지"),
    "염전": (520, "연안습지"),
    "해변": (610, "자연나지"),
    "강기슭": (610, "자연나지"),
    "암벽바위": (610, "자연나지"),
    "채광지역": (620, "인공나지"),
    "운동장": (620, "인공나지"),
    "기타나지": (620, "인공나지"),
    "하천": (710, "내륙수"),
    "호소": (710, "내륙수"),
    "해양수": (720, "해양수"),
}

# Pre-reorganization split/merged districts known in crosswalk.SPLITS
SPLIT_RAW_CODES = {
    ("인천광역시", "중구"): "28110",
    ("인천광역시", "동구"): "28140",
    ("인천광역시", "서구"): "28260",
    ("경기도", "화성시"): "41590",
}

STATS_EXCEL_PARAMS = {
    "fileNo": "2025lcm",
    "dataYear": "2025",
    "dataSeCd": "NLS001",
    "orgFileNm": "2025_stats_ntn_lcm",
    "svFileNm": "2025년(2024년_기준)_국가토지피복통계_토지피복지도현황.xlsx",
    "fileNm": "2025년(2024년_기준)_국가토지피복통계_토지피복지도현황",
}


class ThrottledSession(NG.guarded_session_class(requests.Session)):
    """Sequential HTTP session enforcing >= MIN_DELAY_SEC between requests to the same host."""

    def __init__(self, delay=MIN_DELAY_SEC):
        super().__init__()
        self.headers["User-Agent"] = "Mozilla/5.0"
        self.delay = delay
        self.last_by_host = {}
        self.request_counts = {}

    def get_checked(self, url, *, timeout=120):
        host = urlparse(url).netloc
        now = time.monotonic()
        if host in self.last_by_host:
            wait = self.delay - (now - self.last_by_host[host])
            if wait > 0:
                time.sleep(wait)
        self.request_counts[host] = self.request_counts.get(host, 0) + 1
        t0 = time.monotonic()
        resp = self.get(url, timeout=timeout)
        elapsed = time.monotonic() - t0
        self.last_by_host[host] = time.monotonic()
        resp.raise_for_status()
        print(
            f"  [{host} #{self.request_counts[host]}] {resp.status_code} "
            f"{len(resp.content):,} B ({elapsed:.2f}s) {url[:95]}",
            flush=True,
        )
        return resp


class Archive:
    def __init__(self, root=RAW):
        self.root = root
        self.manifest_path = root / "manifest.json"
        self.entries = (
            json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if self.manifest_path.exists()
            else {}
        )

    def has(self, key):
        if key not in self.entries:
            return False
        entry = self.entries[key]
        path = NG.check_path(self.root, entry["file"])
        if not path.is_file() or path.stat().st_size != entry["bytes"]:
            return False
        return True

    def save(self, key, rel_file, data, *, title, publisher, url, license_str, **extra):
        path = NG.check_path(self.root, rel_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        pending = path.with_suffix(path.suffix + ".tmp")
        try:
            pending.write_bytes(data)
            size = pending.stat().st_size
            if size == 0:
                raise ValueError(f"Empty download: {url}")
            sha = hashlib.sha256(data).hexdigest()
            pending.replace(path)
        finally:
            pending.unlink(missing_ok=True)
        entry = {
            "title": title,
            "publisher": publisher,
            "file": rel_file,
            "url": url,
            "retrieved": dt.datetime.now(dt.timezone.utc).isoformat(),
            "sha256": sha,
            "bytes": size,
            "license": license_str,
            **extra,
        }
        self.entries[key] = entry
        self._flush()
        return path

    def _flush(self):
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.manifest_path)

    def path_of(self, key):
        return self.root / self.entries[key]["file"]


def download_static_assets(session, archive):
    assets = [
        (
            "intro-land-html",
            "intro_land.html",
            AID_BASE + "/intro/land.do",
            "환경공간정보서비스 토지피복지도 분류체계·색상표 및 제작현황",
            PUBLISHER,
            LICENSE_STATS,
            b"<",
        ),
        (
            "legend-png",
            "legend.png",
            AID_BASE + "/images/eais/map/legend.png",
            "토지피복지도 공식 범례 이미지",
            PUBLISHER,
            LICENSE_STATS,
            b"\x89PNG",
        ),
        (
            "wms-capabilities",
            "wms_capabilities.xml",
            WMS_BASE + "?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetCapabilities",
            "환경공간정보서비스 GeoServer WMS GetCapabilities",
            PUBLISHER,
            LICENSE_DATA,
            b"<?xml",
        ),
        (
            "wms-legend-lv2-2025y",
            "getlegend_lv2_2025y.png",
            WMS_BASE + "?" + urlencode({
                "SERVICE": "WMS",
                "VERSION": "1.1.1",
                "REQUEST": "GetLegendGraphic",
                "LAYER": WMS_LAYER,
                "FORMAT": "image/png",
            }),
            "EGIS:lv2_2025y WMS GetLegendGraphic 범례",
            PUBLISHER,
            LICENSE_DATA,
            b"\x89PNG",
        ),
        (
            "stats-ntn-lcm-2025",
            "2025_stats_ntn_lcm.xlsx",
            AID_BASE + "/intro/downloadExcel.do?" + urlencode(STATS_EXCEL_PARAMS),
            "2025년(2024년 기준) 국가토지피복통계 토지피복지도 현황",
            PUBLISHER,
            LICENSE_STATS,
            b"PK",
        ),
    ]
    for key, rel_file, url, title, pub, lic, magic in assets:
        if archive.has(key):
            print(f"  [cached] {rel_file}", flush=True)
            continue
        resp = session.get_checked(url)
        if not (resp.content.lstrip().startswith(magic) if magic == b"<" else resp.content.startswith(magic)):
            raise ValueError(f"Unexpected payload for {key}: starts with {resp.content[:32]!r}")
        archive.save(key, rel_file, resp.content, title=title, publisher=pub, url=url, license_str=lic)


def parse_official_classes(intro_html_path):
    """Parse official 22 mid-level classes (code, 대분류, 중분류, RGB) from intro_land.html."""
    soup = BeautifulSoup(intro_html_path.read_bytes(), "html.parser")
    target_table = None
    for tbl in soup.find_all("table"):
        txt = tbl.get_text(" ", strip=True)
        if "대분류 (7개 항목)" in txt and "중분류 (22개 항목)" in txt and "활엽수림" in txt:
            target_table = tbl
            break
    if target_table is None:
        raise ValueError("Could not find official classification color table in intro_land.html")

    # Expand rowspans into a clean 2D grid of cell texts.
    grid = []
    spans = {}
    for tr in target_table.find_all("tr"):
        row = []
        col = 0
        for td in tr.find_all(["th", "td"]):
            while col in spans:
                val, rem = spans[col]
                row.append(val)
                if rem == 1:
                    del spans[col]
                else:
                    spans[col] = (val, rem - 1)
                col += 1
            text = re.sub(r"\s+", " ", td.get_text(" ", strip=True))
            rs = int(td.get("rowspan") or 1)
            cs = int(td.get("colspan") or 1)
            for _ in range(cs):
                row.append(text)
                if rs > 1:
                    spans[col] = (text, rs - 1)
                col += 1
        while col in spans:
            val, rem = spans[col]
            row.append(val)
            if rem == 1:
                del spans[col]
            else:
                spans[col] = (val, rem - 1)
            col += 1
        grid.append(row)

    # Columns in the table:
    # 0: 대분류명, 1: 대분류코드, 2: 대분류색(빈칸), 3..5: 대분류 R,G,B
    # 6: 중분류명, 7: 중분류코드, 8: 중분류색(빈칸), 9..11: 중분류 R,G,B
    seen = {}
    for row in grid:
        if len(row) < 12:
            continue
        if not re.fullmatch(r"\d{3}", row[7]):
            continue
        code = int(row[7])
        if code in seen:
            continue
        major = row[0].replace(" ", "")
        # Normalize minor name cleanly (strip parenthetical note like "(수변식생)" for consistency? Keep official text cleanly spaced)
        minor = re.sub(r"\s*·\s*", "·", row[6]).strip()
        minor = re.sub(r"\s+", " ", minor)
        r, g, b = int(row[9]), int(row[10]), int(row[11])
        seen[code] = {
            "code": code,
            "major": major,
            "minor": minor,
            "rgb": (r, g, b),
            "hex": f"#{r:02X}{g:02X}{b:02X}",
        }

    if len(seen) != 22:
        raise ValueError(f"Expected 22 mid-level classes, parsed {len(seen)}: {sorted(seen)}")
    # Verify RGB uniqueness
    rgbs = [v["rgb"] for v in seen.values()]
    if len(set(rgbs)) != 22:
        raise ValueError("Duplicate RGB colors in parsed mid-level classification table")
    return [seen[k] for k in sorted(seen)]


def load_reference_grid():
    with rasterio.open(REF_RASTER) as ds:
        profile = ds.profile.copy()
        bounds = ds.bounds
        width, height = ds.width, ds.height
        transform = ds.transform
        res = int(ds.res[0])
    boundary = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    geoms = [
        transform_geom("EPSG:4326", WMS_CRS, f["geometry"])
        for f in boundary["features"]
        if f["geometry"]
    ]
    inside = geometry_mask(geoms, (height, width), transform, all_touched=True, invert=True)
    return profile, bounds, width, height, transform, res, inside


def compute_land_tiles(bounds, width, height, res, inside):
    tiles = []
    idx = 0
    for ty in range(0, height, TILE_CELLS):
        h_c = min(TILE_CELLS, height - ty)
        for tx in range(0, width, TILE_CELLS):
            w_c = min(TILE_CELLS, width - tx)
            n_land = int(inside[ty : ty + h_c, tx : tx + w_c].sum())
            if n_land == 0:
                continue
            x0 = int(bounds.left) + tx * res
            x1 = int(bounds.left) + (tx + w_c) * res
            y1 = int(bounds.top) - ty * res
            y0 = int(bounds.top) - (ty + h_c) * res
            tiles.append({
                "index": idx,
                "key": f"wms-tile-T{idx:02d}",
                "file": f"tiles/lv2_2025y_T{idx:02d}.png",
                "tx": tx,
                "ty": ty,
                "w_c": w_c,
                "h_c": h_c,
                "w_px": w_c * SUB_FACTOR,
                "h_px": h_c * SUB_FACTOR,
                "bbox": (x0, y0, x1, y1),
                "n_land": n_land,
            })
            idx += 1
    return tiles


def download_wms_tiles(session, archive, tiles):
    print(f"Downloading {len(tiles)} WMS tiles ({WMS_LAYER}, {WMS_CRS}, 50 m/px)...", flush=True)
    for t in tiles:
        if archive.has(t["key"]):
            print(f"  [cached] {t['file']}", flush=True)
            continue
        x0, y0, x1, y1 = t["bbox"]
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetMap",
            "LAYERS": WMS_LAYER,
            "STYLES": "",
            "SRS": WMS_CRS,
            "BBOX": f"{x0},{y0},{x1},{y1}",
            "WIDTH": str(t["w_px"]),
            "HEIGHT": str(t["h_px"]),
            "FORMAT": "image/png",
            "TRANSPARENT": "true",
            "FORMAT_OPTIONS": "antialias:none",
        }
        url = WMS_BASE + "?" + urlencode(params)
        resp = session.get_checked(url, timeout=180)
        if not resp.content.startswith(b"\x89PNG"):
            raise ValueError(f"Non-PNG WMS response for {t['key']}: {resp.text[:400]}")
        archive.save(
            t["key"],
            t["file"],
            resp.content,
            title=f"토지피복 중분류 [2025] 전국 WMS 타일 T{t['index']:02d} (50 m)",
            publisher=PUBLISHER,
            url=url,
            license_str=LICENSE_DATA,
            layer=WMS_LAYER,
            srs=WMS_CRS,
            bbox=list(t["bbox"]),
            pixels=[t["w_px"], t["h_px"]],
        )


def build_raster(archive, classes, profile, width, height, inside, tiles):
    rgb_to_idx = {c["rgb"]: i + 1 for i, c in enumerate(classes)}
    idx_to_code = np.array([0] + [c["code"] for c in classes], dtype=np.uint16)
    n_classes = len(classes)

    # Pack RGB into a single 24-bit integer for fast exact lookup (zero nearest-color matching!)
    lut_packed = np.zeros(1 << 24, dtype=np.uint8)
    for (r, g, b), idx in rgb_to_idx.items():
        lut_packed[(r << 16) | (g << 8) | b] = idx

    raster = np.zeros((height, width), dtype=np.uint16)
    stats = {
        "total_subpixels": 0,
        "opaque_subpixels": 0,
        "semitransparent_subpixels": 0,
        "transparent_subpixels": 0,
        "matched_opaque_subpixels": 0,
        "unknown_opaque_subpixels": 0,
        "unknown_rgb_samples": {},
        "land_subpixels_opaque": 0,
        "land_subpixels_transparent": 0,
        "land_subpixels_unknown_opaque": 0,
    }

    for t in tiles:
        im = Image.open(archive.path_of(t["key"])).convert("RGBA")
        if im.size != (t["w_px"], t["h_px"]):
            raise ValueError(f"Unexpected tile size for {t['file']}: {im.size} != {(t['w_px'], t['h_px'])}")
        arr = np.array(im, dtype=np.uint8)
        alpha = arr[:, :, 3]
        opaque = alpha == 255
        semi = (alpha > 0) & (alpha < 255)
        trans = alpha == 0

        packed = (
            (arr[:, :, 0].astype(np.uint32) << 16)
            | (arr[:, :, 1].astype(np.uint32) << 8)
            | arr[:, :, 2].astype(np.uint32)
        )
        cls_idx = np.where(opaque, lut_packed[packed], 0).astype(np.uint8)

        unk_opaque = opaque & (cls_idx == 0)
        stats["total_subpixels"] += int(alpha.size)
        stats["opaque_subpixels"] += int(opaque.sum())
        stats["semitransparent_subpixels"] += int(semi.sum())
        stats["transparent_subpixels"] += int(trans.sum())
        stats["matched_opaque_subpixels"] += int((cls_idx > 0).sum())
        n_unk = int(unk_opaque.sum())
        stats["unknown_opaque_subpixels"] += n_unk
        if n_unk > 0:
            u_vals, u_cnts = np.unique(packed[unk_opaque], return_counts=True)
            for v, c in zip(u_vals.tolist(), u_cnts.tolist()):
                hex_c = f"#{v:06X}"
                stats["unknown_rgb_samples"][hex_c] = stats["unknown_rgb_samples"].get(hex_c, 0) + c

        # Subpixel stats inside land mask
        land_sub = np.repeat(
            np.repeat(inside[t["ty"] : t["ty"] + t["h_c"], t["tx"] : t["tx"] + t["w_c"]], SUB_FACTOR, axis=0),
            SUB_FACTOR,
            axis=1,
        )
        stats["land_subpixels_opaque"] += int((land_sub & opaque).sum())
        stats["land_subpixels_transparent"] += int((land_sub & trans).sum())
        stats["land_subpixels_unknown_opaque"] += int((land_sub & unk_opaque).sum())

        # 5x5 mode aggregation ignoring 0 (NoData/unknown); ties broken by smallest class code
        blocks = (
            cls_idx.reshape(t["h_c"], SUB_FACTOR, t["w_c"], SUB_FACTOR)
            .transpose(0, 2, 1, 3)
            .reshape(t["h_c"], t["w_c"], SUB_FACTOR * SUB_FACTOR)
        )
        counts = np.zeros((t["h_c"], t["w_c"], n_classes), dtype=np.uint8)
        for k in range(1, n_classes + 1):
            counts[:, :, k - 1] = (blocks == k).sum(axis=2)
        best_idx = counts.argmax(axis=2) + 1
        best_cnt = counts.max(axis=2)
        tile_codes = idx_to_code[best_idx]
        tile_codes[best_cnt == 0] = 0
        raster[t["ty"] : t["ty"] + t["h_c"], t["tx"] : t["tx"] + t["w_c"]] = tile_codes

    # Mask outside South Korea land boundary to 0 (same as landcover.tif)
    raster[~inside] = 0

    out_profile = profile.copy()
    out_profile.update(dtype="uint16", nodata=0, count=1, compress="deflate", tiled=True)
    out_tif = OUT / "landcover_me.tif"
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_tif, "w", **out_profile) as dst:
        dst.write(raster, 1)
        dst.update_tags(
            source="기후에너지환경부 환경공간정보서비스 중분류 토지피복지도 2025년 (EGIS:lv2_2025y)",
            wms_url=WMS_BASE,
            fetch_resolution_m=str(250 // SUB_FACTOR),
            resampling="mode_5x5_exact_rgb_no_antialias",
            license=LICENSE_DATA,
            classification=json.dumps({str(c["code"]): c["minor"] for c in classes}, ensure_ascii=False),
        )

    land_total = int(inside.sum())
    land_classified = int((inside & (raster > 0)).sum())
    land_zero = land_total - land_classified
    print(
        f"landcover_me.tif: {width}x{height} uint16, classified={land_classified:,}/{land_total:,} "
        f"({land_classified/land_total*100:.2f}%), land_zero={land_zero:,} ({land_zero/land_total*100:.2f}%), "
        f"unknown_opaque_subpx={stats['unknown_opaque_subpixels']:,}",
        flush=True,
    )
    return raster, stats


def write_classes_csv(classes):
    path = OUT / "landcover_me_classes.csv"
    with NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        writer = csv.writer(f)
        writer.writerow(["code", "대분류", "중분류", "범례 색"])
        for c in classes:
            writer.writerow([c["code"], c["major"], c["minor"], c["hex"]])
    tmp.replace(path)
    print(f"landcover_me_classes.csv: {len(classes)} classes", flush=True)


def build_stats_sgg_csv(archive, classes):
    xlsx_path = archive.path_of("stats-ntn-lcm-2025")
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb["25년_시군구_토지피복지도"]
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    headers = [str(h).strip() if h is not None else "" for h in rows[2]]
    fine_cols = headers[4:]
    missing_fine = set(fine_cols) - set(FINE_TO_MID)
    extra_fine = set(FINE_TO_MID) - set(fine_cols)
    if missing_fine or extra_fine:
        raise ValueError(f"Column mismatch in Excel: missing={missing_fine}, extra={extra_fine}")

    # Build ordered list of 22 mid-level names
    mid_names_ordered = sorted(set(FINE_TO_MID.values()))
    mid_col_indices = {name: [] for _, name in mid_names_ordered}
    for col_idx, col_name in enumerate(headers[4:], start=4):
        _, mid_name = FINE_TO_MID[col_name]
        mid_col_indices[mid_name].append(col_idx)

    regions = Regions()
    current_codes = set(regions.by_code.keys())

    # Verify crosswalk.SPLITS consistency for the known split districts
    for (sido, sgg), old_code in SPLIT_RAW_CODES.items():
        targets = crosswalk.to_current(old_code, current_codes)
        if not targets:
            raise ValueError(f"Crosswalk check failed for {old_code}")

    out_rows = []
    source_id = "mcee-stats-ntn-lcm-2025"
    basis = "2024년 기준·2025년 세분류 토지피복지도 집계·중분류 합산"
    year = "2024"
    unit = "ha"

    def to_ha(val_m2):
        if val_m2 is None or val_m2 == "":
            return ""
        d = (Decimal(str(val_m2)) / Decimal("10000")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        s = format(d, "f").rstrip("0").rstrip(".")
        return s if s else "0"

    n_districts = 0
    n_mapped = 0
    n_split = 0

    for row in rows[3:]:
        kind = str(row[2] or "").strip()
        if "면적" not in kind:
            continue
        sido_raw = str(row[0] or "").strip()
        sgg_raw = str(row[1] or "").strip()

        if sido_raw == "전국":
            sgg_code_raw = ""
            sgg_name_raw = "전국"
            sgg_code_now = ""
            sido_now = "전국"
        else:
            n_districts += 1
            sgg_code_raw = ""
            sgg_name_raw = sgg_raw
            code_now, sido_now, _ = regions.resolve(sgg_raw, sido_raw)
            if code_now:
                # Confirm via crosswalk (read-only) that code_now is valid current code
                mapped = crosswalk.to_current(code_now, current_codes)
                if mapped != [code_now]:
                    raise ValueError(f"Unexpected crosswalk result for {code_now}: {mapped}")
                sgg_code_now = code_now
                n_mapped += 1
            elif (sido_raw, sgg_raw) in SPLIT_RAW_CODES:
                # Pre-reorganization split/merged district: keep sgg_code_now empty (do not distribute)
                sgg_code_now = ""
                n_split += 1
            else:
                raise ValueError(f"Unmapped 시군구 in stats Excel: {sido_raw} / {sgg_raw}")

        # Verify total equals sum of 41 fine classes within 1 m2
        total_m2 = Decimal(str(row[3] or 0))
        sum_fine_m2 = sum(Decimal(str(row[i] or 0)) for i in range(4, len(headers)))
        if abs(total_m2 - sum_fine_m2) > Decimal("1.0"):
            raise ValueError(f"Row total mismatch for {sido_raw} {sgg_raw}: {total_m2} vs {sum_fine_m2}")

        out_rows.append((
            sgg_code_raw, sgg_name_raw, sgg_code_now, sido_now, year,
            "총합계", "", to_ha(total_m2), unit, basis, source_id,
        ))
        for _, mid_name in mid_names_ordered:
            mid_m2 = sum(Decimal(str(row[i] or 0)) for i in mid_col_indices[mid_name])
            out_rows.append((
                sgg_code_raw, sgg_name_raw, sgg_code_now, sido_now, year,
                mid_name, "", to_ha(mid_m2), unit, basis, source_id,
            ))

    path = OUT / "landcover_stats_sgg.csv"
    with NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
        writer = csv.writer(f)
        writer.writerow(STAT_FIELDS)
        writer.writerows(out_rows)
    tmp.replace(path)
    print(
        f"landcover_stats_sgg.csv: {len(out_rows):,} rows "
        f"(전국 + {n_districts} 시군구: {n_mapped} current-code mapped, {n_split} pre-split)",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-download", action="store_true", help="Rebuild outputs from cached raw files only")
    args = parser.parse_args()

    archive = Archive()
    profile, bounds, width, height, transform, res, inside = load_reference_grid()
    tiles = compute_land_tiles(bounds, width, height, res, inside)

    with ThrottledSession() as session:
        if not args.skip_download:
            download_static_assets(session, archive)
            download_wms_tiles(session, archive, tiles)
        print(f"HTTP requests made in this run: {session.request_counts}", flush=True)

    classes = parse_official_classes(archive.path_of("intro-land-html"))
    write_classes_csv(classes)
    build_raster(archive, classes, profile, width, height, inside, tiles)
    build_stats_sgg_csv(archive, classes)


if __name__ == "__main__":
    main()

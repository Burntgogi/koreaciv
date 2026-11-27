"""지도 층 (명세 5a): 불가사의·자원·기반시설 -> site/data/{wonders,resources,infrastructure}.json, 유산 렌즈 -> lenses.json

입력 (모두 이미 받아 둔 원자료, 읽기만): data/raw/datagokr/…, data/raw/heritage/khs_*.xml, data/raw/naturalearth/ne_10m_{roads,railroads}.zip
원자료는 신뢰할 수 없는 입력으로 다룬다: 압축은 메모리에서만 풀고, 원자료 폴더를 작업 디렉터리로 삼지 않는다.

위치 정밀도
  point  : 원자료 좌표가 든 칸 (육지 칸이 아니면 두 칸 안의 가장 가까운 육지 칸)
  area   : 경계 폴리곤의 대표점이 든 칸
  county : 주소에서 시군구까지만 알아내 그 시군구의 읍면동 인구 가중 중심에 가장 가까운 자기 칸
주소에서 시군구도 못 알아내면 지도에 싣지 않고 빠진 수를 센다. 외부 지오코딩은 쓰지 않는다.
"""
import collections
import csv
import io
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import shapefile
import shapely
from pyproj import Transformer
from shapely.geometry import Polygon, shape

from lib import popstats
from lib.address import AddressResolver, nospace
from lib.common import build, load_json, raw, rnd, save_json, site
from lib.hexgrid import Grid

TO5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
SIMPLIFY_M = 300.0
VERSION = "phase5a"

F_PARKS = ("datagokr_15017313", "datagokr/wonders/15017313_국립공원공단_국립공원_공원경계.zip")
F_WH = ("datagokr_15107994", "datagokr/wonders/15107994_국가유산청_한국의_유네스코_세계유산_정보.csv")
F_WHV = ("datagokr_15087524", "datagokr/wonders/15087524_국가유산청_세계유산_관람객_현황.csv")
F_HER = {"국보": ("heritage_11", "heritage/khs_11_국보.xml"), "사적": ("heritage_13", "heritage/khs_13_사적.xml"),
         "명승": ("heritage_15", "heritage/khs_15_명승.xml"), "천연기념물": ("heritage_16", "heritage/khs_16_천연기념물.xml")}
F_NUC = ("datagokr_15046076", "datagokr/energy/15046076_원자력안전위원회_국내_원자력발전소_현황.csv")
F_DAM = ("datagokr_15049846", "datagokr/energy/15049846_한국수자원공사_댐별_제원_정보.csv")
F_NIC = ("datagokr_15085874", "datagokr/industry/15085874_한국산업단지공단_전국산업단지현황통계_국가산업단지.csv")
F_GIC = ("datagokr_15085886", "datagokr/industry/15085886_한국산업단지공단_전국산업단지현황통계_일반.csv")
F_PORT = ("datagokr_15059868", "datagokr/specialty/15059868_해양수산부_어촌_어항_현황.zip")
F_MIN_M = ("datagokr_3077829", "datagokr/minerals/3077829_한국광해광업공단_전국광산_통계_현황(금속광산).csv")
F_MIN_N = ("datagokr_15067760", "datagokr/minerals/15067760_한국광해광업공단_전국광산_통계_현황(비금속광산).csv")
F_MIN_K = ("datagokr_15067761", "datagokr/minerals/15067761_한국광해광업공단_전국광산_통계_현황(광종별_현황).csv")
F_RAIL = ("datagokr_15067652", "datagokr/transport/15067652_국가철도공단_철도역_정보.csv")
F_AIR = ("datagokr_15002610", "datagokr/transport/15002610_한국공항공사_공항별_여객실적.csv")
F_ROADS = ("ne_ne_10m_roads", "naturalearth/ne_10m_roads.zip")
F_RAILS = ("ne_ne_10m_railroads", "naturalearth/ne_10m_railroads.zip")

CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"


def log(*a):
    print("[layers]", *a, flush=True)


def read_csv(rel):
    b = open(raw(*rel.split("/")), "rb").read()
    for enc in ("utf-8-sig", "cp949"):
        try:
            t = b.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"인코딩을 알 수 없음: {rel}")
    rows = list(csv.reader(io.StringIO(t)))
    hdr = [h.strip() for h in rows[0]]
    return hdr, [[c.strip() for c in r] for r in rows[1:] if any(c.strip() for c in r)]


def num(s):
    s = (s or "").replace(",", "").strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def zip_names(z):
    """zip 안 이름: 한글 이름이 cp437 로 읽힌 경우 cp949 로 되돌린다."""
    out = {}
    for i in z.infolist():
        nm = i.filename
        if not (i.flag_bits & 0x800):
            try:
                nm = nm.encode("cp437").decode("cp949")
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
        out[nm] = i
    return out


class World:
    def __init__(self):
        self.w = load_json(site("world.json"))
        w = self.w
        self.G = Grid(w["grid"]["cols"], w["grid"]["rows"], w["grid"]["radius"])
        self.N = self.G.n
        self.owner = np.array(w["owner"])
        self.county = np.array(w["county"])
        self.foreign = np.array(w["foreign"])
        self.land = self.owner >= 0
        self.ox, self.oy = w["origin_5179"]
        self.mpu = w["meters_per_unit"]
        self.codes = [c["code"] for c in w["counties"]]
        self.code_of = np.array([self.codes[k] if k >= 0 else "" for k in self.county], dtype=object)
        self.sido_of_code = {c["code"]: c["sido"] for c in w["counties"]}
        self.cname = {c["code"]: c["name"] for c in w["counties"]}
        self.centers = np.array([self.G.center(i) for i in range(self.N)])
        npz = np.load(build("world_samples.npz"))
        self.samp, self.offs = npz["samp"], npz["offs"]

    def m2u(self, e, n):
        return (np.asarray(e) - self.ox) / self.mpu, (self.oy - np.asarray(n)) / self.mpu

    def lonlat2u(self, lon, lat):
        e, n = TO5179.transform(lon, lat)
        return self.m2u(e, n)

    def ring(self, c, d):
        seen, frontier, out = {c}, [c], [c]
        for _ in range(d):
            nxt = []
            for f in frontier:
                for nb in self.G.neighbors(f):
                    if nb not in seen:
                        seen.add(nb)
                        nxt.append(nb)
            out += nxt
            frontier = nxt
        return out

    def snap(self, ux, uy, maxd=2):
        """화면 좌표 -> 육지 칸. 육지가 아니면 maxd 칸 안의 가장 가까운 육지 칸. (칸, 사유)"""
        c = self.G.point_to_cell(float(ux), float(uy))
        if c < 0:
            return None, "격자 밖"
        if self.land[c]:
            return c, None
        cand = [k for k in self.ring(c, maxd) if self.land[k]]
        if not cand:
            return None, "남한 범위 밖"
        k = min(cand, key=lambda k: (self.centers[k][0] - ux) ** 2 + (self.centers[k][1] - uy) ** 2)
        return k, None

    def near_codes(self, c):
        return {self.code_of[k] for k in [c] + self.G.neighbors(c) if self.land[k]}


def load_heritage(W, resolver):
    """국가유산 목록(국보·사적·명승·천연기념물 XML) -> (좌표가 유효한 항목, 종류별 원자료 수, 뺀 이유별 수). 5d 세계유산 구성 유산 대응에도 쓴다."""
    her = []
    her_excl = collections.Counter()
    her_raw = collections.Counter()
    for kind, (key, rel) in F_HER.items():
        txt = open(raw(*rel.split("/")), encoding="utf-8").read()
        pages = [p for p in txt.split("<!--page-->") if p.strip()]
        tot = None
        n_items = 0
        for p in pages:
            root = ET.fromstring(p.strip().encode("utf-8"))
            tot = int(root.findtext("totalCnt") or 0)
            for it in root.findall("item"):
                n_items += 1
                d = {e.tag: (e.text or "").strip() for e in it}
                her_raw[kind] += 1
                if d.get("ccbaCncl", "N") != "N":
                    her_excl[(kind, "지정 해제")] += 1
                    continue
                lon, lat = num(d.get("longitude")), num(d.get("latitude"))
                if not lon or not lat:
                    her_excl[(kind, "좌표 0 또는 없음")] += 1
                    continue
                ux, uy = W.lonlat2u(lon, lat)
                c, why = W.snap(ux, uy)
                if c is None:
                    her_excl[(kind, why)] += 1
                    continue
                r = resolver.resolve(d.get("ccsiName", ""), sido_hint=d.get("ccbaCtcdNm", ""))
                her.append({"kind": kind, "name": d.get("ccbaMnm1", ""), "cell": c, "lon": lon, "lat": lat,
                            "codes": sorted(r["codes"]) if r else None, "asno": d.get("ccbaAsno"), "ctcd": d.get("ccbaCtcd")})
        if tot != n_items:
            raise ValueError(f"{kind}: totalCnt {tot} != 항목 {n_items}")
    return her, her_raw, her_excl


def main():
    W = World()
    w = W.w
    cities = load_json(site("cities.json"))
    states = load_json(site("states.json"))
    lenses = load_json(site("lenses.json"))
    manifest = load_json(raw("manifest.json"))
    dongs = load_json(build("dongs.json"))
    resolver = AddressResolver(w, cities)
    sido_name = {s["code"]: s["name"] for s in w["states"]}
    city_of_code = {}
    for c in cities:
        for s in c["sgg"]:
            city_of_code[s] = c["id"]

    def src(key_file):
        k, rel = key_file
        e = manifest.get(k, {})
        return {"key": k, "title": e.get("title"), "publisher": e.get("publisher"), "retrieved": (e.get("retrieved") or "")[:10],
                "file": rel}

    # ---------- 시군구 단위의 인구 가중 중심 칸 (county 정밀도) ----------
    _, _, f_emd, _ = popstats.latest_files()
    dpop = {}
    if f_emd:
        rec, _ = popstats.dong_population(f_emd, dongs)
        dpop = {d["code"]: rec[d["code"]]["total"] for d in dongs}
    center_cache = {}

    def unit_center(codes):
        codes = frozenset(codes)
        if codes in center_cache:
            return center_cache[codes]
        items = [(d["rx"], d["ry"], dpop.get(d["code"], 0)) for d in dongs if d["sgg"] in codes]
        own = np.nonzero(np.isin(W.code_of, list(codes)) & W.land)[0]
        if not len(own):
            raise ValueError(f"칸이 없는 단위 {sorted(codes)}")
        tw = sum(i[2] for i in items)
        if tw > 0:
            px = sum(i[0] * i[2] for i in items) / tw
            py = sum(i[1] * i[2] for i in items) / tw
        else:
            px, py = W.centers[own].mean(0)
        k = int(own[np.argmin(((W.centers[own] - [px, py]) ** 2).sum(1))])
        center_cache[codes] = k
        return k

    def county_names(codes):
        return " · ".join(W.cname[c] for c in sorted(codes))

    def base_item(kind, name, cell, precision, codes, **kw):
        codes = sorted(codes)
        sd = W.sido_of_code[codes[0]]
        it = {"id": None, "kind": kind, "name": name, "cell": int(cell), "precision": precision, "sgg": codes, "sido": sd,
              "city": city_of_code.get(codes[0]) if all(city_of_code.get(c) == city_of_code.get(codes[0]) for c in codes) else None,
              "place": f"{sido_name[sd]} {county_names(codes)}"}
        it.update(kw)
        return it

    def place_point_or_county(lon, lat, unit):
        """좌표가 있으면 point. 좌표 칸(또는 이웃)의 시군구가 주소의 시군구와 다르면 좌표를 믿지 않고 county."""
        if lon and lat:
            ux, uy = W.lonlat2u(lon, lat)
            c, why = W.snap(ux, uy)
            if c is not None and (unit is None or W.near_codes(c) & set(unit)):
                return c, "point", None
            if unit is None:
                return None, None, why or "좌표 칸이 육지가 아님"
            reason = "좌표가 주소의 시군구와 맞지 않아 주소로 놓음" if c is not None else f"좌표가 {why}라 주소로 놓음"
            return unit_center(unit), "county", reason
        if unit is None:
            return None, None, "좌표와 주소가 모두 없음"
        return unit_center(unit), "county", "좌표가 없어 주소로 놓음"

    # =====================================================================
    # 불가사의
    # =====================================================================
    W_items, W_kinds = [], {}

    # ---------- 국립공원 ----------
    z = zipfile.ZipFile(raw(*F_PARKS[1].split("/")))
    names = zip_names(z)
    base = next(n for n in names if n.lower().endswith(".shp"))[:-4]
    prj = z.read(names[base + ".prj"]).decode("utf-8", "replace")
    if "Korea_2000_Korea_Unified" not in prj and "5179" not in prj:
        raise ValueError(f"국립공원 경계 좌표계가 EPSG:5179 가 아님: {prj[:80]}")
    shp = shapefile.Reader(shp=io.BytesIO(z.read(names[base + ".shp"])), dbf=io.BytesIO(z.read(names[base + ".dbf"])),
                           shx=io.BytesIO(z.read(names[base + ".shx"])), encoding="cp949")
    flds = [f[0] for f in shp.fields[1:]]
    park_recs = []
    for sr in shp.iterShapeRecords():
        d = dict(zip(flds, sr.record))
        g = shapely.make_valid(shape(sr.shape.__geo_interface__))
        park_recs.append((d, g))
    n_park_raw = len(park_recs)
    # 표본점 (칸 × 37) 을 EPSG:5179 로
    spx = (W.centers[:, None, 0] + W.offs[None, :, 0]).ravel()
    spy = (W.centers[:, None, 1] + W.offs[None, :, 1]).ravel()
    spe, spn = W.ox + spx * W.mpu, W.oy - spy * W.mpu
    S = W.offs.shape[0]
    half = S // 2 + 1
    pts = shapely.points(spe, spn)
    ptree = shapely.STRtree(pts)
    on_kr = (W.samp >= 0).ravel()
    parks = []
    for k, (d, g) in enumerate(park_recs):
        idx = ptree.query(g, predicate="contains")
        cnt = np.bincount(idx // S, minlength=W.N)
        kr_frac = float(on_kr[idx].mean()) if len(idx) else 0.0
        marine = kr_frac < 0.5
        cells = [int(c) for c in np.nonzero((cnt >= half) & W.land)[0]]
        rule_used = f"표본점 {half}개 이상"
        if not cells:
            cand = np.nonzero((cnt > 0) & W.land)[0]
            if len(cand):
                cells = [int(cand[np.argmax(cnt[cand])])]
                rule_used = "표본점 과반 칸이 없어 표본점이 가장 많은 육지 칸"
        rp = g.point_on_surface()
        ux, uy = W.m2u(rp.x, rp.y)
        c0 = W.G.point_to_cell(float(ux), float(uy))
        icon = c0 if c0 in cells else (min(cells, key=lambda c: (W.centers[c][0] - ux) ** 2 + (W.centers[c][1] - uy) ** 2) if cells else None)
        nm = str(d.get("NPK_NM", "")).strip()
        spans = sorted({W.code_of[c] for c in cells})
        park = {"id": f"park-{k}", "code": str(d.get("NPK_CD", "")).strip(), "name": nm + ("국립공원" if not nm.endswith("국립공원") else ""),
                "short": nm, "area_km2": round(g.area / 1e6, 2), "marine": marine, "land_sample_share": round(kr_frac, 3),
                "cells": cells, "icon_cell": icon, "spans": spans, "cells_rule": rule_used, "visitors": None,
                "boundary_date": str(d.get("CRT_YMD", "")).strip()}
        parks.append(park)
        if icon is None:
            continue
        W_items.append(base_item("national_park", park["name"], icon, "area", [W.code_of[icon]], ref=park["id"],
                                 value=park["area_km2"], unit="km²", year=park["boundary_date"][:4] or None,
                                 source=F_PARKS[0],
                                 detail=[f"경계 폴리곤 넓이 {park['area_km2']:,} km²" + (" (해상·해안 공원: 바다 포함)" if marine else "")
                                         + " — 파일의 경계가 '공원경계버퍼'라 공식 공원 면적보다 클 수 있음",
                                         f"덮는 육지 칸 {len(cells)}개 · 걸친 시군구 {len(spans)}곳",
                                         "탐방객: 5b 에서 붙임 (설악산 한 곳만 있는 파일은 쓰지 않음)"]))
    area_sum = round(sum(p["area_km2"] for p in parks), 2)
    W_kinds["national_park"] = {
        "name": "국립공원", "group": "wonders", "count": len(parks), "raw_count": n_park_raw,
        "rule": (f"국립공원공단 공원경계 파일의 공원 {n_park_raw}곳 전부. 넓이는 경계 폴리곤(EPSG:5179)에서 계산했다(합 {area_sum:,} km²). "
                 f"압축 안 도형 이름이 '공원경계버퍼'(BSI_NPK_BBNDR)라 경계 바깥 완충 띠가 포함된 것으로 보이며, 이 넓이는 공식 공원 면적보다 "
                 "크게 나올 수 있다(공식 면적은 이 파일에 없어 비교하지 않았다). "
                 f"공원이 덮는 칸은 칸의 표본점 {S}개 중 {half}개 이상이 폴리곤 안인 대한민국 육지 칸이다. 해상·해안 공원(폴리곤 안 표본점 가운데 "
                 "육지 점이 절반 미만)도 같은 규칙이라 섬·해안의 육지 칸만 남는다. 아이콘은 폴리곤 대표점(point_on_surface)이 든 칸, 그 칸이 "
                 "공원 칸이 아니면 대표점에 가장 가까운 공원 칸. 탐방객은 5b 에서 붙인다(필드는 null)."),
        "source": [src(F_PARKS)], "year": "경계 작성일 " + ", ".join(sorted({p["boundary_date"] for p in parks})),
        "missing": [{"name": p["name"], "reason": "덮는 육지 칸 없음"} for p in parks if p["icon_cell"] is None],
        "precision_note": "area (폴리곤 대표점)"}
    log(f"국립공원 {len(parks)}곳 (원자료 {n_park_raw}), 넓이 합 {area_sum:,} km², 해상·해안 {[p['short'] for p in parks if p['marine']]}")

    # ---------- 국가유산 (국보·사적·명승·천연기념물) ----------
    her, her_raw, her_excl = load_heritage(W, resolver)
    n_valid = len(her)
    log(f"국가유산 원자료 {dict(her_raw)}, 좌표 유효 {n_valid}, 뺀 것 {dict(her_excl)}")

    # 유산 렌즈: 칸별 건수 (육지 칸, 0 은 0)
    hcount = np.zeros(W.N, int)
    hk = collections.defaultdict(collections.Counter)
    for h in her:
        hcount[h["cell"]] += 1
        hk[h["cell"]][h["kind"]] += 1
    lens_vals = [int(hcount[i]) if W.land[i] else None for i in range(W.N)]

    # 국가유산 밀집지: 국보 + 사적 칸별 건수 상위 칸
    ns_cnt = collections.Counter()
    ns_names = collections.defaultdict(list)
    for h in her:
        if h["kind"] in ("국보", "사적"):
            ns_cnt[h["cell"]] += 1
            ns_names[h["cell"]].append([h["kind"], h["name"]])
    dist = collections.Counter(ns_cnt.values())
    thr = None
    for t in range(1, max(ns_cnt.values()) + 2):
        if sum(1 for v in ns_cnt.values() if v >= t) <= 50:
            thr = t
            break
    hot = sorted([c for c, v in ns_cnt.items() if v >= thr], key=lambda c: -ns_cnt[c])
    dist_txt = ", ".join(f"{k}건 {v}칸" for k, v in sorted(dist.items()))
    log(f"국보·사적 칸별 건수 분포: {dist_txt}; 기준 {thr}건 이상 -> {len(hot)}칸")
    for c in hot:
        lst = sorted(ns_names[c], key=lambda t: (t[0] != "국보", t[1]))
        W_items.append(base_item("heritage_cluster", f"국가유산 밀집지 ({W.cname[W.code_of[c]]})", c, "point", [W.code_of[c]],
                                 value=ns_cnt[c], unit="건", year=None, source="heritage_11+heritage_13",
                                 list=lst, detail=[f"국보 {sum(1 for t in lst if t[0] == '국보')} · 사적 {sum(1 for t in lst if t[0] == '사적')}건 (좌표가 이 칸에 든 것)"]))
    W_kinds["heritage_cluster"] = {
        "name": "국가유산 밀집지", "group": "wonders", "count": len(hot),
        "rule": (f"국보·사적 가운데 지정 해제되지 않고 좌표가 있는 건을 칸에 세었다(좌표가 바다 칸이면 두 칸 안의 가장 가까운 육지 칸). "
                 f"칸별 건수 분포는 {dist_txt}. 아이콘 수가 30–50칸이 되도록, 칸 수가 50 이하가 되는 가장 작은 기준인 "
                 f"'{thr}건 이상'인 칸 {len(hot)}곳에 둔다. 낱개 국보·사적은 그리지 않고 패널에 이름 목록을 싣는다. "
                 "국보에는 박물관에 있는 동산 유물이 많아 국립박물관이 있는 칸이 높게 나온다."),
        "source": [src(F_HER["국보"]), src(F_HER["사적"])], "year": "목록 수집 시점",
        "missing": [], "excluded": {f"{k}·{r}": v for (k, r), v in her_excl.items() if k in ("국보", "사적")},
        "precision_note": "point (칸에 센 값)"}

    # ---------- 세계유산 ----------
    hdr, rows = read_csv(F_WH[1])
    ix = {h: i for i, h in enumerate(hdr)}
    vh, vrows = read_csv(F_WHV[1])
    vyears = [h for h in vh[1:]]

    def vkey(s):
        return re.sub(r"[^가-힣]", "", s).replace("과", "").replace("와", "")

    vis = {vkey(r[0]): r for r in vrows}
    def strip_region(nm):
        ws = nm.split()
        return nospace(" ".join(ws[1:])) if len(ws) > 1 else nospace(nm)

    her_strip = [(strip_region(h["name"]), h) for h in her]
    whs = []
    wh_missing = []
    for r in rows:
        name = r[ix["세계유산명"]]
        text = r[ix["내용"]] + " " + r[ix.get("세계유산적가치", ix["내용"])]
        toks = [nospace(re.sub(r"^한국의\s*", "", t.strip())) for t in re.split(r"[,:]|과\s|와\s", name) if t.strip()]
        comp = []
        for st, h in her_strip:
            if any(st == t or (len(t) >= 3 and st.startswith(t)) for t in toks):
                comp.append(h)
        located_by = "이름 대응" if comp else None
        if not comp:
            tx = nospace(text)
            comp = [h for st, h in her_strip if h["kind"] == "사적" and len(st) >= 3 and st in tx]
            located_by = "내용 문장의 사적 이름" if comp else None
        # 같은 칸은 하나로
        by_cell = {}
        for h in comp:
            by_cell.setdefault(h["cell"], []).append(h)
        k_ = vkey(name)
        vr = vis.get(k_) or next((v for kk, v in vis.items() if kk and (kk in k_ or k_ in kk)), None)
        series = None
        visitors = None
        if vr:
            series = {vyears[j].replace("년", ""): (int(num(x)) if num(x) is not None else None) for j, x in enumerate(vr[1:])}
            yrs = [y for y, v in series.items() if v is not None]
            if yrs:
                visitors = {"year": max(yrs), "value": series[max(yrs)], "matched": vr[0]}
        wid = f"wh-{r[ix['연번']]}"
        entry = {"id": wid, "no": r[ix["연번"]], "name": name, "located_by": located_by, "visitors": visitors,
                 "visitor_series": series, "link": r[ix.get("링크", 0)] if "링크" in ix else None,
                 "components": []}
        for c, hs in by_cell.items():
            h = hs[0]
            codes = h["codes"] if h["codes"] else [W.code_of[c]]
            entry["components"].append({"cell": int(c), "names": [f"{x['kind']} {x['name']}" for x in hs], "sgg": codes})
            W_items.append(base_item("world_heritage", name, c, "point", codes, ref=wid,
                                     value=visitors["value"] if visitors else None, unit="명" if visitors else None,
                                     year=visitors["year"] if visitors else None, source=F_WH[0],
                                     component=" · ".join(f"{x['kind']} {x['name']}" for x in hs),
                                     detail=[f"이 아이콘의 위치: {hs[0]['kind']} {hs[0]['name']}{' 외 ' + str(len(hs) - 1) + '건' if len(hs) > 1 else ''} 의 좌표 ({located_by})",
                                             (f"관람객 {visitors['value']:,}명 ({visitors['year']}, 관람객 현황 '{visitors['matched']}')" if visitors
                                              else "관람객 자료 없음")]))
        if not by_cell:
            wh_missing.append({"name": name, "reason": "파일에 좌표·주소가 없고, 이름이나 내용 문장에서 국가유산 목록과 대응되는 구성 유산을 찾지 못함"})
        whs.append(entry)
    n_wh_placed = sum(1 for e in whs if e["components"])
    W_kinds["world_heritage"] = {
        "name": "세계유산", "group": "wonders", "count": len(whs), "placed": n_wh_placed,
        "rule": ("국가유산청 '한국의 유네스코 세계유산 정보' 파일의 등재 건 전부(한 행 = 한 등재 건). 파일에 좌표·주소가 없어 구성 유산의 위치를 "
                 "국가유산 목록(국보·사적·명승·천연기념물, 좌표 있음)에서 찾는다: (1) 세계유산 이름을 쉼표·쌍점·'과/와'로 나눈 낱말과, "
                 "국가유산 이름에서 맨 앞 지역 낱말을 뗀 나머지가 같거나(3글자 이상 낱말은 그 낱말로 시작하면) 구성 유산으로 본다. "
                 "(2) (1)로 하나도 못 찾으면 '내용' 문장에 이름(지역 낱말 뗀 것, 3글자 이상)이 그대로 나오는 사적을 구성 유산으로 본다. "
                 "같은 칸의 구성 유산은 아이콘 하나로 그린다. 관람객은 '세계유산 관람객 현황'에서 이름이 같은 행(띄어쓰기·문장부호·'과/와' 무시)의 "
                 "값이 있는 마지막 연도를 붙인다."),
        "source": [src(F_WH), src(F_WHV)], "year": "관람객 " + (vyears[-1] if vyears else ""),
        "missing": wh_missing, "precision_note": "point (대응된 국가유산의 좌표)"}
    log(f"세계유산 {len(whs)}건, 위치 찾음 {n_wh_placed}, 못 찾음 {[m['name'] for m in wh_missing]}")
    for e in whs:
        log(f"   {e['name']}: {e['located_by']} {[cc['names'] for cc in e['components']]} 관람객 {e['visitors']}")

    # =====================================================================
    # 자원
    # =====================================================================
    R_items, R_kinds, R_unplaced = [], {}, []

    # ---------- 원전 ----------
    hdr, rows = read_csv(F_NUC[1])
    ix = {h: i for i, h in enumerate(hdr)}
    sites = collections.OrderedDict()
    tot_op = {"units": 0, "mw": 0.0}
    for r in rows:
        st = r[ix["구분"]]
        nm = r[ix["발전소명"]]
        site_nm = nm[1:] if nm.startswith("신") else nm
        s = sites.setdefault(site_nm, {"operating": [], "stopped": [], "construction": [], "names": set(), "cap2": set()})
        s["names"].add(nm)
        mw = num(r[ix["용량1(MWe)"]])
        unit = {"name": f"{nm} {r[ix['호기']]}", "mw": mw, "type": r[ix["노형"]], "start": r[ix["상업운전개시일"]],
                "design_end": r[ix["설계수명만료일"]]}
        if st == "운영원전":
            s["operating"].append(unit)
            s["cap2"].add(num(r[ix["용량2(MWe)"]]))
            tot_op["units"] += 1
            tot_op["mw"] += mw or 0
        elif st == "정지원전":
            s["stopped"].append(unit)
        elif st == "건설원전":
            s["construction"].append(unit)
        else:
            raise ValueError(f"원전 구분 값을 모름: {st}")
    nuc_sites = []
    for nm, s in sites.items():
        mw = sum(u["mw"] or 0 for u in s["operating"])
        check = sorted(x for x in s["cap2"] if x is not None)
        nuc_sites.append({"id": f"nuc-{nm}", "kind": "nuclear", "name": f"{nm} 원전 (본부 단위)", "site": nm,
                          "members": sorted(s["names"]), "value": mw, "unit": "MW", "units_operating": len(s["operating"]),
                          "stopped": s["stopped"], "construction": s["construction"], "operating": s["operating"],
                          "cap2_in_file": check, "cap2_matches": (len(check) == 1 and abs(check[0] - mw) < 0.5) if check else None,
                          "placed": False, "reason": "원자료에 좌표·주소 필드가 없어 위치를 정할 수 없음"})
    R_unplaced += nuc_sites
    R_kinds["nuclear"] = {
        "name": "원전", "group": "resources", "count": len(nuc_sites), "placed": 0,
        "totals": {"operating_units": tot_op["units"], "operating_mw": tot_op["mw"],
                   "stopped_units": sum(len(s["stopped"]) for s in nuc_sites),
                   "construction_units": sum(len(s["construction"]) for s in nuc_sites)},
        "rule": ("원자력안전위원회 '국내 원자력발전소 현황'에서 구분이 '운영원전'인 호기를 발전소 이름 앞의 '신'을 뗀 이름(신고리→고리, "
                 "신월성→월성, 신한울→한울)으로 묶어 본부(부지) 단위 설비용량(용량1 합, MW)과 호기 수를 낸다. 이렇게 묶은 합은 파일의 "
                 "'용량2'(부지 합계)와 같다. 정지·건설 중 호기는 따로 센다. 파일에 좌표·주소가 없어 지도에 놓지 않았다(5b 에서 위치 자료를 붙임)."),
        "source": [src(F_NUC)], "year": "파일 수집 시점",
        "missing": [{"name": s["name"], "reason": s["reason"]} for s in nuc_sites], "precision_note": "없음 (위치 없음)"}
    log(f"원전 본부 {len(nuc_sites)}곳, 운영 {tot_op['units']}기 {tot_op['mw']:,.0f} MW, 용량2 일치 {[s['cap2_matches'] for s in nuc_sites]}")

    # ---------- 댐 ----------
    hdr, rows = read_csv(F_DAM[1])
    ix = {h: i for i, h in enumerate(hdr)}
    dams = []
    for r in rows:
        dams.append({"id": f"dam-{r[ix['시설명']]}", "kind": "dam", "name": f"{r[ix['시설명']]}댐", "type": r[ix["종류"]],
                     "value": num(r[ix["총저수용량"]]), "unit": "백만㎥", "completed": r[ix["준공일"]], "height_m": num(r[ix["높이"]]),
                     "placed": False, "reason": "원자료에 좌표·주소 필드가 없어 위치를 정할 수 없음 (댐 이름은 주소가 아님)"})
    R_unplaced += dams
    R_kinds["dam"] = {
        "name": "댐", "group": "resources", "count": len(dams), "placed": 0,
        "rule": ("한국수자원공사 '댐별 제원 정보'의 댐 전부. 값은 총저수용량(파일에 단위 표기가 없으며 K-water 제원표의 백만㎥ 단위로 읽었다). "
                 "파일에 좌표도 주소도 없어 지도에 놓지 않았다. 댐 이름(예: 충주·대청)을 시군구 이름에 맞추는 것은 주소가 아니라서 하지 않았다."),
        "source": [src(F_DAM)], "year": "파일 수집 시점",
        "missing": [{"name": d["name"], "reason": d["reason"]} for d in dams], "precision_note": "없음 (위치 없음)"}

    # ---------- 산업단지 ----------
    def complex_units(rel):
        hdr, rows = read_csv(rel)
        hdr = [h.strip() for h in hdr]
        ix = {h: i for i, h in enumerate(hdr)}
        units, cur = [], None
        for r in rows:
            nm = r[ix["단지명"]]
            if re.search(r"\(\s*①", nm):
                kind = "parent"
            elif re.search(r"\(\s*[②-⑳]", nm):
                kind = "subparent"
            elif re.search(f"[{CIRCLED}]\\s*$", nm):
                kind = "comp"
            else:
                kind = "single"
            rec = {"sido": r[ix["시도"]], "sgg": r[ix["시군"]], "name": nm, "state": r[ix["조성상태"]],
                   "area": num(r[ix["지정면적(천제곱미터)"]]), "tenants": num(r[ix["입주업체(개)"]]),
                   "operating": num(r[ix["가동업체(개)"]])}
            if kind in ("parent", "single"):
                cur = dict(rec, parts=[], kind=kind)
                units.append(cur)
            elif kind == "comp":
                if cur is None or cur["kind"] != "parent":
                    raise ValueError(f"상위 단지 없이 나온 구성 단지: {nm}")
                cur["parts"].append(rec)
        return units, len(rows)

    nic, n_nic_rows = complex_units(F_NIC[1])
    nic_missing = []
    for k, u in enumerate(nic):
        r_ = resolver.resolve(u["sgg"], sido_hint=u["sido"])
        if r_ is None:
            nic_missing.append({"name": u["name"], "reason": f"소재지 '{u['sido']} {u['sgg']}' 를 현재 시군구에 대응하지 못함"})
            continue
        spans = set(r_["codes"])
        for p in u["parts"]:
            rp_ = resolver.resolve(p["sgg"], sido_hint=p["sido"])
            if rp_:
                spans |= set(rp_["codes"])
        nm = re.sub(r"\s*\([^()]*[①-⑳][^()]*\)\s*$", "", u["name"]).strip()
        c = unit_center(r_["codes"])
        det = [f"입주 {int(u['tenants']):,} · 가동 {int(u['operating']):,}곳" if u["tenants"] is not None and u["operating"] is not None else "입주·가동 업체 자료 없음",
               f"지정면적 {u['area'] / 1000:,.2f} km² · 조성 {u['state']}" if u["area"] is not None else f"조성 {u['state']}"]
        if u["parts"]:
            det.append("구성: " + ", ".join(f"{p['name']} ({p['sido']} {p['sgg']})" for p in u["parts"]))
        if len(spans) > len(r_["codes"]):
            det.append("걸친 시군구: " + county_names(spans))
        R_items.append(base_item("industrial_national", nm, c, "county", r_["codes"], value=u["operating"], unit="곳 가동",
                                 year=None, source=F_NIC[0], tenants=u["tenants"], area_km2=rnd(u["area"] / 1000, 3) if u["area"] is not None else None,
                                 spans=sorted(spans), status=u["state"], detail=det, city_level=r_["city_level"]))
    R_kinds["industrial_national"] = {
        "name": "국가산업단지", "group": "resources", "count": len(nic), "placed": len(nic) - len(nic_missing),
        "rule": ("한국산업단지공단 전국산업단지현황통계(국가) 파일의 단지 전부. 파일은 여러 지구로 된 단지를 '(① + ②)' 표시가 붙은 상위 행과 "
                 "①②… 표시가 붙은 구성 행으로 나눠 적으므로, 상위 행과 홀로 있는 행만 단지로 센다(구성 행은 '걸친 곳'으로 적는다). "
                 "값은 파일에 있는 가동업체 수(입주업체 수·지정면적은 패널에). 고용·생산·수출은 이 파일에 없다. 위치는 파일의 시도·시군 표기의 "
                 "시군구(일반구가 없으면 시 전체)의 인구 가중 중심 칸(county)이다. 여러 시군구에 걸친 단지는 상위 행의 소재지에 놓는다."),
        "source": [src(F_NIC)], "year": "파일에 기준 시점 없음 (수집 시점)", "raw_rows": n_nic_rows,
        "missing": nic_missing, "precision_note": "county"}
    log(f"국가산업단지 {len(nic)}곳 (원자료 {n_nic_rows}행), 대응 실패 {len(nic_missing)}")

    gic, n_gic_rows = complex_units(F_GIC[1])
    g_unit = collections.defaultdict(lambda: {"count": 0, "area_km2": 0.0, "operating": 0, "tenants": 0, "area_na": 0, "names": []})
    gic_missing = []
    for u in gic:
        r_ = resolver.resolve(u["sgg"], sido_hint=u["sido"])
        if r_ is None:
            gic_missing.append({"name": u["name"], "reason": f"소재지 '{u['sido']} {u['sgg']}' 대응 실패"})
            continue
        g = g_unit["+".join(sorted(r_["codes"]))]
        g["count"] += 1
        if u["area"] is None:
            g["area_na"] += 1
        else:
            g["area_km2"] += u["area"] / 1000
        g["operating"] += u["operating"] or 0
        g["tenants"] += u["tenants"] or 0
        g["names"].append(re.sub(r"\s*\([^()]*[①-⑳][^()]*\)\s*$", "", u["name"]).strip())

    def gsum(pred):
        out = {"count": 0, "area_km2": 0.0, "operating": 0, "tenants": 0, "units": []}
        for k, g in g_unit.items():
            codes = set(k.split("+"))
            if pred(codes):
                out["count"] += g["count"]
                out["area_km2"] += g["area_km2"]
                out["operating"] += g["operating"]
                out["tenants"] += g["tenants"]
                out["units"].append({"sgg": sorted(codes), "place": county_names(codes), "count": g["count"],
                                     "area_km2": round(g["area_km2"], 3), "names": g["names"]})
        out["area_km2"] = round(out["area_km2"], 3)
        return out if out["count"] else None

    gic_city = {c["id"]: v for c in cities if (v := gsum(lambda cs, c=c: cs <= set(c["sgg"])))}
    gic_sido = {s["code"]: v for s in w["states"] if (v := gsum(lambda cs, s=s: all(W.sido_of_code[x] == s["code"] for x in cs)))}
    for v in gic_sido.values():
        v.pop("units", None)
    R_kinds["industrial_general"] = {
        "name": "일반산업단지 (시군구 합계)", "group": "resources", "count": len(gic), "placed": None,
        "rule": ("한국산업단지공단 전국산업단지현황통계(일반) 파일의 단지(상위 행과 홀로 있는 행)를 낱개로 그리지 않고, 시군 표기의 시군구별로 "
                 "단지 수·지정면적·입주·가동업체 수를 더해 도시·시도 패널에 싣는다."),
        "source": [src(F_GIC)], "year": "파일에 기준 시점 없음 (수집 시점)", "raw_rows": n_gic_rows,
        "missing": gic_missing, "precision_note": "시군구 합계 (지도 아이콘 없음)"}
    log(f"일반산업단지 {len(gic)}곳 (원자료 {n_gic_rows}행), 대응 실패 {len(gic_missing)}, 도시 {len(gic_city)}곳에 합계")

    # ---------- 국가어항 ----------
    z = zipfile.ZipFile(raw(*F_PORT[1].split("/")))
    names = zip_names(z)
    pf = next((n for n in names if "어항" in n and n.lower().endswith(".csv")), None)
    if pf is None:
        raise ValueError(f"어항 zip 안에 어항 목록 CSV 가 없음: {list(names)}")
    t = z.read(names[pf]).decode("cp949")
    prow = list(csv.reader(io.StringIO(t)))
    phdr = [nospace(h) for h in prow[0]]
    pix = {h: i for i, h in enumerate(phdr)}
    port_missing = []
    n_ports = 0
    for r in prow[1:]:
        if not any(x.strip() for x in r):
            continue
        n_ports += 1
        nm, addr = r[pix["항명"]].strip(), r[pix["주소"]].strip()
        r_ = resolver.resolve(addr)
        if r_ is None:
            port_missing.append({"name": nm, "reason": f"주소 '{addr}' 대응 실패"})
            continue
        R_items.append(base_item("port", nm, unit_center(r_["codes"]), "county", r_["codes"], value=None, unit=None, year=None,
                                 source=F_PORT[0], address=addr, detail=[f"주소: {addr}", "국가어항 (어항 현황 목록)"],
                                 city_level=r_["city_level"]))
    R_kinds["port"] = {
        "name": "국가어항", "group": "resources", "count": n_ports, "placed": n_ports - len(port_missing),
        "rule": (f"해양수산부 '어촌 어항 현황' 압축 안의 '{pf}'는 개별 어항 목록(항명·주소)이다. 명세대로 국가어항만 아이콘으로 두고, "
                 "위치는 주소의 시군구 인구 가중 중심 칸(county)이다. 같은 압축의 '어촌현황'(시군구별 어촌 읍면동 목록)은 이번에 쓰지 않았다."),
        "source": [src(F_PORT)], "year": "파일 작성 2020-06 (압축 안 파일 날짜)", "missing": port_missing, "precision_note": "county"}
    log(f"국가어항 {n_ports}곳, 대응 실패 {len(port_missing)}")

    # ---------- 광산 (시도 집계) ----------
    def mine_by_sido(rel):
        hdr, rows = read_csv(rel)
        ix = {h: i for i, h in enumerate(hdr)}
        dates = sorted({r[ix["기준일"]] for r in rows})
        last = dates[-1]
        out, unk = {}, []
        for r in rows:
            if r[ix["기준일"]] != last or r[ix["운영상태"]] != "가행광":
                continue
            for h in hdr[2:]:
                sd, rest = resolver.sido_of(h)
                if sd is None or rest:
                    unk.append(h)
                    continue
                v = num(r[ix[h]])
                if v is None:
                    out.setdefault(sd, None)
                    continue
                out[sd] = (out.get(sd) or 0) + int(v)
        if unk:
            raise ValueError(f"광산 파일의 시도 이름을 모름: {unk}")
        return out, last

    mm, mm_d = mine_by_sido(F_MIN_M[1])
    mn, mn_d = mine_by_sido(F_MIN_N[1])
    hdr, rows = read_csv(F_MIN_K[1])
    ix = {h: i for i, h in enumerate(hdr)}
    kd = max(r[ix["기준일"]] for r in rows)
    kr_ = next(r for r in rows if r[ix["기준일"]] == kd and r[ix["운영상태"]] == "가행광")
    mines_nat = {"date": kd, "metal": num(kr_[ix["금속광산"]]), "nonmetal": num(kr_[ix["비금속광산"]]), "coal": num(kr_[ix["석탄광산"]])}
    minerals = {"by_sido": {sd: {"metal": mm.get(sd), "nonmetal": mn.get(sd)} for sd in sorted(set(mm) | set(mn))},
                "metal_date": mm_d, "nonmetal_date": mn_d, "national": mines_nat,
                "check": {"metal_sum": sum(v for v in mm.values() if v), "nonmetal_sum": sum(v for v in mn.values() if v)}}
    R_kinds["mines"] = {
        "name": "가행 광산 (시도 집계)", "group": "resources", "count": None, "placed": None,
        "rule": (f"한국광해광업공단 전국광산 통계: 시도별 금속·비금속 가행광 수(기준 {mm_d[:4]}년 말)를 시도 패널에 싣는다. 개별 광산 좌표가 없어 "
                 "지도 아이콘은 없다. 원자료의 광주·전남 칸은 전남광주통합특별시로, 강원·전북은 특별자치도로 더했다. 석탄광은 전국 합계만 있다."),
        "source": [src(F_MIN_M), src(F_MIN_N), src(F_MIN_K)], "year": f"{mm_d} (금속), {mn_d} (비금속), {kd} (광종별 전국)",
        "missing": [], "precision_note": "시도 합계"}
    log(f"광산: 금속 가행 {minerals['check']['metal_sum']} ({mm_d}), 비금속 {minerals['check']['nonmetal_sum']} ({mn_d}), 전국 {mines_nat}")

    # =====================================================================
    # 기반시설
    # =====================================================================
    I_items, I_kinds, I_unplaced = [], {}, []

    # ---------- 철도역 ----------
    hdr, rows = read_csv(F_RAIL[1])
    ix = {h: i for i, h in enumerate(hdr)}
    st_missing, st_excl, st_fallback = [], collections.Counter(), []
    n_pass = 0
    for r in rows:
        work = r[ix["취급업무"]]
        if "객취급" not in work:
            st_excl[f"여객 취급 아님 ('{work}')"] += 1
            continue
        n_pass += 1
        nm = r[ix["역이름"]]
        addr = r[ix["주소"]]
        r_ = resolver.resolve(addr)
        lat, lon = num(r[ix["위도좌표"]]), num(r[ix["경도좌표"]])
        unit = sorted(r_["codes"]) if r_ else None
        c, prec, why = place_point_or_county(lon, lat, unit)
        if c is None:
            st_missing.append({"name": nm, "reason": why})
            continue
        if prec == "county":
            st_fallback.append({"name": nm, "reason": why})
        lines_ = r[ix["관련노선"]]
        hsr = "(고속)" in lines_
        m = re.search(r"여객열차\s*(\d+)\s*회", r[ix["열차정차횟수"]])
        stops = int(m.group(1)) if m else None
        grade = r[ix["역등급"]]
        codes = unit or [W.code_of[c]]
        I_items.append(base_item("station", nm, c, prec, codes, value=stops, unit="회 정차 (여객열차)" if stops is not None else None,
                                 year=(r[ix["입력일"]] or "")[:4] or None, source=F_RAIL[0], hsr=hsr, grade=grade,
                                 detail=[f"노선: {lines_}", f"정차: {r[ix['열차정차횟수']]}", f"역등급 {grade} · 취급 {work}", f"주소: {addr}"]
                                 + ([why] if why else [])))
    I_kinds["station"] = {
        "name": "철도역", "group": "infrastructure", "count": n_pass, "placed": n_pass - len(st_missing),
        "hsr": sum(1 for i in I_items if i["kind"] == "station" and i["hsr"]),
        "rule": ("국가철도공단 철도역 정보에서 취급업무에 '여객취급'이 있는 역(오기 '객취급' 포함). 관련노선에 '(고속)' 노선이 있으면 고속철도 정차역으로 "
                 "보고 전국 화면에서도 그리며, 나머지 역은 확대했을 때만 그린다. 위치는 원자료 좌표(point). 좌표가 0 이거나, 좌표가 든 칸과 "
                 "이웃 칸의 시군구가 주소의 시군구와 다르면 좌표를 믿지 않고 주소의 시군구(county)에 놓는다."),
        "source": [src(F_RAIL)], "year": "입력일 " + ", ".join(sorted({(r[ix['입력일']] or '')[:10] for r in rows})[:3]),
        "missing": st_missing, "excluded": dict(st_excl), "fallback": st_fallback, "precision_note": "point, 일부 county"}
    log(f"철도역: 원자료 {len(rows)}, 여객 {n_pass}, 고속 {I_kinds['station']['hsr']}, 제외 {dict(st_excl)}, 주소로 놓음 {len(st_fallback)} {[s['name'] for s in st_fallback]}")

    # ---------- 공항 ----------
    hdr, rows = read_csv(F_AIR[1])
    ix = {h: i for i, h in enumerate(hdr)}
    yr = max(int(r[ix["연도"]]) for r in rows)
    ap = collections.OrderedDict()
    pcols = ["여객성인도착", "여객성인출발", "여객유아도착", "여객유아출발"]
    for r in rows:
        if int(r[ix["연도"]]) != yr:
            continue
        nm = r[ix["공항"]].split("_")[0].strip()
        a = ap.setdefault(nm, {"total": 0, "domestic": 0, "international": 0, "na": 0})
        for col in pcols:
            v = num(r[ix[col]])
            if v is None:
                a["na"] += 1
                continue
            a["total"] += int(v)
            a["domestic" if r[ix["노선"]] == "국내선" else "international"] += int(v)
    airports = []
    for nm, a in ap.items():
        airports.append({"id": f"air-{nm}", "kind": "airport", "name": f"{nm}공항", "value": a["total"], "unit": "명", "year": yr,
                         "domestic": a["domestic"], "international": a["international"], "placed": False,
                         "reason": "원자료에 좌표도 소재 시군구도 없음 (공항 이름은 주소가 아님: 김포공항은 서울 강서구, 김해공항은 부산 강서구)"})
    I_unplaced += airports
    I_kinds["airport"] = {
        "name": "공항", "group": "infrastructure", "count": len(airports), "placed": 0,
        "rule": (f"한국공항공사 공항별 여객실적의 공항 전부. 값은 최신 연도({yr}) 여객 수(성인·유아 도착+출발, 국내선+국제선, 정기+부정기). "
                 "파일에 좌표도 소재 시군구도 없고, 이번 단계에서 쓸 수 있는 공식 원자료에도 공항 좌표가 없어 지도에 놓지 않았다(명세: 손 입력 금지). "
                 "인천공항은 이 파일에 있다."),
        "source": [src(F_AIR)], "year": str(yr), "missing": [{"name": a["name"], "reason": a["reason"]} for a in airports],
        "precision_note": "없음 (위치 없음)"}
    log(f"공항 {len(airports)}곳 ({yr}), 인천 포함 {'인천공항' in [a['name'] for a in airports]}")

    # ---------- 도로·철도 선 (Natural Earth 초안) ----------
    hexes = [Polygon([(W.centers[i][0] + W.G.R * math.cos(math.radians(60 * k - 30)), W.centers[i][1] + W.G.R * math.sin(math.radians(60 * k - 30)))
                      for k in range(6)]) for i in range(W.N) if W.land[i]]
    fhex = [Polygon([(W.centers[i][0] + W.G.R * 1.001 * math.cos(math.radians(60 * k - 30)), W.centers[i][1] + W.G.R * 1.001 * math.sin(math.radians(60 * k - 30)))
                     for k in range(6)]) for i in range(W.N) if W.foreign[i] == 1]
    kr_poly = shapely.union_all(hexes).buffer(W.G.R * 0.5)
    fg_poly = shapely.union_all(fhex)
    clip = kr_poly.difference(fg_poly)

    def read_ne(rel):
        z = zipfile.ZipFile(raw(*rel.split("/")))
        b = [n for n in z.namelist() if n.endswith(".shp")][0][:-4]
        r = shapefile.Reader(shp=io.BytesIO(z.read(b + ".shp")), dbf=io.BytesIO(z.read(b + ".dbf")),
                             shx=io.BytesIO(z.read(b + ".shx")), encoding="utf-8")
        flds = [f[0] for f in r.fields[1:]]
        for sr in r.iterShapeRecords():
            yield shape(sr.shape.__geo_interface__), dict(zip(flds, sr.record))

    from shapely.geometry import box as _box
    llbox = _box(124.0, 32.8, 132.2, 39.2)

    def to_lines(rel, tier_of):
        out = []
        n_feat = 0
        for g, rec in read_ne(rel):
            if not g.intersects(llbox):
                continue
            n_feat += 1
            gm = shapely.transform(g, lambda xy: np.column_stack(TO5179.transform(xy[:, 0], xy[:, 1])))
            gm = gm.simplify(SIMPLIFY_M)
            gu = shapely.transform(gm, lambda xy: np.column_stack(W.m2u(xy[:, 0], xy[:, 1])))
            cut = gu.intersection(clip)
            if cut.is_empty:
                continue
            for ln in getattr(cut, "geoms", [cut]):
                if ln.geom_type != "LineString" or ln.length < 1:
                    continue
                pts_ = [round(v, 1) for xy in ln.coords for v in xy]
                out.append({"tier": tier_of(rec), "pts": pts_})
        return out, n_feat

    roads, n_rf = to_lines(F_ROADS[1], lambda r: 1 if (r.get("expressway") == 1 or r.get("type") == "Major Highway") else 2)
    rails, n_lf = to_lines(F_RAILS[1], lambda r: 1)
    n_road_pts = sum(len(x["pts"]) // 2 for x in roads)
    n_rail_pts = sum(len(x["pts"]) // 2 for x in rails)
    lines_note = "초안: Natural Earth 1:10m, 공식 도로망으로 교체 예정"
    I_kinds["roads"] = {
        "name": "도로 선", "group": "lines", "count": len(roads),
        "rule": (f"Natural Earth 1:10m 도로 가운데 지도 범위에 드는 {n_rf}개 선을 EPSG:5179 로 옮겨 300 m 허용 오차로 단순화한 뒤 화면 좌표로 저장. "
                 "고속도로 급(expressway=1 또는 type 'Major Highway')과 그 밖의 주요 도로 2단계. 대한민국 육지 칸(반 칸 여백) 안만 남기고 "
                 f"북한 땅 칸은 잘라 낸다. {lines_note}."),
        "source": [src(F_ROADS)], "year": "Natural Earth 5.x", "missing": [], "draft": True}
    I_kinds["rails"] = {
        "name": "철도 선", "group": "lines", "count": len(rails),
        "rule": (f"Natural Earth 1:10m 철도 가운데 지도 범위에 드는 {n_lf}개 선. 처리 방식은 도로와 같다(300 m 단순화, 북한 구간 제외). "
                 "1:10m 자료라 고속선·일반선 구분이 없다. 초안: Natural Earth 1:10m, 공식 철도망으로 교체 예정."),
        "source": [src(F_RAILS)], "year": "Natural Earth 5.x", "missing": [], "draft": True}
    log(f"도로 선 {len(roads)}개 ({n_road_pts}점, 고속 {sum(1 for x in roads if x['tier'] == 1)}), 철도 선 {len(rails)}개 ({n_rail_pts}점)")

    # =====================================================================
    # 저장
    # =====================================================================
    def finish(items, prefix):
        for k, it in enumerate(items):
            it["id"] = f"{prefix}-{k}"
            if it.get("value") is not None and isinstance(it["value"], float) and it["value"].is_integer():
                it["value"] = int(it["value"])
        return items

    def prec_count(items):
        return dict(collections.Counter(i["precision"] for i in items))

    vintage = "2026-11"
    wonders = {"version": VERSION, "layer": "wonders", "name": "불가사의", "vintage": vintage, "kinds": W_kinds,
               "items": finish(W_items, "w"), "parks": parks, "world_heritage": whs,
               "heritage": {"raw": dict(her_raw), "valid": n_valid, "excluded": {f"{k}·{r}": v for (k, r), v in her_excl.items()},
                            "cluster_threshold": thr, "cluster_distribution": {str(k): v for k, v in sorted(dist.items())}},
               "precision_counts": prec_count(W_items)}
    resources = {"version": VERSION, "layer": "resources", "name": "자원", "vintage": vintage, "kinds": R_kinds,
                 "items": finish(R_items, "r"), "unplaced": R_unplaced, "general_complexes": {"by_city": gic_city, "by_sido": gic_sido},
                 "minerals": minerals, "precision_counts": prec_count(R_items)}
    infra = {"version": VERSION, "layer": "infrastructure", "name": "기반시설", "vintage": vintage, "kinds": I_kinds,
             "items": finish(I_items, "i"), "unplaced": I_unplaced, "lines": {"roads": roads, "rails": rails, "note": lines_note},
             "precision_counts": prec_count(I_items)}
    for nm, obj in (("wonders", wonders), ("resources", resources), ("infrastructure", infra)):
        size = save_json(site(f"{nm}.json"), obj)
        log(f"{nm}.json {size / 1e3:.0f} KB, 아이콘 {len(obj['items'])}개, 정밀도 {obj['precision_counts']}")

    # ---------- 유산 렌즈 ----------
    nz = [v for v in lens_vals if v]
    lens = {"id": "heritage", "group": "land", "name": "국가유산", "emoji": "🏯", "unit": "건", "format": "int", "scale": "bins",
            "breaks": [1, 2, 4, 8, 16],
            "bin_labels": ["0건", "1건", "2–3건", "4–7건", "8–15건", "16건 이상"],
            "ramp": ["#efece6", "#f0cf7e", "#e2a347", "#c8742f", "#9a4421", "#5c2213"],
            "higher_is": "neutral", "basis": "소재지 (지정 유산 좌표)", "vintage": "목록 수집 2026-11",
            "source": "국가유산청 국가유산 목록 (국보·사적·명승·천연기념물, 좌표 포함)",
            "description": (f"칸별 국가유산 건수: 국보 + 사적 + 명승 + 천연기념물 가운데 지정 해제되지 않고 좌표가 있는 {n_valid:,}건을 좌표가 든 칸에 센다 "
                            "(좌표가 바다 칸이면 두 칸 안의 가장 가까운 육지 칸). 0건인 칸은 0이다(자료 없음이 아님). 국보에는 박물관 소장 유물이 많아 "
                            f"박물관이 있는 칸이 높다. 좌표가 없거나 범위 밖이라 뺀 것: {sum(her_excl.values()):,}건."),
            "domain": [0, 16], "values": lens_vals, "coverage": 1.0, "total": int(sum(nz))}
    lenses["lenses"] = [l_ for l_ in lenses["lenses"] if l_["id"] != "heritage"] + [lens]
    if not any(g["id"] == "land" for g in lenses["groups"]):
        lenses["groups"].append({"id": "land", "name": "땅"})
    save_json(site("lenses.json"), lenses)
    log(f"유산 렌즈: 칸별 건수 합 {sum(nz):,} = 좌표 유효 {n_valid:,}, 1건 이상 칸 {len(nz)}")

    save_json(build("layers_audit.json"), {
        "heritage_excluded": {f"{k}·{r}": v for (k, r), v in her_excl.items()},
        "stations_fallback": st_fallback, "stations_missing": st_missing,
        "wh": [{"name": e["name"], "located_by": e["located_by"], "components": e["components"]} for e in whs],
        "nuclear": [{"site": s["site"], "mw": s["value"], "units": s["units_operating"], "cap2": s["cap2_in_file"]} for s in nuc_sites],
    }, compact=False)


if __name__ == "__main__":
    sys.exit(main())

"""5b 2부 — 층과 렌즈 (명세 docs/SPEC_PHASE5B.md §4–§6).

build_layers.py(5a)가 만든 site/data/{wonders,resources,infrastructure}.json 과 lenses.json 에 5b 층을 붙이고,
site/data/frontier.json 을 새로 만든다.

입력 (읽기만, 신뢰할 수 없는 입력으로 다룬다 — 필드 값은 데이터로만 쓰고 형식이 다르면 빌드 오류):
  data/build/layers/{airport_locations,airport_traffic,ports,port_traffic,generators,park_visitors,
                     geographical_indications,rice,livestock,border_areas,key_industries,research_institutes,
                     foreign_residents,pm25_stations,health,disaster_damage,academies}.csv, roads.geojson
  data/build/terrain_cache.npz (칸별 피복 비율·출처 — 기후에너지환경부 세분류 토지피복지도 도엽 통계, 도엽이 닿지 않는 칸은 ESA)
중간 결과 캐시: data/build/roads_5b.npz (도로 선을 이어 붙이고 겹친 차로를 뺀 결과, roads.geojson 크기·시각이 같으면 다시 쓴다)

위치 정밀도는 5a 와 같다: point(원자료 좌표) / county(주소의 시군구, 인구 가중 중심 칸).
무역항은 county 이되 '해안에 닿은 칸' 가운데 고른다. 시군구가 없는 위치 문자열(예: '울산광역시')은 sido.
"""
import collections
import csv
import math
import os
import re
import sys

import numpy as np
import shapely
from shapely.geometry import Polygon

from build_layers import TO5179, World
from lib import econ as E
from lib import popstats
from lib import profile as PRF
from lib import cover_sheets as CS
from lib import terrain as TR
from lib.address import AddressResolver, nospace
from lib.common import build, load_json, raw, rnd, save_json, site
from lib.terrain import layer_path

VERSION = "phase5b-2"
CONIFER_MIN_FOREST = 0.10   # 5c 침엽수림 비중 렌즈: 숲이 칸의 이 비율 미만이면 자료 없음 (명세 5c §1.4)


def log(*a):
    print("[layers5b]", *a, flush=True)


def read_rows(name):
    with open(layer_path(name), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def fnum(s):
    s = (s or "").replace(",", "").strip()
    if s == "":
        return None
    return float(s)


def as_int(v):
    return None if v is None else int(round(v))


class LayerEcon(E.Econ):
    """경제 정리표와 같은 열을 쓰는 data/build/layers 의 시군구 표를 같은 규칙(lib/econ.py)으로 단위에 붙인다."""

    def table(self, name):
        if name in self.tables:
            return self.tables[name]
        rows = read_rows(name + ".csv")
        need = {"sgg_code_raw", "sgg_name_raw", "sgg_code_now", "sido_now", "year", "indicator", "industry", "value"}
        if rows and not need <= set(rows[0]):
            raise ValueError(f"{name}.csv 열이 다름: {sorted(need - set(rows[0]))}")
        out = []
        for r in rows:
            res = self.resolve(r)
            if res is None:
                self.ignored[(name, r["sido_now"], r["sgg_name_raw"])] += 1
                continue
            kind, key, codes = res
            out.append({"kind": kind, "key": key, "codes": codes, "year": r["year"], "raw": (r.get("sgg_code_raw") or "").strip(),
                        "indicator": r["indicator"], "industry": r["industry"], "value": E.num(r["value"]),
                        "raw_empty": (r["value"] or "").strip() == "", "unit": r.get("unit", ""), "basis": r.get("basis", ""),
                        "source": r.get("source_id", "")})
        self.tables[name] = out
        return out


ICN_STATIONS = ("인천공항1터미널", "인천공항2터미널")
ICN_POSITION_NOTE = "제1·2여객터미널 역 위치의 중점 — 공항 기준점이 아님"


def _read_l5_csv(key):
    """data/raw/layers5 의 공공데이터포털 CSV (CP949, 수집 기록의 sha256 과 대조, 신뢰할 수 없는 입력 — 값으로만 읽는다)."""
    from lib import cover_sheets as CS_
    b, e = CS_.read_checked(("files", key + ".csv"), key)
    rows = list(csv.reader(b.decode("cp949").splitlines()))
    return rows[0], rows[1:], e


def incheon_from_rail():
    """인천공항 위치: 공항철도 역위치(15041331)의 두 터미널 역 좌표 중점, 주소: 공항철도 주소데이터(15041094)의 1터미널역 도로명주소."""
    from pyproj import Transformer
    h, rows, e1 = _read_l5_csv("p1-15041331")
    if h != ["철도운영기관명", "선명", "역명", "경도", "위도"]:
        raise ValueError(f"공항철도 역위치 열이 다름: {h}")
    st = {}
    for r in rows:
        if r[0] == "공항철도주식회사" and r[1] == "공항철도" and r[2] in ICN_STATIONS:
            lon, lat = float(r[3]), float(r[4])
            if not (126.3 < lon < 126.6 and 37.4 < lat < 37.55):
                raise ValueError(f"공항철도 역 좌표가 영종도 밖: {r}")
            if r[2] in st:
                raise ValueError(f"공항철도 역이 둘: {r[2]}")
            st[r[2]] = (lon, lat)
    if set(st) != set(ICN_STATIONS):
        raise ValueError(f"공항철도 역위치에 두 터미널 역이 없음: {sorted(st)}")
    h2, rows2, e2 = _read_l5_csv("p1-15041094")
    if h2 != ["철도운영기관명", "선명", "역명", "지번주소", "도로명주소"]:
        raise ValueError(f"공항철도 주소데이터 열이 다름: {h2}")
    addr = {r[2]: r[4].strip() for r in rows2 if r[0] == "공항철도주식회사" and r[1] == "공항철도" and r[2] in ICN_STATIONS}
    if set(addr) != set(ICN_STATIONS):
        raise ValueError(f"공항철도 주소데이터에 두 터미널 역이 없음: {sorted(addr)}")
    fw = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    bw = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    p = [fw.transform(*st[k]) for k in ICN_STATIONS]
    mx, my = (p[0][0] + p[1][0]) / 2, (p[0][1] + p[1][1]) / 2
    lon, lat = bw.transform(mx, my)
    gap = math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]) / 1000
    a1 = re.sub(r"\s*\(.*?\)\s*", " ", addr[ICN_STATIONS[0]]).split(" 인천공항")[0].strip()

    def srcrec(key, e, title):
        return {"key": key, "title": title, "publisher": "국가철도공단", "retrieved": (e.get("retrieved") or "")[:10], "file": "layers5/" + e["file"],
                "license": "이용허락범위 제한 없음"}
    return {"row": {"name": "인천", "kind": "공항", "value": "", "unit": "", "year": "2026", "lon": f"{lon:.7f}", "lat": f"{lat:.7f}",
                    "address": a1, "source_id": "data-15041331"},
            "source": "data-15041331", "position_note": ICN_POSITION_NOTE, "gap_km": gap,
            "stations": [{"name": k + "역", "lon": st[k][0], "lat": st[k][1], "address": addr[k]} for k in ICN_STATIONS],
            "detail": " · ".join(f"{k}역 {st[k][0]:.5f}, {st[k][1]:.5f}" for k in ICN_STATIONS) + " — 국가철도공단 공항철도 역위치",
            "src_loc": srcrec("data-15041331", e1, "국가철도공단_공항철도_역위치"), "src_addr": srcrec("data-15041094", e2, "국가철도공단_공항철도_주소데이터")}


def main():
    W = World()
    w = W.w
    cities = load_json(site("cities.json"))
    states = load_json(site("states.json"))
    lenses = load_json(site("lenses.json"))
    wonders = load_json(site("wonders.json"))
    resources = load_json(site("resources.json"))
    infra = load_json(site("infrastructure.json"))
    if any(o.get("version") in ("phase5d", "phase5e") for o in (wonders, resources, infra)):
        # 5d(build_layers3.py)·5e(build_layers5e.py)가 이미 고친 층 위에 5b 를 다시 얹으면 댐·세계유산 등이 어긋난다
        raise RuntimeError("층 JSON 이 5d 결과다 — build_layers.py 부터 다시 돌린다 (build_all.py 는 그 순서로 돈다)")
    lman = load_json(raw("layers", "manifest.json"))
    dongs = load_json(build("dongs.json"))
    resolver0 = AddressResolver(w, cities)
    _memo = {}

    class _R:
        sido_of = staticmethod(resolver0.sido_of)

        @staticmethod
        def resolve(text, sido_hint=None):
            k = (text, sido_hint)
            if k not in _memo:
                _memo[k] = resolver0.resolve(text, sido_hint=sido_hint)
            return _memo[k]

    resolver = _R
    ec = LayerEcon(w, cities)
    sido_name = {s["code"]: s["name"] for s in w["states"]}
    sido_short = {s["code"]: s["short"] for s in w["states"]}
    city_of_code = {s: c["id"] for c in cities for s in c["sgg"]}
    owner = W.owner
    water = np.array(w["water"])
    foreign = W.foreign
    G = W.G

    def src(key, file=None):
        e = lman.get(key, {})
        return {"key": key, "title": e.get("title"), "publisher": e.get("publisher"), "retrieved": (e.get("retrieved") or "")[:10],
                "file": "layers/" + (file or str(e.get("file"))), "license": e.get("license") or e.get("license_note")}

    # ---------- 시군구 단위 인구 가중 중심 칸 (5a 와 같은 규칙) ----------
    _, _, f_emd, _ = popstats.latest_files()
    rec, _ = popstats.dong_population(f_emd, dongs)
    dpop = {d["code"]: rec[d["code"]]["total"] for d in dongs}
    center_cache = {}

    def unit_xy(codes):
        items = [(d["rx"], d["ry"], dpop.get(d["code"], 0)) for d in dongs if d["sgg"] in codes]
        tw = sum(i[2] for i in items)
        own = np.nonzero(np.isin(W.code_of, list(codes)) & W.land)[0]
        if tw > 0:
            return sum(i[0] * i[2] for i in items) / tw, sum(i[1] * i[2] for i in items) / tw, own
        return W.centers[own][:, 0].mean(), W.centers[own][:, 1].mean(), own

    def unit_center(codes, among=None):
        """codes 의 인구 가중 중심에 가장 가까운 자기 칸. among 이 있으면 그 칸 집합 안에서만."""
        key = (frozenset(codes), None if among is None else "coast")
        if key in center_cache:
            return center_cache[key]
        px, py, own = unit_xy(set(codes))
        cand = own if among is None else np.array([c for c in own if among(c)], dtype=int)
        if not len(cand):
            center_cache[key] = None
            return None
        k = int(cand[np.argmin(((W.centers[cand] - [px, py]) ** 2).sum(1))])
        center_cache[key] = k
        return k

    def is_sea(j):
        return owner[j] < 0 and foreign[j] != 1 and water[j] in (1, 2, 4)

    def coastal(i):
        return bool(W.land[i]) and any(is_sea(j) for j in G.neighbors(i))

    def cnames(codes):
        return " · ".join(W.cname[c] for c in sorted(codes))

    def place_of(codes):
        codes = sorted(codes)
        sd = W.sido_of_code[codes[0]]
        # 일반구를 둔 시 전체면 시 이름으로
        cid = city_of_code.get(codes[0])
        cty = next((c for c in cities if c["id"] == cid), None)
        if cty and set(cty["sgg"]) == set(codes) and len(codes) > 1:
            return f"{sido_name[sd]} {cty['name']}"
        return f"{sido_name[sd]} {cnames(codes)}"

    def item(kind, name, cell, precision, codes, **kw):
        codes = sorted(codes)
        sd = W.sido_of_code[codes[0]]
        same_city = all(city_of_code.get(c) == city_of_code.get(codes[0]) for c in codes)
        it = {"id": None, "kind": kind, "name": name, "cell": int(cell), "precision": precision, "sgg": codes, "sido": sd,
              "city": city_of_code.get(codes[0]) if same_city else None, "place": place_of(codes)}
        it.update(kw)
        return it

    def rank_items(items):
        """종류 안에서 값이 큰 순서 (값이 없으면 맨 뒤). 화면이 전국 화면에서 종류별 상위만 그리는 데 쓴다."""
        order = sorted(range(len(items)), key=lambda k: -(items[k].get("value") if items[k].get("value") is not None else -1))
        for r, k in enumerate(order):
            items[k]["rank"] = r + 1
        return items

    def finish(items, prefix):
        for k, it in enumerate(items):
            it["id"] = f"{prefix}-{k}"
            v = it.get("value")
            if isinstance(v, float) and v.is_integer():
                it["value"] = int(v)
        return items

    city_by_id = {c["id"]: c for c in cities}

    def by_city_sum(units):
        """{코드 집합: {키: 값}} -> 도시별·시도별 합 (도시 영토 안에 든 단위만)"""
        bc, bs = {}, {}
        for codes, vals in units.items():
            cids = {city_of_code[c] for c in codes}
            sds = {W.sido_of_code[c] for c in codes}
            if len(cids) == 1:
                d = bc.setdefault(next(iter(cids)), collections.Counter())
                for k, v in vals.items():
                    d[k] += v
            if len(sds) == 1:
                d = bs.setdefault(next(iter(sds)), collections.Counter())
                for k, v in vals.items():
                    d[k] += v
        rr = lambda d: {k: round(v, 3) for k, v in sorted(d.items(), key=lambda kv: -kv[1])}
        return {str(k): rr(v) for k, v in bc.items()}, {k: rr(v) for k, v in bs.items()}

    # =====================================================================
    # 공항 (point)
    # =====================================================================
    ap_loc = [r for r in read_rows("airport_locations.csv") if r["source_id"] != "incheon-aip"]   # 항공정보간행물(AIP) 좌표는 두 판 모두 쓰지 않는다
    ap_tr = read_rows("airport_traffic.csv")
    tr = collections.defaultdict(dict)
    for r in ap_tr:
        nm = re.sub(r"\(.*?\)", "", r["name"]).strip()
        tr[nm][r["kind"]] = (fnum(r["value"]), r["unit"], r["year"])
    nat_air = tr.pop("전체 합계", {})
    # 인천공항: 국가철도공단 공항철도 역위치(15041331)의 인천공항1터미널·2터미널 역 좌표의 중점 (EPSG:5179 에서 잰 중점), 주소는 같은 공단의 주소데이터(15041094)
    icn = incheon_from_rail()
    ap_loc.append(icn["row"])
    A_items, ap_missing = [], []
    for r in ap_loc:
        nm = r["name"].strip()
        lon, lat = fnum(r["lon"]), fnum(r["lat"])
        ux, uy = W.lonlat2u(lon, lat)
        c, why = W.snap(ux, uy)
        if c is None:
            ap_missing.append({"name": nm + "공항", "reason": f"좌표 칸이 {why}"})
            continue
        res = resolver.resolve(r["address"])
        notes = []
        if res is None:
            codes = [W.code_of[c]]
            notes.append("주소가 시군구 이름표로 읽히지 않아(" + ("영문 주소" if re.search(r"[A-Za-z]", r["address"]) else "주소 표기") + ") 좌표가 든 칸의 시군구로 적음")
        elif len(res["codes"]) > 1 and W.code_of[c] in res["codes"] and not res.get("city_level"):
            codes = [W.code_of[c]]
            notes.append(f"주소의 옛 구가 개편으로 {cnames(res['codes'])}로 나뉘어 좌표가 든 칸의 시군구({W.cname[W.code_of[c]]})로 적음")
        else:
            codes = sorted(res["codes"])
            if not (W.near_codes(c) & set(codes)):
                notes.append(f"좌표 칸의 시군구({W.cname[W.code_of[c]]})가 주소의 시군구와 다름")
        t = tr.get(nm, {})
        pax, cargo = t.get("여객"), t.get("화물")
        dist = math.hypot(ux - W.centers[c][0], uy - W.centers[c][1])
        is_icn = r["source_id"] == icn["source"]
        det = [f"주소: {r['address']}", (f"좌표 {lon:.5f}, {lat:.5f} — {icn['position_note']} ({icn['detail']})" if is_icn else f"좌표 {lon:.5f}, {lat:.5f} (한국공항공사 공항 위치정보)")]
        det.append(f"2025년 여객 {int(pax[0]):,}명 · 화물 {int(cargo[0]):,}톤 (항공정보포털 공항별 통계)" if pax and cargo
                   else "2025년 실적 행이 원표에 없음 → 값 없음")
        extra = {"position_note": icn["position_note"], "position_from": icn["stations"]} if is_icn else {}
        A_items.append(item("airport", f"{nm}공항", c, "point", codes, value=as_int(pax[0]) if pax else None, unit="명 (2025 여객)" if pax else None,
                            year="2025", cargo_t=as_int(cargo[0]) if cargo else None, lon=lon, lat=lat, dist_u=round(dist, 2),
                            source=r["source_id"], detail=det + notes, **extra))
    rank_items(A_items)
    no_tr = [i["name"] for i in A_items if i["value"] is None]
    log(f"공항 {len(A_items)}곳 (원자료 {len(ap_loc)}), 실적 없음 {no_tr}, 전국 합계 행 {nat_air}; 인천 {icn['row']['lon']}, {icn['row']['lat']} ({icn['detail']})")
    air_kind = {
        "name": "공항", "group": "ports", "count": len(ap_loc), "placed": len(A_items),
        "rule": (f"한국공항공사 공항 위치정보 {len(ap_loc) - 1}곳은 원자료 좌표가 든 칸(point)에 놓는다. 인천공항은 한국공항공사 관할이 아니라 그 파일에 없어, "
                 f"국가철도공단 공항철도 역위치의 인천공항1터미널역과 인천공항2터미널역 좌표의 중점(EPSG:5179 에서 잰 중점, 두 역 사이 {icn['gap_km']:.1f} km)에 놓는다 — "
                 f"{icn['position_note']}. 모두 {len(ap_loc)}곳. 항공정보간행물(AIP)의 공항 기준점 좌표는 허락 없는 복제·배포를 막는 조건이 있어 두 판 모두 쓰지 않는다. "
                 "값은 항공정보포털 공항별 통계의 2025년 여객(명)과 화물(톤). 이름은 통계표의 '김포(GMP)'에서 괄호를 뗀 이름으로 맞춘다. "
                 f"실적 행이 없는 공항({', '.join(no_tr) or '없음'})은 값을 비운다(0 이 아님). 소재 시군구는 주소에서 읽는다(인천공항은 공항철도 주소데이터의 "
                 "인천공항1터미널역 도로명주소; 옛 인천 중구가 개편으로 나뉘어 좌표가 든 칸의 시군구로 적는다). 5a 의 '위치 없음' 공항 목록(한국공항공사 여객실적 파일)을 대신한다."),
        "source": [src("data-15002851"), icn["src_loc"], icn["src_addr"], src("airportal-2025")], "year": "2025 (실적), 2026 (위치)",
        "missing": ap_missing, "precision_note": "point",
        "national": {"passengers": as_int(nat_air.get("여객", (None,))[0]), "cargo_t": as_int(nat_air.get("화물", (None,))[0])}}

    # 현재 시·군 이름(구 제외). 일반구를 둔 시는 시 이름으로 한 단위.
    sigun = collections.defaultdict(list)
    for c in w["counties"]:
        if c["name"].endswith(("시", "군")) and " " not in c["name"]:
            sigun[c["name"]].append(frozenset([c["code"]]))
    for c in cities:
        if len(c["sgg"]) > 1 and c["name"].endswith("시"):
            sigun[c["name"]].append(frozenset(c["sgg"]))
    # =====================================================================
    # 무역항 (county, 해안에 닿은 칸)
    # =====================================================================
    ports = read_rows("ports.csv")
    ptr = read_rows("port_traffic.csv")

    def pkey(s):
        return re.sub(r"[.\s·]", "", s)

    # 통계표 이름은 '장항'·'포항'처럼 끝 글자 '항'이 이름의 일부일 수 있어, 항만 이름에서만 끝의 '항'을 떼고 통계표 이름은 그대로·'항'을 뗀 것 둘 다로 찾는다
    cargo, teu, cargo_raw = {}, {}, {}
    for r in ptr:
        k = pkey(r["name"])
        d = cargo if r["kind"] == "화물 처리량" else teu if r["kind"] == "컨테이너 처리량" else None
        if d is None:
            raise ValueError(f"port_traffic.csv 종류를 모름: {r['kind']}")
        if r["kind"] == "화물 처리량":
            cargo_raw[k] = (fnum(r["value"]), r["source_id"])
        for kk in {k, k.removesuffix("항")}:
            d.setdefault(kk, (fnum(r["value"]), r["source_id"], k))
    not_ports = {k: v for k, v in cargo_raw.items() if k in ("합계", "기타")}
    nat_teu = teu.pop("전국", None)
    P_items, port_missing, port_flags = [], [], []
    used_cargo = set()
    for r in ports:
        nm = r["name"].strip()
        loc = r["address"].strip()
        toks = [t.strip() for t in re.split(r",|\s및\s", loc) if t.strip()]
        first, spans, unread, last_sd = None, set(), [], None
        for t in toks:
            res = resolver.resolve(t)
            if res is None and last_sd:
                res = resolver.resolve(sido_name[last_sd] + " " + t)
            if res is None:
                sd, rest = resolver.sido_of(t)
                if sd is not None and re.fullmatch(r"(일원|전역)?", rest):
                    res = {"codes": frozenset(c["code"] for c in w["counties"] if c["sido"] == sd), "sido": sd, "sido_level": True}
            if res is None:
                hit = [sigun[x][0] for x in (nospace(y) for y in t.split()) if x in sigun and len(sigun[x]) == 1]
                if hit:
                    res = {"codes": hit[0], "sido": W.sido_of_code[sorted(hit[0])[0]]}
            if res is None:
                unread.append(t)
                continue
            last_sd = res["sido"]
            if first is None:
                first = res
            spans |= set(res["codes"])
        if first is None:
            port_missing.append({"name": nm, "reason": f"위치 문자열 '{loc}' 에서 시군구를 읽지 못함"})
            continue
        codes = sorted(first["codes"])
        precision = "sido" if first.get("sido_level") else "county"
        c = unit_center(codes, among=coastal)
        on_coast = c is not None
        if c is None:
            c = unit_center(codes)
            port_flags.append({"name": nm, "reason": f"{cnames(codes)} 에 바다와 맞닿은 육지 칸이 없어(하천항) 시군구 중심 칸에 놓음"})
        k = pkey(nm).removesuffix("항")
        cv = cargo.get(k)
        if cv:
            used_cargo.add(cv[2])
        tv = teu.get(k)
        det = [f"위치 문자열(원표): {loc}"]
        if precision == "sido":
            det.append("위치 문자열에 시군구가 없어 시도 단위로만 알 수 있음: 그 시도의 해안 칸 가운데 시도 인구 중심에 가장 가까운 칸에 놓음 (sido)")
        if len(spans) > len(codes):
            det.append("걸친 시군구: " + cnames(spans))
        if unread:
            det.append("읽지 못한 표기: " + ", ".join(unread))
        det.append(f"2025년 화물 처리량 {int(cv[0]):,} 톤(R/T) (국가물류통합정보센터 PORT-MIS 1~12월 누계)" if cv else "화물 처리량 행이 원표에 없음")
        teu_note = None
        if tv:
            teu_note = "발표 반올림값" if tv[1] == "mof-ports-2025" else "원자료 합계"
            det.append(f"컨테이너 {int(tv[0]):,} TEU ({teu_note}: {'해양수산부 2025년 물동량 발표의 천·만 단위 공표값' if teu_note == '발표 반올림값' else '부산항만공사 외내항 컨테이너 통합집계 원자료 합'})")
        P_items.append(item("trade_port", nm, c, precision, codes, value=as_int(cv[0]) if cv else None, unit="톤 (2025 화물)" if cv else None,
                            year="2025", teu=as_int(tv[0]) if tv else None, teu_note=teu_note, spans=sorted(spans), coastal=on_coast,
                            location=loc, source="data-15088273", detail=det))
    rank_items(P_items)
    unmatched_cargo = sorted(set(cargo_raw) - used_cargo - set(not_ports))
    log(f"무역항 {len(P_items)}곳 (원자료 {len(ports)}), 해안 칸 아님 {[f['name'] for f in port_flags]}, 화물 행 대응 안 됨 {unmatched_cargo}, "
        f"정밀도 {collections.Counter(i['precision'] for i in P_items)}")
    port_kind = {
        "name": "무역항", "group": "ports", "count": len(ports), "placed": len(P_items),
        "rule": ("해양수산부 항만정보의 무역항 31곳. 위치 문자열을 쉼표와 '및'으로 나눠 첫 시군구에 놓고(앞 조각의 시도를 뒤 조각에 이어 씀), 나머지는 '걸친 시군구'로 적는다. "
                 "칸은 그 시군구의 육지 칸 가운데 바다(먼바다·연안·갯벌 칸)와 맞닿은 칸 중 시군구 인구 가중 중심에 가장 가까운 칸이다(county). "
                 "위치 문자열이 '울산광역시'처럼 시도뿐이면 시도의 해안 칸 가운데 시도 인구 중심에 가장 가까운 칸(sido). 바다와 맞닿은 칸이 없는 하천항(서울항)은 "
                 "시군구 중심 칸에 두고 표시한다. 값은 국가물류통합정보센터 PORT-MIS 2025년 1~12월 화물 처리량(톤, R/T); 이름은 '항'·'.'을 떼고 맞춘다. "
                 "원표의 '합계'·'기타' 행은 항만이 아니라 쓰지 않는다. 컨테이너(TEU)는 있는 항만만: 부산항은 부산항만공사 원자료 합계, 인천항·광양항은 "
                 "해양수산부 발표의 반올림 공표값('발표 반올림값')."),
        "source": [src("data-15088273"), src("nlic-ports-2025"), src("data-15147941"), src("mof-ports-2025")], "year": "2025",
        "missing": port_missing, "flags": port_flags, "precision_note": "county (해안 칸), 시도뿐인 표기는 sido",
        "national": {"cargo_t": as_int(not_ports.get("합계", (None,))[0]), "other_t": as_int(not_ports.get("기타", (None,))[0]),
                     "teu": as_int(nat_teu[0]) if nat_teu else None, "teu_note": "발표 반올림값" if nat_teu else None},
        "unmatched_cargo": unmatched_cargo}

    # =====================================================================
    # 발전소 (generators.csv)
    # =====================================================================
    FUEL = {"원자력": "nuclear", "석탄": "coal", "석탄가스화에너지": "coal_gasification", "가스": "gas", "석유": "oil",
            "수력에너지": "hydro", "양수": "pumped", "태양에너지": "solar", "풍력에너지": "wind", "연료전지": "fuel_cell",
            "바이오에너지": "bio", "해양에너지": "ocean", "": "unspecified"}
    FUEL_KO = {"nuclear": "원자력", "coal": "석탄", "coal_gasification": "석탄가스화", "gas": "가스(LNG)", "oil": "유류",
               "hydro": "수력", "pumped": "양수", "solar": "태양광", "wind": "풍력", "fuel_cell": "연료전지", "bio": "바이오",
               "ocean": "해양", "unspecified": "연료원 빈칸(폐기물·소각열·ESS 등)"}
    gens = read_rows("generators.csv")
    UNIT_RE = re.compile(r"(\s*(\(#[\d #]+\)|\d+-\d+CC|CC\d+|GT\s*#?\d*|ST\s*#?\d*|#\s*\d+\s*(GT|ST)?|(제\s*)?\d+\s*호기?|\d+(GT|ST)))+\s*$")

    def plant_name(n):
        n = re.sub(r"\s+", " ", n).strip()
        prev = None
        while prev != n:
            prev = n
            n = UNIT_RE.sub("", n).strip()
        return n

    fuel_tot = collections.Counter()
    unit_fuel = collections.defaultdict(collections.Counter)  # 코드 집합 -> 연료원 -> MW
    gen_fail = collections.Counter()
    gen_fail_mw = collections.Counter()
    gen_fail_fuel = collections.Counter()
    plants = collections.OrderedDict()
    n_gen = 0
    total_mw = 0.0
    for r in gens:
        kraw = r["kind"].strip()
        if kraw not in FUEL:
            raise ValueError(f"generators.csv 연료원을 모름: {kraw!r}")
        if r["unit"] != "MW":
            raise ValueError(f"generators.csv 단위가 MW 가 아님: {r['unit']}")
        mw = fnum(r["value"])
        if mw is None:
            raise ValueError(f"generators.csv 용량 빈칸: {r['name']}")
        fu = FUEL[kraw]
        n_gen += 1
        total_mw += mw
        fuel_tot[fu] += mw
        res = resolver.resolve(r["address"])
        if res is None:
            gen_fail[r["address"]] += 1
            gen_fail_mw[r["address"]] += mw
            gen_fail_fuel[fu] += mw
            codes = None
        else:
            codes = frozenset(res["codes"])
            unit_fuel[codes][fu] += mw
        if fu in ("coal", "coal_gasification", "gas", "oil", "hydro", "pumped", "nuclear"):
            grp = {"coal_gasification": "coal"}.get(fu, fu)
            key = (grp, plant_name(r["name"])) if fu != "nuclear" else (grp, codes)
            p = plants.setdefault(key, {"fuel": grp, "name": key[1], "mw": 0.0, "units": [], "by_unit": collections.Counter(), "failed_mw": 0.0,
                                        "subtypes": collections.Counter()})
            p["mw"] += mw
            p["units"].append(f"{r['name']} {mw:g} MW")
            p["subtypes"][FUEL_KO[fu]] += mw
            if codes is None:
                p["failed_mw"] += mw
            else:
                p["by_unit"][codes] += mw
    unit_sum = sum(sum(v.values()) for v in unit_fuel.values())
    fail_n, fail_mw = sum(gen_fail.values()), sum(gen_fail_mw.values())
    log(f"발전기 {n_gen:,}기 {total_mw:,.1f} MW, 연료원별 {dict((k, round(v, 1)) for k, v in fuel_tot.items())}, "
        f"시군구 대응 {unit_sum:,.1f} MW + 실패 {fail_n}기 {fail_mw:,.1f} MW {dict(gen_fail)}")

    THR = {"coal": 500.0, "gas": 500.0, "oil": 500.0, "hydro": 100.0, "pumped": 100.0}
    KIND_OF = {"coal": "power_coal", "gas": "power_gas", "oil": "power_oil", "hydro": "power_hydro", "pumped": "power_hydro"}
    PW_items = []
    nssc = [u for u in resources.get("nuclear_nssc", []) or [u for u in resources["unplaced"] if u["kind"] == "nuclear"]]
    nuc_cmp = []
    plants_below = collections.Counter()
    for key, p in plants.items():
        if not p["by_unit"]:
            continue
        codes = max(p["by_unit"], key=p["by_unit"].get)
        spans = set().union(*p["by_unit"].keys())
        if p["fuel"] == "nuclear":
            names = sorted({plant_name(u.rsplit(" ", 2)[0]) for u in p["units"]})
            match = [s for s in nssc if set(s["members"]) & set(names)]
            ref = match[0] if len(match) == 1 else None
            ok = ref is not None and abs(ref["value"] - p["mw"]) < 0.5
            nuc_cmp.append({"sgg": cnames(codes), "generators": names, "mw": p["mw"], "units": len(p["units"]),
                            "nssc_site": ref["site"] if ref else None, "nssc_mw": ref["value"] if ref else None,
                            "nssc_units": ref["units_operating"] if ref else None, "match": ok})
            det = [f"발전기 {len(p['units'])}기: " + ", ".join(p["units"]),
                   (f"원자력안전위원회 본부 '{ref['site']}' 가동 {ref['units_operating']}기 {ref['value']:,.0f} MW 와 " + ("일치" if ok else "다름"))
                   if ref else "원자력안전위원회 본부 목록과 이름으로 대응되지 않음"]
            PW_items.append(item("nuclear", "·".join(names) + " 원전", unit_center(codes), "county", codes, value=round(p["mw"], 1),
                                 unit="MW", year="2026-08", units_count=len(p["units"]), nssc=ref and ref["site"], nssc_match=ok,
                                 source="epsis-generators", detail=det))
            continue
        thr = THR[p["fuel"]]
        if p["mw"] < thr:
            plants_below[p["fuel"]] += 1
            continue
        det = [f"발전기 {len(p['units'])}기 합 {p['mw']:,.1f} MW: " + ", ".join(p["units"][:12]) + (" …" if len(p["units"]) > 12 else "")]
        if len(p["subtypes"]) > 1 or p["fuel"] == "hydro":
            det.append("연료원: " + ", ".join(f"{k} {v:,.1f} MW" for k, v in p["subtypes"].items()))
        if len(spans) > len(codes):
            det.append("발전기 소재지가 여러 시군구: " + ", ".join(f"{cnames(k)} {v:,.1f} MW" for k, v in p["by_unit"].items()) + " — 용량이 가장 큰 곳에 놓음")
        if p["failed_mw"]:
            det.append(f"소재지를 시군구로 읽지 못한 발전기 {p['failed_mw']:,.1f} MW 포함 (위치는 읽힌 발전기로 정함)")
        PW_items.append(item(KIND_OF[p["fuel"]], p["name"], unit_center(codes), "county", codes, value=round(p["mw"], 1), unit="MW",
                             year="2026-08", fuel=p["fuel"], subtype="양수" if "양수" in p["subtypes"] else ("수력" if p["fuel"] in ("hydro", "pumped") else None),
                             units_count=len(p["units"]), spans=sorted(spans), source="epsis-generators", detail=det))
    # 태양광·풍력: 시군구 합계 상위
    SOLAR_T, WIND_T = 500.0, 100.0
    solar_vals = sorted((v["solar"] for v in unit_fuel.values() if v["solar"]), reverse=True)
    wind_vals = sorted((v["wind"] for v in unit_fuel.values() if v["wind"]), reverse=True)
    for fu, thr, kind in (("solar", SOLAR_T, "power_solar"), ("wind", WIND_T, "power_wind")):
        n_g = collections.Counter()
        for r in gens:
            if FUEL[r["kind"].strip()] == fu:
                res = resolver.resolve(r["address"])
                if res:
                    n_g[frozenset(res["codes"])] += 1
        for codes, v in unit_fuel.items():
            if v[fu] >= thr:
                PW_items.append(item(kind, f"{FUEL_KO[fu]} 밀집 ({place_of(codes).split(' ', 1)[1]})", unit_center(codes), "county", codes,
                                     value=round(v[fu], 1), unit="MW (시군구 합계)", year="2026-08", gens=n_g[codes], source="epsis-generators",
                                     detail=[f"이 시군구 소재지로 적힌 {FUEL_KO[fu]} 발전기 {n_g[codes]:,}기 합계 {v[fu]:,.1f} MW",
                                             "낱개 발전소가 아니라 시군구 합계다 (발전기 좌표 없음)"]))
    kinds_count = collections.Counter(i["kind"] for i in PW_items)
    for k in ("power_coal", "power_gas", "power_oil", "power_hydro", "power_solar", "power_wind", "nuclear"):
        rank_items([i for i in PW_items if i["kind"] == k])
    pct = lambda vals, q: float(np.percentile(vals, q)) if len(vals) else None
    log(f"발전소 아이콘 {dict(kinds_count)}, 기준 미달 발전소 {dict(plants_below)}; 태양광 시군구 합계 95백분위 {pct(solar_vals, 95):.0f} MW "
        f"({sum(1 for x in solar_vals if x >= SOLAR_T)}곳 ≥ {SOLAR_T:g}), 풍력 {sum(1 for x in wind_vals if x >= WIND_T)}곳 ≥ {WIND_T:g}")
    for n in nuc_cmp:
        log(f"   원전 {n['sgg']}: {n['generators']} {n['mw']:,.0f} MW {n['units']}기 / 원안위 {n['nssc_site']} {n['nssc_mw']} MW {n['nssc_units']}기 → {n['match']}")
    pw_city, pw_sido = by_city_sum({k: dict(v) for k, v in unit_fuel.items()})
    power = {
        "fuel_ko": FUEL_KO, "fuel_raw": {v: k for k, v in FUEL.items()}, "generators": n_gen, "total_mw": round(total_mw, 3),
        "by_fuel_mw": {k: round(v, 3) for k, v in fuel_tot.most_common()}, "unit_sum_mw": round(unit_sum, 3),
        "failed": {"count": fail_n, "mw": round(fail_mw, 3), "by_fuel_mw": {k: round(v, 3) for k, v in gen_fail_fuel.items()},
                   "addresses": [{"address": a, "count": n, "mw": round(gen_fail_mw[a], 3)} for a, n in gen_fail.most_common()]},
        "by_city": pw_city, "by_sido": pw_sido, "nuclear_compare": nuc_cmp,
        "thresholds": {"coal": 500, "gas": 500, "oil": 500, "hydro_pumped": 100, "solar_county": SOLAR_T, "wind_county": WIND_T},
        "solar_county_pcts": {str(q): round(pct(solar_vals, q), 1) for q in (50, 90, 95, 99)},
        "wind_county_pcts": {str(q): round(pct(wind_vals, q), 1) for q in (50, 90, 95, 99)},
        "date": "2026-08-05"}
    name_rule = ("발전기 이름 끝의 호기 표기 — '#1', '1호기', '제1호기', 'CC1', 'GT1'·'ST1'·'GT#1'·'1GT', '2-1CC', '(#1 #2 #5)' — 를 되풀이해 떼고 "
                 "남은 이름이 같고 연료원 묶음이 같은 발전기를 한 발전소로 묶는다(석탄가스화는 석탄 묶음, 양수는 수력 묶음과 따로 묶되 같은 아이콘).")
    loc_rule = ("소재지(원표 '시도 시군구' 두 낱말)를 현재 시군구 이름표로 읽어 county 에 놓는다(일반구를 둔 시는 시 전체). 한 발전소의 발전기가 여러 "
                "시군구에 적혀 있으면 용량이 가장 큰 시군구. 옛 이름(당진군·여주군·청원군·마산시), 없는 이름(송도구·남구·횡선군), 시도가 없는 '한림읍'은 읽지 못한 것으로 센다.")
    src_gen = [src("epsis-generators", "C1/generators-20260805.txt")]
    PK = {
        "nuclear": {"name": "원전", "group": "power", "count": kinds_count["nuclear"], "placed": kinds_count["nuclear"],
                    "rule": ("한국전력거래소 EPSIS 발전기 현황(2026-08-05)의 연료원 '원자력' 발전기를 소재 시군구별로 묶어 그 시군구(county)에 놓는다. "
                             "값은 설비용량 합(MW). 원자력안전위원회 '국내 원자력발전소 현황'의 본부별 가동 용량(5a)과 나란히 대조한다: "
                             + "; ".join(f"{n['sgg']} {n['mw']:,.0f} MW ↔ {n['nssc_site']} {n['nssc_mw'] if n['nssc_mw'] is not None else '–'} MW "
                                         f"({'일치' if n['match'] else '다름'})" for n in nuc_cmp)
                             + ". 5a 의 '위치 없음' 원전 목록을 대신한다. " + loc_rule),
                    "source": src_gen + [r_ for r_ in resources["kinds"].get("nuclear", {}).get("source", []) if r_.get("key") != "epsis-generators"], "year": "2026-08-05 (발전기 현황)",
                    "missing": [], "precision_note": "county"},
        "power_coal": {"name": "석탄 발전소", "group": "power", "count": kinds_count["power_coal"], "placed": kinds_count["power_coal"],
                       "rule": f"연료원 '석탄'·'석탄가스화에너지' 발전기. {name_rule} 발전소 합계 500 MW 이상만 아이콘(미달 {plants_below['coal']}곳은 시군구 합계에만). {loc_rule}",
                       "source": src_gen, "year": "2026-08-05", "missing": [], "precision_note": "county"},
        "power_gas": {"name": "가스(LNG) 발전소", "group": "power", "count": kinds_count["power_gas"], "placed": kinds_count["power_gas"],
                      "rule": f"연료원 '가스' 발전기(복합·열병합). {name_rule} 발전소 합계 500 MW 이상만 아이콘(미달 {plants_below['gas']}곳은 시군구 합계에만). {loc_rule}",
                      "source": src_gen, "year": "2026-08-05", "missing": [], "precision_note": "county"},
        "power_oil": {"name": "유류 발전소", "group": "power", "count": kinds_count["power_oil"], "placed": kinds_count["power_oil"],
                      "rule": (f"연료원 '석유' 발전기 {sum(1 for r in gens if r['kind'] == '석유')}기 {fuel_tot['oil']:,.1f} MW. 같은 이름 규칙으로 묶으면 가장 큰 발전소도 "
                               f"500 MW 에 못 미친다(대부분 섬 내연발전). 그래서 아이콘이 없고 시군구 합계에만 싣는다."),
                      "source": src_gen, "year": "2026-08-05", "missing": [], "precision_note": "아이콘 없음"},
        "power_hydro": {"name": "수력·양수 발전소", "group": "power", "count": kinds_count["power_hydro"], "placed": kinds_count["power_hydro"],
                        "rule": f"연료원 '수력에너지'·'양수' 발전기. {name_rule} 발전소 합계 100 MW 이상만 아이콘(미달 수력 {plants_below['hydro']}곳·양수 {plants_below['pumped']}곳). {loc_rule}",
                        "source": src_gen, "year": "2026-08-05", "missing": [], "precision_note": "county"},
        "power_solar": {"name": "태양광 (시군구 합계)", "group": "power", "count": kinds_count["power_solar"], "placed": kinds_count["power_solar"],
                        "rule": (f"태양광 발전기 {sum(1 for r in gens if r['kind'] == '태양에너지'):,}기는 대부분 1 MW 미만이라 낱개로 그리지 않고 시군구 합계를 낸다. "
                                 f"시군구 합계의 분포(중앙값 {power['solar_county_pcts']['50']} MW, 90백분위 {power['solar_county_pcts']['90']}, 95백분위 {power['solar_county_pcts']['95']} MW)를 보고 "
                                 f"명세의 예시 300 MW(33곳)보다 높은 {SOLAR_T:g} MW 이상인 시군구 {kinds_count['power_solar']}곳에만 아이콘을 둔다(전국 화면이 덮이지 않게). "
                                 "모든 시군구 합계는 도시·시도 패널에."),
                        "source": src_gen, "year": "2026-08-05", "missing": [], "precision_note": "county (시군구 합계)"},
        "power_wind": {"name": "풍력 (시군구 합계)", "group": "power", "count": kinds_count["power_wind"], "placed": kinds_count["power_wind"],
                       "rule": (f"풍력 발전기의 시군구 합계(중앙값 {power['wind_county_pcts']['50']} MW, 95백분위 {power['wind_county_pcts']['95']} MW)가 "
                                f"{WIND_T:g} MW 이상인 시군구 {kinds_count['power_wind']}곳에 아이콘. 모든 시군구 합계는 패널에."),
                       "source": src_gen, "year": "2026-08-05", "missing": [], "precision_note": "county (시군구 합계)"},
    }
    PK["power_sums"] = {"name": "발전설비 (시군구 합계)", "group": "power", "count": n_gen, "placed": None,
                        "rule": (f"발전기 {n_gen:,}기 {total_mw:,.1f} MW 를 소재 시군구·연료원별로 더해 도시·시도 패널에 싣는다. 연료원(원표 값 → 화면 이름): "
                                 + ", ".join(f"'{k or '빈칸'}' → {FUEL_KO[v]}" for k, v in FUEL.items())
                                 + f". 소재지를 시군구로 읽지 못한 발전기 {fail_n}기 {fail_mw:,.1f} MW 는 합계에서 빠진다(연감에 주소 목록). "
                                 f"검산: 연료원별 합 = 시군구 합 {unit_sum:,.1f} + 대응 실패 {fail_mw:,.1f} MW."),
                        "source": src_gen, "year": "2026-08-05",
                        "missing": [{"name": f"{a['address']} ({a['count']}기)", "reason": f"{a['mw']:,.2f} MW — 소재지를 현재 시군구로 읽지 못함"} for a in power["failed"]["addresses"]],
                        "precision_note": "시군구 합계 (지도 아이콘은 위 종류)"}

    # =====================================================================
    # 국립공원 탐방객
    # =====================================================================
    pv = read_rows("park_visitors.csv")
    pvm = {nospace(r["name"]): (int(fnum(r["value"])), r["year"]) for r in pv}
    pv_total = sum(v for v, _ in pvm.values())
    park_unmatched = []
    for p in wonders["parks"]:
        v = pvm.get(nospace(p["short"]))
        if v is None:
            park_unmatched.append(p["name"])
            continue
        p["visitors"] = {"year": v[1], "value": v[0]}
    vis_park = [p for p in wonders["parks"] if p["visitors"]]
    vis_rank = {p["id"]: k + 1 for k, p in enumerate(sorted(vis_park, key=lambda p: -p["visitors"]["value"]))}
    vmax = max(p["visitors"]["value"] for p in vis_park)
    for it in wonders["items"]:
        if it["kind"] != "national_park":
            continue
        p = next(x for x in wonders["parks"] if x["id"] == it["ref"])
        if p["visitors"]:
            it.update(value=p["visitors"]["value"], unit="명 (2025 탐방객)", year=p["visitors"]["year"], rank=vis_rank[p["id"]],
                      size=round(math.sqrt(p["visitors"]["value"] / vmax), 3), area_km2=p["area_km2"])
            it["detail"] = [d for d in it["detail"] if not d.startswith("탐방객")]
            it["detail"][0] = f"경계 파일 기준(완충 구역 포함) 넓이 {p['area_km2']:,} km²" + (" (해상·해안 공원: 바다 포함)" if p["marine"] else "")
            it["detail"].insert(0, f"2025년 탐방객 {p['visitors']['value']:,}명 (전국 23개 공원 중 {vis_rank[p['id']]}위, 국립공원공단 기본통계)")
    pk = wonders["kinds"]["national_park"]
    pk["rule"] = pk["rule"].split(" 탐방객은 국립공원공단 2026")[0]
    pk["source"] = [x for x in pk["source"] if x.get("key") != "knps-statistics"]
    pk["year"] = pk["year"].split(" · 탐방객")[0]
    pk["rule"] = pk["rule"].replace("탐방객은 5b 에서 붙인다(필드는 null).", "").strip() + (
        f" 탐방객은 국립공원공단 2026 국립공원기본통계(수정 공표)의 2025년 값을 공원 이름(띄어쓰기 무시)으로 붙였다: {len(vis_park)}/{len(wonders['parks'])}곳 대응, "
        f"합계 {pv_total:,}명. 아이콘 크기와 전국 화면의 순위(탐방객 순)에 반영한다. 넓이 표기는 '경계 파일 기준(완충 구역 포함)'이다.")
    pk["source"] = pk["source"] + [src("knps-statistics")]
    pk["year"] = pk["year"] + " · 탐방객 2025"
    pk["visitors_total"] = pv_total
    pk["visitors_unmatched"] = park_unmatched
    log(f"국립공원 탐방객: 대응 {len(vis_park)}/{len(wonders['parks'])}, 원표 {len(pvm)}행 합계 {pv_total:,}, 못 붙인 공원 {park_unmatched}")

    # =====================================================================
    # 지리적표시
    # =====================================================================
    gi_rows = read_rows("geographical_indications.csv")
    VALID = {"농산물": {"유효"}, "임산물": {"운영"}, "수산물": {""}}
    stems = collections.defaultdict(list)
    for nm, lst in sigun.items():
        for codes in lst:
            stems[nm[:-1]].append((nm, codes))
    GI_items, gi_sido, gi_list = [], [], []
    n_valid = 0
    gi_excl = collections.Counter()
    for r in gi_rows:
        kind = r["kind"]
        st = r["registration_status"].strip()
        if kind not in VALID:
            raise ValueError(f"지리적표시 종류를 모름: {kind}")
        if st not in VALID[kind]:
            gi_excl[f"{kind} 상태 '{st or '빈칸'}'"] += 1
            continue
        n_valid += 1
        nm = r["name"].strip()
        area = re.sub(r"^행정구역상(의)?\s*", "", r["registration_area"].strip())
        base = {"no": r["registration_number"], "name": nm, "gi_kind": kind, "product": r["product"] or None, "area": r["registration_area"] or None,
                "registered": r["registration_date"] or None, "source": r["source_id"]}
        codes, place_from, note = None, None, None
        if area:
            a2 = area.replace("특례시", "시")
            res = resolver.resolve(a2)
            if res is None:
                sd, rest = resolver.sido_of(a2)
                if sd is not None and re.fullmatch(r"(일원|전역|일대)?", rest):
                    gi_sido.append(dict(base, sido=sd, reason="등록지역이 시도 전체"))
                    continue
                toks = [nospace(t) for t in re.split(r"[\s(,]+", a2) if t]
                hit = [sigun[t][0] for t in toks if t in sigun and len(sigun[t]) == 1]
                if hit:
                    res = {"codes": hit[0]}
                    note = "등록지역 문자열의 시도 표기를 읽지 못해 전국에 하나뿐인 시·군 이름으로 찾음"
            if res is None:
                gi_list.append(dict(base, reason=f"등록지역 '{r['registration_area']}' 에서 시군구를 읽지 못함 (전국 또는 날짜)"))
                continue
            codes, place_from = res["codes"], "area"
        else:
            cand = [(stem, lst) for stem, lst in stems.items() if nospace(nm).startswith(stem)]
            cand.sort(key=lambda t: -len(t[0]))
            if cand and len(cand[0][1]) == 1:
                codes, place_from = cand[0][1][0][1], "name"
                note = f"등록지역 칸이 비어 품목 이름이 '{cand[0][1][0][0]}' 이름으로 시작하는 것으로 놓음 (그 이름은 전국에 하나)"
            else:
                why = (f"품목 이름이 시·군 '{cand[0][0]}' 로 시작하지만 그 이름이 전국에 {len(cand[0][1])}곳" if cand
                       else "등록지역 칸이 비었고 품목 이름이 현재 시·군 이름으로 시작하지 않음")
                gi_list.append(dict(base, reason=why))
                continue
        codes = sorted(codes)
        det = [f"{kind} 지리적표시 {r['registration_number']}" + (f" · 품목 {r['product']}" if r["product"] and r["product"] != nm else ""),
               f"등록지역(원표): {r['registration_area']}" if r["registration_area"] else "등록지역 칸 빈칸"]
        if r["address"]:
            det.append(f"원표의 등록자 주소: {r['address']} (위치에는 쓰지 않음)")
        if note:
            det.append(note)
        GI_items.append(item("gi", nm, unit_center(codes), "county", codes, value=None, unit=None, year=(r["registration_date"] or "")[:4] or None,
                             gi_kind=kind, place_from=place_from, source=r["source_id"], detail=det))
    # 같은 시군구 칸에 겹치는 특산은 패널 목록으로 (아이콘 하나에 묶임) — 렌더러가 칸별 대표 하나를 그린다
    gi_per_unit = collections.Counter(tuple(i["sgg"]) for i in GI_items)
    for i in GI_items:
        i["value"] = gi_per_unit[tuple(i["sgg"])]
        i["unit"] = "건 (이 시군구의 지리적표시)"
    rank_items(GI_items)
    pf = collections.Counter(i["place_from"] for i in GI_items)
    log(f"지리적표시: 원자료 {len(gi_rows)}, 유효 {n_valid} = 지도 {len(GI_items)} (place_from {dict(pf)}) + 시도 {len(gi_sido)} + 목록만 {len(gi_list)}; 뺀 것 {dict(gi_excl)}")
    gi_kind = {"name": "특산 (지리적표시)", "group": "farm", "count": n_valid, "placed": len(GI_items),
               "rule": ("농산물(농식품부, 등록 상태 '유효'), 임산물(산림청, '운영'; '취소'는 뺌), 수산물(국립수산물품질관리원 등록 현황 — 원표에 상태 칸이 없어 "
                        "현황표에 실린 것을 유효로 봄)의 지리적표시. 등록지역이 있으면 그 문자열('행정구역상' 덧붙임을 떼고, '창원특례시'는 '창원시'로)에서 "
                        "시군구를 읽어 county 에 '특산' 아이콘을 둔다(place_from 'area'). 등록지역이 시도 전체('제주특별자치도 일원')면 지도에 놓지 않고 시도 패널에, "
                        "'국내'처럼 시군구가 없으면 연감 목록에만. 등록지역 칸이 빈 수산물·임산물은 품목 이름이 현재 시·군 이름('시'·'군'을 뗀 이름, 예: '완도')으로 "
                        "시작하고 그 이름이 전국에 하나뿐일 때만 그 시·군에 놓는다(place_from 'name', 등록자 주소는 쓰지 않음). 그 밖은 연감 목록에만. "
                        f"결과: 유효 {n_valid}건 = 지도 {len(GI_items)}(등록지역 {pf['area']} · 이름 {pf['name']}) + 시도 {len(gi_sido)} + 목록만 {len(gi_list)}."),
               "source": [src("mafra-farm-gi"), src("fish-gi"), src("forest-gi")], "year": "농산물 2026-03-17 · 임산물 2026-07 · 수산물 수집 시점",
               "missing": [{"name": g["name"], "reason": g["reason"]} for g in gi_list], "excluded": dict(gi_excl),
               "sido_level": [{"name": g["name"], "reason": f"{sido_short[g['sido']]} 전체"} for g in gi_sido],
               "place_from": dict(pf), "precision_note": "county"}

    # =====================================================================
    # 쌀 · 축산 (시군구 표)
    # =====================================================================
    def umap_of(table, indicator, additive=True, year=None):
        rows = [r for r in ec.table(table) if r["indicator"] == indicator and (year is None or r["year"] == year)]
        return ec.unit_map(rows, additive)

    def top_items(umap, kind, n, name_fmt, unit, year, src_id, detail_fn):
        vals = [(k, v) for k, v in umap.items() if v is not None]
        vals.sort(key=lambda kv: -kv[1])
        out = []
        for k, v in vals[:n]:
            out.append(item(kind, name_fmt(place_of(k).split(" ", 1)[1]), unit_center(k), "county", k, value=as_int(v), unit=unit, year=year,
                            source=src_id, detail=detail_fn(k, v)))
        return rank_items(out), vals

    rice = umap_of("rice", "paddy_rice_production")
    RICE_N = 20
    RI, rice_sorted = top_items(rice, "rice", RICE_N, lambda p: f"쌀 · {p}", "톤 (2026 논벼)", "2026", "kosis-101-DT_1ET0034",
                                lambda k, v: [f"2026년 논벼 생산량(정곡 92.9%) {int(v):,}톤", "농작물생산조사 시군별 논벼 생산량"])
    pigs = umap_of("livestock", "pigs")
    cattle = umap_of("livestock", "beef_cattle_including_non_hanwoo")
    LV_N = 15
    PI, pig_sorted = top_items(pigs, "pigs", LV_N, lambda p: f"돼지 · {p}", "마리 (2019)", "2019", "data-15071107",
                               lambda k, v: [f"2019년 돼지 {int(v):,}마리", "국립환경과학원 전국오염원조사 축산계 (사육지 기준)"])
    CA, cat_sorted = top_items(cattle, "cattle", LV_N, lambda p: f"한우·육우 · {p}", "마리 (2019)", "2019", "data-15071107",
                               lambda k, v: [f"2019년 한우·육우 {int(v):,}마리 (원표는 한우와 육우를 합쳐 공표, 한우만 분리한 시군구 값은 없음)",
                                             "국립환경과학원 전국오염원조사 축산계 (사육지 기준)"])
    lv_blank = sorted({r["key"] for r in ec.table("livestock") if r["raw_empty"]})
    log(f"쌀 상위 {len(RI)} (단위 {len(rice)}개), 돼지 {len(PI)}, 한우·육우 {len(CA)}; 축산 원표 빈 값 단위 {lv_blank}")

    def per_city(umap):
        out = {}
        for c in cities:
            v = E.agg(umap, c["sgg"])
            if v is not None:
                out[str(c["id"])] = as_int(v)
            elif any(k & set(c["sgg"]) for k in umap):
                out[str(c["id"])] = None
        return out

    def per_sido(umap):
        out = {}
        for s in w["states"]:
            codes = [c["code"] for c in w["counties"] if c["sido"] == s["code"]]
            parts = [v for k, v in umap.items() if k <= set(codes)]
            out[s["code"]] = {"sum": as_int(sum(v for v in parts if v is not None)), "units": len(parts), "blank": sum(1 for v in parts if v is None)}
        return out

    farm = {"rice": {"by_city": per_city(rice), "by_sido": per_sido(rice), "year": "2026", "unit": "톤", "label": "논벼 생산량 (정곡 92.9%)"},
            "pigs": {"by_city": per_city(pigs), "by_sido": per_sido(pigs), "year": "2019", "unit": "마리", "label": "돼지"},
            "cattle": {"by_city": per_city(cattle), "by_sido": per_sido(cattle), "year": "2019", "unit": "마리", "label": "한우·육우"},
            "livestock_blank": [cnames(k) if len(k) else k for k in []]}
    lv_blank_names = sorted({f"{r['sido_now']} {r['sgg_name_raw']}" for r in read_rows("livestock.csv") if not r["value"].strip()})
    farm["livestock_blank"] = lv_blank_names
    farm_kinds = {
        "rice": {"name": "쌀 (생산량 상위)", "group": "farm", "count": len(RI), "placed": len(RI),
                 "rule": (f"농작물생산조사 2026년 시군별 논벼 생산량(정곡 92.9%, 톤) 상위 {RICE_N}곳(값이 있는 단위 {len(rice_sorted)}곳 중)에 '쌀' 아이콘. "
                          "시 전체로만 공표된 값(화성시·청주시 등)은 그 시 단위 하나로 순위를 매긴다. 모든 시군 값은 도시 패널 식량 구역에."),
                 "source": [src("kosis-101-DT_1ET0034")], "year": "2026", "missing": [], "precision_note": "county"},
        "pigs": {"name": "돼지 (사육 상위)", "group": "farm", "count": len(PI), "placed": len(PI),
                 "rule": (f"국립환경과학원 전국오염원조사 축산계 2019년 돼지 사육 마릿수 상위 {LV_N}곳. 기준 연도 2019. 원표에서 같은 시도·시군 이름이 되풀이돼 어느 값이 "
                          f"시군 전체인지 알 수 없는 {len(lv_blank_names)}곳({', '.join(lv_blank_names)})은 빈 값(0 이 아님)."),
                 "source": [src("data-15071107")], "year": "2019", "missing": [], "precision_note": "county"},
        "cattle": {"name": "한우·육우 (사육 상위)", "group": "farm", "count": len(CA), "placed": len(CA),
                   "rule": (f"같은 조사의 한우(육우 포함) 마릿수 상위 {LV_N}곳. 원표가 한우와 육우를 합쳐 공표해 표기는 '한우·육우'. 기준 연도 2019. "
                            "빈 값 규칙은 돼지와 같다."),
                   "source": [src("data-15071107")], "year": "2019", "missing": [], "precision_note": "county"},
    }

    # =====================================================================
    # 주력 업종 (지도 아이콘 없음)
    # =====================================================================
    ki = ec.table("key_industries")
    inds = sorted({r["industry"] for r in ki})
    ki_units = {ind: ec.unit_map([r for r in ki if r["industry"] == ind], True) for ind in inds}
    ki_city = {}
    for c in cities:
        row = {}
        for ind in inds:
            um = ki_units[ind]
            if not any(k & set(c["sgg"]) for k in um):
                continue
            row[ind] = as_int(E.agg(um, c["sgg"]))
        if row:
            ki_city[str(c["id"])] = row
    ki_sido = sorted({r["sido_now"] for r in read_rows("key_industries.csv")})
    log(f"주력 업종: 업종 {len(inds)}개, 값이 붙은 도시 {len(ki_city)}곳, 시도 {ki_sido}")
    ki_kind = {"name": "주력 업종 종사자 (지도 아이콘 없음)", "group": "farm", "count": len(ki_city), "placed": None,
               "rule": (f"전국사업체조사 2024 도별 통계표의 업종 {len(inds)}개({', '.join(inds)}) 종사자 수. {len(ki_sido)}개 시도({', '.join(ki_sido)})의 시군만 "
                        "자료가 있어 전국 비교가 안 되므로 지도 아이콘 없이, 값이 있는 도시의 패널에 보조 정보로 싣는다. 5개 시도만 자료 있음. "
                        "시 전체 공표값은 일반구에 나누지 않는다. 비공개(빈 값)는 '비공개'."),
               "source": [{"key": "key_industries", "title": "주력 업종 종사자 정리표 (도별 전국사업체조사 통계표 2)", "publisher": "각 도",
                           "retrieved": "", "file": "layers/key_industries.csv"}], "year": "2024", "missing": [], "precision_note": "시군 값 (지도 없음)",
               "industries": inds, "sido": ki_sido}

    # =====================================================================
    # 접경 -> frontier.json
    # =====================================================================
    fr_rows = read_rows("border_areas.csv")
    areas = []
    for r in fr_rows:
        res = ec.resolve(r)
        if res is None:
            raise ValueError(f"접경지역 시군을 현재 시군구로 읽지 못함: {r['sido_now']} {r['sgg_name_raw']}")
        m = re.search(r"제2조제(\d)항", r["basis"])
        areas.append({"name": r["sgg_name_raw"], "sido": W.sido_of_code[sorted(res[2])[0]], "sgg": sorted(res[2]),
                      "article": r["basis"], "clause": int(m.group(1)) if m else None,
                      "city": city_of_code.get(sorted(res[2])[0])})
    frontier = {"version": VERSION, "name": "접경지역", "areas": areas,
                "rule": ("「접경지역 지원 특별법 시행령」 제2조의 접경지역 17개 시·군(제1항 10곳, 제2항 7곳; 2025-03-11 시행 개정으로 가평군·속초시 포함). "
                         "고양시는 시 단위로 지정돼 일반구 전부를 칠한다. 켜면 해당 시군의 영토 테두리를 띠로 강조하고 휴전선을 함께 굵게 보인다. "
                         "도시 패널에 '접경지역(시행령 제2조제○항)'을 적는다. 군사시설보호구역 면적은 받지 못해 싣지 않고, 군 기지 위치는 싣지 않는다."),
                "source": [src("border-article"), src("border-law"), src("border-act")], "year": "2025-03-11 시행"}
    log(f"접경지역 {len(areas)}곳 (제1항 {sum(1 for a in areas if a['clause'] == 1)}, 제2항 {sum(1 for a in areas if a['clause'] == 2)})")

    # =====================================================================
    # 도로 (표준노드링크) — Natural Earth 도로 교체
    # =====================================================================
    road_path = layer_path("roads.geojson")
    stamp = np.array([os.path.getsize(road_path), int(os.path.getmtime(road_path))], dtype=np.int64)
    cache = build("roads_5b.npz")
    TOL = {"고속국도": 250.0, "일반국도": 300.0}
    DUP_CELL, DUP_FRAC, MIN_LEN = 150.0, 0.7, 300.0
    if os.path.exists(cache) and np.array_equal(np.load(cache, allow_pickle=False)["stamp"], stamp):
        z = np.load(cache, allow_pickle=False)
        road_meta = {k: z[k] for k in z.files}
        log("도로: 캐시 사용 (data/build/roads_5b.npz)")
    else:
        import pyogrio.raw as R
        meta, _, geom, fields = R.read(road_path)
        if "4326" not in str(meta.get("crs")):
            raise ValueError("roads.geojson 좌표계가 EPSG:4326 이 아님")
        cols = dict(zip(list(meta["fields"]), fields))
        g = shapely.from_wkb(geom)
        g = shapely.transform(g, lambda xy: np.column_stack(TO5179.transform(xy[:, 0], xy[:, 1])))
        grade, route = cols["grade"].astype(str), cols["route"].astype(str)
        link_len = shapely.length(g)
        out_xy, out_off, out_grade, out_route = [], [0], [], []
        dedup_len = collections.Counter()

        def samples(ln, step=75.0):
            n = max(2, int(ln.length / step) + 1)
            p = shapely.line_interpolate_point(ln, np.linspace(0, ln.length, n))
            return np.column_stack([shapely.get_x(p), shapely.get_y(p)])

        for gr in ("고속국도", "일반국도"):
            for rt in sorted(set(route[grade == gr]), key=lambda s: (len(s), s)):
                m = (grade == gr) & (route == rt)
                merged = shapely.line_merge(shapely.union_all(g[m]))
                parts = sorted(getattr(merged, "geoms", [merged]), key=lambda l: -l.length)
                occ = set()
                for ln in parts:
                    k = np.floor(samples(ln) / DUP_CELL).astype(np.int64)
                    hit = sum(1 for a, b in k if (a, b) in occ)
                    if hit >= DUP_FRAC * len(k):
                        continue
                    for a, b in k:
                        for da in (-1, 0, 1):
                            for db in (-1, 0, 1):
                                occ.add((a + da, b + db))
                    s = ln.simplify(TOL[gr])
                    if s.length < MIN_LEN:
                        continue
                    dedup_len[gr] += s.length
                    c_ = np.asarray(s.coords)
                    out_xy.append(c_)
                    out_off.append(out_off[-1] + len(c_))
                    out_grade.append(1 if gr == "고속국도" else 2)
                    out_route.append(rt)
        road_meta = {"stamp": stamp, "xy": np.concatenate(out_xy), "off": np.array(out_off), "grade": np.array(out_grade),
                     "route": np.array(out_route), "raw_links": np.array([int((grade == "고속국도").sum()), int((grade == "일반국도").sum())]),
                     "raw_km": np.array([link_len[grade == "고속국도"].sum() / 1000, link_len[grade == "일반국도"].sum() / 1000]),
                     "routes": np.array([len(set(route[grade == "고속국도"])), len(set(route[grade == "일반국도"]))]),
                     "dedup_km": np.array([dedup_len["고속국도"] / 1000, dedup_len["일반국도"] / 1000])}
        np.savez_compressed(cache, **road_meta)
        log("도로: 원자료에서 다시 만듦 → data/build/roads_5b.npz")
    hexes = [Polygon([(W.centers[i][0] + W.G.R * math.cos(math.radians(60 * k - 30)), W.centers[i][1] + W.G.R * math.sin(math.radians(60 * k - 30)))
                      for k in range(6)]) for i in range(W.N) if W.land[i]]
    fhex = [Polygon([(W.centers[i][0] + W.G.R * 1.001 * math.cos(math.radians(60 * k - 30)), W.centers[i][1] + W.G.R * 1.001 * math.sin(math.radians(60 * k - 30)))
                     for k in range(6)]) for i in range(W.N) if W.foreign[i] == 1]
    clip = shapely.union_all(hexes).buffer(W.G.R * 0.5).difference(shapely.union_all(fhex))
    roads = []
    xy, off = road_meta["xy"], road_meta["off"]
    for k in range(len(off) - 1):
        c_ = xy[off[k]:off[k + 1]]
        ux, uy = W.m2u(c_[:, 0], c_[:, 1])
        ln = shapely.LineString(np.column_stack([ux, uy])).intersection(clip)
        for part in getattr(ln, "geoms", [ln]):
            if part.is_empty or part.geom_type != "LineString" or part.length < 0.5:
                continue
            roads.append({"tier": int(road_meta["grade"][k]), "route": str(road_meta["route"][k]),
                          "pts": [round(v, 1) for p_ in part.coords for v in p_]})
    rk = road_meta
    road_stats = {"expressway": {"links": int(rk["raw_links"][0]), "routes": int(rk["routes"][0]), "raw_link_km": round(float(rk["raw_km"][0]), 1),
                                 "dedup_km": round(float(rk["dedup_km"][0]), 1)},
                  "national": {"links": int(rk["raw_links"][1]), "routes": int(rk["routes"][1]), "raw_link_km": round(float(rk["raw_km"][1]), 1),
                               "dedup_km": round(float(rk["dedup_km"][1]), 1)},
                  "lines": len(roads), "points": sum(len(r_["pts"]) // 2 for r_ in roads)}
    log(f"도로: {road_stats}")
    old_rails = infra["lines"]["rails"]
    infra["lines"] = {"roads": roads, "rails": old_rails, "note": "철도 선 — 초안: Natural Earth 1:10m, 공식 철도망으로 교체 예정",
                      "road_note": "국가교통정보센터 전국표준노드링크 (2026-11-11), 고속국도·일반국도"}
    infra["kinds"]["roads"] = {
        "name": "도로 선", "group": "lines", "count": len(roads),
        "rule": (f"국가교통정보센터 전국표준노드링크(2026-11-11)의 도로등급 101 고속국도 {road_stats['expressway']['links']:,}개·103 일반국도 "
                 f"{road_stats['national']['links']:,}개 링크. 노선번호(고속 {road_stats['expressway']['routes']}개, 일반국도 {road_stats['national']['routes']}개)별로 "
                 "맞닿은 링크를 이어 붙인 뒤, 상·하행이 따로 그려진 링크와 나들목 연결로를 빼려고 같은 노선 안에서 긴 선부터 남기며 이미 남긴 선의 "
                 f"{DUP_CELL:.0f} m 격자 이웃 안에 {DUP_FRAC * 100:.0f}% 이상 드는 선은 뺀다. 남은 선을 EPSG:5179 에서 고속국도 {TOL['고속국도']:.0f} m · 일반국도 "
                 f"{TOL['일반국도']:.0f} m 허용 오차로 단순화하고 {MIN_LEN:.0f} m 미만 조각은 버린다. 고속국도는 전국 화면부터, 일반국도는 확대했을 때 그린다. "
                 f"연장: 고속국도 링크 합 {road_stats['expressway']['raw_link_km']:,.0f} km(상·하행 따로) → 겹침 뺀 뒤 {road_stats['expressway']['dedup_km']:,.0f} km, "
                 f"일반국도 {road_stats['national']['raw_link_km']:,.0f} → {road_stats['national']['dedup_km']:,.0f} km. 대한민국 육지 칸(반 칸 여백) 안만 남긴다."),
        "source": [src("its-nodelink-20261111")], "year": "2026-11-11", "missing": [], "draft": False, "stats": road_stats}
    infra["kinds"]["rails"]["rule"] = infra["kinds"]["rails"]["rule"]  # 철도는 초안 그대로

    # =====================================================================
    # 층 JSON 정리
    # =====================================================================
    # 원전: 5a 의 원안위 본부 목록은 대조용으로 남기고 '위치 없음' 목록에서 뺀다
    resources["nuclear_nssc"] = nssc
    resources["unplaced"] = [u for u in resources["unplaced"] if u["kind"] != "nuclear"]
    dk = resources["kinds"]["dam"]
    if "5b:" not in dk["rule"]:
        dk["rule"] += (" 5b: 수면 자료(lakes.geojson)의 '○○호' 이름과 댐 이름 '○○댐'이 맞는 경우가 있어도 이름이 비슷하다는 것만으로는 위치 근거가 "
                       "부족해 지도에 놓지 않는다(목록만).")
    resources["kinds"].pop("nuclear", None)
    infra["kinds"].pop("airport", None)
    infra["unplaced"] = [u for u in infra["unplaced"] if u["kind"] != "airport"]
    infra["items"] = [i for i in infra["items"] if i["kind"] not in ("airport", "trade_port")]
    # 5b 항목은 각 층 JSON 끝에 붙인다 (id 는 층 접두 + 번호)
    resources["items"] = [i for i in resources["items"] if i["kind"] not in ("nuclear",) and not i["kind"].startswith("power_")
                          and i["kind"] not in ("gi", "rice", "pigs", "cattle")]
    base_r = len(resources["items"])
    new_r = PW_items + GI_items + RI + PI + CA
    for k, it in enumerate(new_r):
        it["id"] = f"r5-{k}"
    resources["items"] += new_r
    for k, it in enumerate(A_items + P_items):
        it["id"] = f"i5-{k}"
    infra["items"] += A_items + P_items
    resources["kinds"] = {**PK, **resources["kinds"], "gi": gi_kind, **farm_kinds, "key_industries": ki_kind}
    infra["kinds"] = {**infra["kinds"], "airport": air_kind, "trade_port": port_kind}
    resources["power"] = power
    resources["farm"] = farm
    resources["gi"] = {"sido_level": gi_sido, "list_only": gi_list, "excluded": dict(gi_excl), "valid": n_valid}
    resources["key_industries"] = {"by_city": ki_city, "industries": inds, "sido": ki_sido}
    resources["knowledge"] = {
        "research_institutes": [r["name"] for r in read_rows("research_institutes.csv")],
        "note": ("지식 불가사의: 위치·연구비 자료 미확보. 국가과학기술연구회 인력 공표 CSV 는 소관 출연연 "
                 f"{len(read_rows('research_institutes.csv'))}곳의 기관명만 준다. 주소, 대학별 연구비, 과학기술원 정리표가 없어 지도에 놓지 않는다."),
        "source": [src("data-15045195")]}
    resources["trade_routes"] = {
        "note": ("교역로는 만들지 않았다. 필요한 자료: 한국도로공사 영업소 간 교통량(공공데이터포털 다운로드에 로그인 필요), "
                 "관세청 시군구 수출입 실적(공식 API 키·활용 신청 필요), 한국교통연구원 KTDB 화물 기종점(O/D) 통행량(자료 신청서·승인 필요). "
                 "인증키·로그인·신청이 필요한 자료는 받지 않는다는 원칙에 따라 목록으로만 남긴다.")}
    for obj in (resources, infra):
        obj["version"] = VERSION
        obj["precision_counts"] = dict(collections.Counter(i["precision"] for i in obj["items"]))
        for it in obj["items"]:
            v = it.get("value")
            if isinstance(v, float) and v.is_integer():
                it["value"] = int(v)
    wonders["version"] = VERSION
    for nm, obj in (("wonders", wonders), ("resources", resources), ("infrastructure", infra), ("frontier", frontier)):
        size = save_json(site(f"{nm}.json"), obj)
        log(f"{nm}.json {size / 1e3:.0f} KB" + (f", 아이콘 {len(obj['items'])}개, 정밀도 {obj['precision_counts']}" if "items" in obj else ""))

    # =====================================================================
    # 렌즈
    # =====================================================================
    N = W.N
    land = W.land
    county = W.county
    county_codes = W.codes
    nl = int(land.sum())
    pop = E.Population(set(county_codes))
    new_l = []
    cover_log = {}

    def pdom(vals, lo=2, hi=98):
        v = np.array([x for x in vals if x is not None], float)
        return [float(np.percentile(v, lo)), float(np.percentile(v, hi))]

    def add_cells(lid, group, name, emoji, unit, fmt, scale, ramp, higher, basis, vintage, source, desc, vals, **extra):
        cov = sum(1 for i in range(N) if land[i] and vals[i] is not None) / nl
        cover_log[lid] = round(100 * cov, 1)
        if cov < 0.5:
            log(f"!! 렌즈 {lid}: 값이 있는 육지 칸 {100 * cov:.1f}% < 50% — 만들지 않음")
            return
        L = {"id": lid, "group": group, "name": name, "emoji": emoji, "unit": unit, "format": fmt, "scale": scale, "ramp": ramp,
             "higher_is": higher, "basis": basis, "vintage": vintage, "source": source, "description": desc, "values": vals,
             "coverage": round(cov, 4), "phase": "5b"}
        L.update(extra)
        if "domain" not in L:
            d = pdom(vals)
            L["domain"] = [rnd(d[0], 2), rnd(d[1], 2)]
        new_l.append(L)

    from lib import units as U
    namer = U.Namer(W.w, cities)

    def add_county(lid, group, name, emoji, unit, fmt, scale, ramp, higher, basis, vintage, source, desc, umap, nd=1, **extra):
        # 여러 시군구에 걸친 공표 단위(시 전체·개편 전 구)는 lens.units 에 적는다 (감사 01)
        cval = {}
        for k, v in umap.items():
            for code in k:
                cval[code] = v
        by_county = [rnd(cval.get(code), nd) if cval.get(code) is not None else None for code in county_codes]
        vals = [by_county[county[i]] if land[i] else None for i in range(N)]
        cov = sum(1 for i in range(N) if land[i] and vals[i] is not None) / nl
        cover_log[lid] = round(100 * cov, 1)
        if cov < 0.5:
            log(f"!! 렌즈 {lid}: 값이 있는 육지 칸 {100 * cov:.1f}% < 50% — 만들지 않음")
            return
        L = {"id": lid, "group": group, "name": name, "emoji": emoji, "unit": unit, "format": fmt, "scale": scale, "ramp": ramp,
             "higher_is": higher, "basis": basis, "vintage": vintage, "source": source, "description": desc, "by_county": by_county,
             "coverage": round(cov, 4), "phase": "5b"}
        L.update(extra)
        U.annotate(L, [(k, vintage) for k, v in umap.items() if v is not None], namer)
        if "domain" not in L:
            d = pdom(vals)
            L["domain"] = [rnd(d[0], 2), rnd(d[1], 2)]
        new_l.append(L)

    SEQ_FOREST = ["#f4f1e4", "#d6e4b8", "#a7cc8a", "#6fa865", "#3f7f46", "#1d5230"]
    SEQ_CROP = ["#f6f2e2", "#efe1a6", "#dcc66a", "#bca13d", "#8f7a22", "#5c4f12"]
    SEQ_BUILT = ["#f3f1ef", "#dcd4d2", "#bcaeab", "#977f7c", "#6c5552", "#3f2f2e"]
    SEQ_TEAL = ["#eef6f4", "#c3e3dc", "#8cc8bb", "#52a596", "#287a6e", "#0f4e47"]
    SEQ_AIR = ["#eef6f1", "#cfe6c4", "#f0e29a", "#efb066", "#d76a45", "#9e2f35"]
    SEQ_RED = ["#fbf0ec", "#f3cbbd", "#e79a83", "#d4664f", "#ad3a2f", "#741c1c"]
    SEQ_PURP = ["#f4f0f7", "#dccdea", "#bea4d6", "#9c79bc", "#78519f", "#4d2a78"]
    SEQ_BLUE = ["#eef3f9", "#c9d9ec", "#97b8db", "#5f90c4", "#33669f", "#183f70"]
    SEQ_GREEN = ["#f3f6e8", "#d5e8b4", "#a9d18a", "#73b161", "#3f8a43", "#1a5c2c"]
    SEQ_BROWN = ["#f7f1e6", "#e7d3b0", "#d0ae79", "#b2844b", "#875b2b", "#583816"]

    # 땅: 칸별 토지피복 비율 (정확한 값, terrain_cache.npz). 두 판 공용: 기후에너지환경부 세분류 토지피복지도 도엽 통계를 칸에 나눈 값 (lib/cover_sheets.py)
    tz = np.load(build("terrain_cache.npz"))
    if str(tz["profile"]) != PRF.PROFILE:
        raise RuntimeError(f"terrain_cache.npz 가 {tz['profile']} 판 world 빌드 — build_world.py 를 같은 판으로 다시 돌린다")
    skeys = [str(k) for k in tz["share_keys"]]
    cs = tz["cover_share"]
    csrc = tz["cover_src"]
    land_idx = np.nonzero(land)[0]
    n_esa = int((csrc[land] == 2).sum())
    cmeta = load_json(site("world.json"))["cover_meta"]
    src_me = CS.SOURCE_NAME
    yr = cmeta["label"]
    bias_note = " " + cmeta["bias_note"]
    cover_note = f"칸 비율은 {CS.SOURCE_NAME}를 칸에 나눈 값이다: " + cmeta["method"]
    esa_note = (f" 도엽 통계가 닿지 않는 {n_esa}칸은 대체 자료 ESA WorldCover 2021 v200 (CC BY 4.0) 250 m 최빈값 격자로 채웠다." if n_esa else "")
    esa_none = (f" 도엽 통계가 닿지 않는 {n_esa}칸은 ESA 에 이 구분이 없어 자료 없음." if n_esa else "")
    vintage = f"{max(int(y) for y in cmeta['sheets']['chosen_base_year'])} (도엽 통계 기준년도)"

    def as_land(lid, vals):
        """칸 배열 -> 육지 칸 값 (육지 아닌 칸에 값이 있으면 빌드 오류)."""
        if any(vals[i] is not None for i in range(N) if not land[i]):
            raise ValueError(f"렌즈 {lid}: 육지 아닌 칸에 값")
        return [vals[i] for i in land_idx]

    def add_land(lid, name, emoji, ramp, desc, vals, source, vintage):
        add_cells(lid, "land", name, emoji, "%", "pct1", "linear", ramp, "neutral", "칸 (세분류 토지피복지도 도엽 통계)", vintage, source, desc, vals,
                  domain=[0, 100])
        if new_l and new_l[-1]["id"] == lid:
            L_ = new_l[-1]
            L_["land_values"] = as_land(lid, L_.pop("values"))
            L_["cells"] = "land"
            L_["phase"] = "5c"

    sub_of = {k: [nm for nm, kk in CS.CLASS_MAP if kk == k] for k in CS.LEAVES}
    for lid, key, name, emoji, ramp, parts in (("forest", "forest", "숲", "🌲", SEQ_FOREST, "활엽수림·침엽수림·혼효림"),
                                               ("cropland", "crop", "농경지", "🌾", SEQ_CROP, "논·밭·시설재배지·과수원·목장양식장·기타재배지"),
                                               ("built", "built", "시가지", "🏙️", SEQ_BUILT, "시가화건조지역 세분류 14개")):
        q = skeys.index(key)
        vals = [None if (not land[i] or np.isnan(cs[i, q])) else rnd(100 * cs[i, q], 1) for i in range(N)]
        add_land(lid, name, emoji, ramp, f"칸 넓이 중 {name}({parts}) 비율. {cover_note}{esa_note}{bias_note}", vals,
                 src_me + (f" · 도엽 통계가 닿지 않는 {n_esa}칸 ESA WorldCover 2021 v200 (대체 자료, CC BY 4.0)" if n_esa else ""), vintage)
    for lid, key, name, emoji, ramp in (("paddy_share", "paddy", "논 (칸)", "🌾", SEQ_GREEN), ("field_share", "field", "밭 (칸)", "🥬", SEQ_BROWN)):
        q = skeys.index(key)
        vals = [None if (not land[i] or csrc[i] != 1 or np.isnan(cs[i, q])) else rnd(100 * cs[i, q], 1) for i in range(N)]
        add_land(lid, name, emoji, ramp, f"칸 넓이 중 {name.split(' ')[0]}(세분류 {'·'.join(sub_of[key])}) 비율. {cover_note}{esa_none}{bias_note}", vals, src_me, vintage)
    qf, qc = skeys.index("forest"), skeys.index("conifer")
    vals = [None if (not land[i] or csrc[i] != 1 or not (cs[i, qf] >= CONIFER_MIN_FOREST)) else rnd(100 * cs[i, qc] / cs[i, qf], 1) for i in range(N)]
    add_land("conifer", "침엽수림 비중", "🌲", SEQ_TEAL,
             f"숲(활엽수림·침엽수림·혼효림) 가운데 침엽수림 비율. 숲이 칸의 {CONIFER_MIN_FOREST * 100:.0f}% 미만이면 비율이 흔들려 자료 없음. "
             f"{cover_note}{esa_none}", vals, src_me, vintage)

    # 사람: 외국인주민 ÷ 같은 조사의 총인구
    fr = umap_of("foreign_residents", "foreign_residents")
    fb = umap_of("foreign_residents", "foreign_residents_population_base")
    fmap = {k: (None if v is None or not fb.get(k) else 100 * v / fb[k]) for k, v in fr.items()}
    add_county("foreign", "people", "외국인 주민", "🌏", "%", "pct1", "linear", SEQ_TEAL, "neutral", "거주지", "2024-11-01",
               "행정안전부 지방자치단체 외국인주민 현황 (2024)",
               "외국인주민(외국인 근로자·결혼이민자·유학생·외국국적동포·기타 외국인, 귀화자·외국인주민 자녀 포함) ÷ 같은 조사의 총인구(주민등록 인구 + 등록 외국인 등). "
               "시 전체로만 공표된 값은 소속 일반구 칸에 같은 값을 칠한다.", fmap, nd=2)

    # 일상: PM2.5 (측정소 거리 역가중)
    pm = read_rows("pm25_stations.csv")
    st_ok, st_excl = [], collections.Counter()
    for r in pm:
        if "*" in r["kind"]:
            st_excl["유효측정비율 미달 표시(* 또는 **)"] += 1
            continue
        v = fnum(r["value"])
        if v is None:
            st_excl["연평균 값 없음"] += 1
            continue
        lon, lat = fnum(r["lon"]), fnum(r["lat"])
        if lon is None or lat is None:
            st_excl["좌표 없음"] += 1
            continue
        e_, n_ = TO5179.transform(lon, lat)
        st_ok.append((e_, n_, v))
    S = np.array(st_ok)
    ce = W.ox + W.centers[:, 0] * W.mpu
    cn = W.oy - W.centers[:, 1] * W.mpu
    RAD, KN = 30000.0, 3
    from scipy.spatial import cKDTree
    tree = cKDTree(S[:, :2])
    dd, ii = tree.query(np.column_stack([ce, cn]), k=KN, distance_upper_bound=RAD)
    pmv = []
    for i in range(N):
        if not land[i]:
            pmv.append(None)
            continue
        ok = np.isfinite(dd[i])
        if not ok.any():
            pmv.append(None)
            continue
        d_ = np.maximum(dd[i][ok], 500.0)
        wts = 1.0 / d_
        pmv.append(rnd(float((S[ii[i][ok], 2] * wts).sum() / wts.sum()), 1))
    add_cells("pm25", "daily", "초미세먼지", "😷", "µg/m³", "f1", "linear", SEQ_AIR, "bad", "측정소 (칸 중심 30 km 안)", "2025",
              "환경부 2025 대기환경연보 (측정소별 PM2.5 연평균, 측정소 제원 좌표)",
              f"PM2.5 연평균. 칸 중심에서 {RAD / 1000:.0f} km 안의 도시대기 등 측정소 가운데 가까운 {KN}곳까지를 거리 역가중(1/거리, 거리는 0.5 km 아래로 두지 않음) 평균한다. "
              f"30 km 안에 측정소가 없으면 자료 없음. 원표에서 유효측정비율 미달 표시(* 또는 **)가 붙은 측정소 {st_excl['유효측정비율 미달 표시(* 또는 **)']}곳과 "
              f"값·좌표가 없는 측정소({st_excl['연평균 값 없음'] + st_excl['좌표 없음']}곳)는 뺐다. 쓴 측정소 {len(st_ok)}곳.",
              pmv, stations_used=len(st_ok), stations_excluded=dict(st_excl))
    log(f"PM2.5 측정소: 원표 {len(pm)}, 사용 {len(st_ok)}, 뺀 것 {dict(st_excl)}")

    # 일상: 건강 네 지표 (합치지 않음)
    HL = [("smoking", "current_smoking_rate", "현재 흡연율", "🚬", SEQ_BROWN, "bad", "평생 담배 5갑(100개비) 이상 피웠고 현재 피우는 사람의 비율"),
          ("obesity", "self_reported_obesity_rate", "비만율", "⚖️", SEQ_RED, "bad", "자가보고 키·몸무게로 낸 체질량지수 25 이상 비율"),
          ("depression", "annual_depressed_mood_rate", "우울감 경험률", "🌧️", SEQ_PURP, "bad", "최근 1년 동안 2주 이상 연속으로 일상생활에 지장이 있을 만큼 슬프거나 절망감을 느낀 사람의 비율"),
          ("health_good", "self_rated_good_health_rate", "주관적 건강 양호", "💪", SEQ_GREEN, "good", "자신의 건강이 '매우 좋음' 또는 '좋음'이라고 답한 사람의 비율")]
    h_ignored = sorted({k[2] for k in ec.ignored if k[0] == "health"})
    for lid, ind, name, emoji, ramp, hi, defn in HL:
        add_county(lid, "daily", name, emoji, "%", "pct1", "linear", ramp, hi, "거주지 (표본조사)", "2025", "질병관리청 지역사회건강조사 (2025)",
                   f"{defn}. 연령표준화율. 네 지표를 하나의 종합 지수로 합치지 않는다. 시 단위로만 공표된 값은 소속 일반구 칸 전부에 칠한다. "
                   f"보건소 관할 구역으로 나눠 공표된 행({', '.join(h_ignored)})은 비율이라 합칠 수 없어 쓰지 않았고, 그 시의 시 전체 값도 없으면 자료 없음.",
                   umap_of("health", ind, additive=False))

    # 위험: 자연재난 피해액 ÷ 주민등록 인구
    dmg = umap_of("disaster_damage", "natural_disaster_damage")
    dmap = {}
    for k, v in dmg.items():
        p_, _ = pop.get(k, "2024")
        dmap[k] = None if v is None or not p_ else v * 1000 / p_
    n_zero = sum(1 for v in dmg.values() if v == 0)
    add_county("disaster", "risk", "자연재난 피해", "🌊", "원/명", "int", "log", SEQ_BLUE, "bad", "피해 발생지", "2024",
               "행정안전부 2024 재해연보 선공개(자연재난 피해·복구비), 주민등록 인구 2024-12",
               f"2024년 자연재난 총피해액(천원 → 원) ÷ 2024년 12월 주민등록 인구 = 1인당 원. 표에 있는 시군구 {len(dmg)}곳 가운데 피해액 0 으로 공표된 "
               f"{n_zero}곳은 0원이고, 표에 없는 시군구는 자료 없음(0 으로 넣지 않는다). 한 해 값이라 큰 재난 한 번에 크게 흔들린다.",
               dmap, nd=0)

    # 배움: 인구 천 명당 사설학원 수
    ac = umap_of("academies", "private_academies")
    amap = {}
    for k, v in ac.items():
        p_, _ = pop.get(k, "2025")
        amap[k] = None if v is None or not p_ else v / p_ * 1000
    add_county("academies", "learn", "사설학원", "📚", "곳/천명", "f2", "linear", SEQ_PURP, "neutral", "소재지", "2025",
               "KOSIS 지역통계 사설학원 수 (2025), 주민등록 인구 2025-12",
               "사설학원 수 ÷ 2025년 12월 주민등록 인구 × 1,000. 원표의 학원 수(원값)를 직접 나눴다(원표의 '천명당' 값은 쓰지 않음). 시 전체로만 공표된 값은 일반구에 같은 값.",
               amap, nd=2)

    keep = [l_ for l_ in lenses["lenses"] if l_["id"] not in {n["id"] for n in new_l}]
    lenses["lenses"] = keep + new_l
    if not any(g["id"] == "risk" for g in lenses["groups"]):
        lenses["groups"].append({"id": "risk", "name": "위험"})
    order = ["people", "age", "future", "living", "industry", "daily", "learn", "faith", "land", "risk"]
    lenses["groups"] = sorted(lenses["groups"], key=lambda g: order.index(g["id"]) if g["id"] in order else 99)
    lenses.setdefault("notes", [])
    note = ("5b·5c 렌즈: 숲·농경지·시가지·논 (칸)·밭 (칸)·침엽수림 비중은 칸 값(기후에너지환경부 세분류 토지피복지도 도엽 통계를 칸에 나눔, 도엽이 닿지 않는 칸은 ESA 대체 자료), "
            "초미세먼지는 측정소 거리 역가중, 나머지는 시군구 값을 칸에 펼친다. 토지피복 칸 값 렌즈는 육지 칸 값만 land_values 로 싣는다(world.cover_share.land_cells 순서).")
    lenses["notes"] = [n for n in lenses.get("notes", []) if not n.startswith("5b·5c 렌즈")]
    lenses["notes"] = [n for n in lenses["notes"] if not n.startswith("5b 렌즈: 숲·농경지·시가지는 칸 값(위성 피복)")]
    if note not in lenses["notes"]:
        lenses["notes"].append(note)
    lenses["coverage_5b"] = cover_log
    size = save_json(site("lenses.json"), lenses)
    log(f"렌즈 {len(new_l)}개 추가 {[l_['id'] for l_ in new_l]}, 값이 있는 육지 칸 % {cover_log}, lenses.json {size / 1e6:.2f} MB")
    nation = load_json(site("nation.json"))
    cov = nation.get("econ", {}).get("coverage", {}).get("lens_land_coverage_pct")
    if cov is not None:
        cov.update(cover_log)
        save_json(site("nation.json"), nation)

    save_json(build("layers5b_audit.json"), {
        "power_failed": power["failed"], "nuclear_compare": nuc_cmp, "ports_flags": port_flags, "unmatched_cargo": unmatched_cargo,
        "gi_list_only": gi_list, "gi_sido": gi_sido, "parks_unmatched": park_unmatched, "roads": road_stats, "lens_coverage": cover_log,
        "health_ignored": h_ignored, "pm25_excluded": dict(st_excl)}, compact=False)


if __name__ == "__main__":
    sys.exit(main())

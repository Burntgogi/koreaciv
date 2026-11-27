"""5e — 돼지 시군구 값(2026)과 보훈대상자 렌즈 (명세 docs/SPEC_PHASE5E.md).

build_layers3.py(5d)가 만든 site/data/{resources,cities,states,lenses}.json 에 붙인다. 다시 돌려도 같은 결과가 나온다
(돼지 아이콘·규칙·패널 값, 렌즈, 도시·시도 값은 매번 통째로 바꿔 쓴다).

입력 (읽기만, 신뢰할 수 없는 입력으로 다룬다 — 칸 값은 데이터로만 쓰고 형식이 다르면 빌드 오류):
  data/raw/layers3/pig/15147317_pig_herd_by_county_2018_2026.csv + manifest.tsv
      가축위생방역지원본부 「전국 시군별 일반돼지 사육규모 현황」 (cp949)
  data/raw/layers3/veterans/1509857x.csv (17개) + manifest.tsv
      국가보훈부 「시도별 시군구별 보훈대상자 인원현황」 (cp949, 세종은 읍면동별)
manifest.tsv(데이터 번호, 제목, URL, sha256, 바이트)의 sha256·바이트가 파일과 다르면 빌드 오류.

이름 -> 현재 시군구 코드: lib/address.py(현재 이름표 + 옛 시도 이름) 와 lib/crosswalk.py(옛 코드 -> 현재 코드).
"""
import collections
import csv
import hashlib
import io
import os
import re
import sys

import numpy as np

from build_layers import World
from lib import crosswalk
from lib import econ as E
from lib import popstats
from lib.address import AddressResolver, nospace
from lib.common import RAW, build, load_json, raw, rnd, save_json, site

VERSION = "phase5e"
PIG_N = 15            # 돼지 아이콘: 상위 N (5b 와 같은 규칙)
PIG_DIR = raw("layers3", "pig")
VET_DIR = raw("layers3", "veterans")
PIG_COLS = ["순번", "품종", "시도", "시군", "년도", "전체호수", "전체두수"]
VET_COLS = ["연도", "분기", "시도", "시군구", "연번", "대상구분_상", "대상구분_하", "합계", "본인", "선순위유족"]
VET_DUP_NOTE = "원자료 설명대로 대상 사이에 중복이 있어 실제 인원보다 많을 수 있다."
PIG_NOTE = "일반돼지만 포함(종돈·흑돼지 등은 별도 자료라 빠짐), 방역 시스템 등록 농가 기준"


def log(*a):
    print("[layers5e]", *a, flush=True)


def read_manifest(d):
    """manifest.tsv (머리행 없음, 탭 5칸) -> [{no, title, url, sha256, bytes, file, path}]. 파일 sha256·바이트를 대조한다."""
    out = []
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(".csv"))
    with open(os.path.join(d, "manifest.tsv"), encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\r\n")
            if not ln.strip():
                continue
            p = ln.split("\t")
            if len(p) != 5 or not p[0].strip().isdigit():
                raise ValueError(f"{d}/manifest.tsv 행 형식이 다름: {ln[:80]!r}")
            no = p[0].strip()
            hit = [x for x in files if x.startswith(no)]
            if len(hit) != 1:
                raise ValueError(f"manifest 번호 {no} 에 맞는 파일이 {len(hit)}개")
            path = os.path.join(d, hit[0])
            with open(path, "rb") as fh:
                b = fh.read()
            sha = hashlib.sha256(b).hexdigest()
            if sha != p[3].strip() or len(b) != int(p[4]):
                raise ValueError(f"{hit[0]}: sha256/바이트가 manifest 와 다름")
            out.append({"no": no, "title": p[1].strip(), "url": p[2].strip(), "sha256": sha, "bytes": len(b), "file": hit[0], "path": path,
                        "data": b})
    if len(out) != len(files):
        raise ValueError(f"{d}: manifest {len(out)}행, CSV {len(files)}개")
    return out


def decode_csv(b, need):
    """바이트 -> (인코딩, 머리행, 행 목록). utf-8 이 아니면 cp949. 머리행이 need 로 시작하지 않으면 오류."""
    for enc in ("utf-8-sig", "cp949"):
        try:
            t = b.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("인코딩을 알 수 없음")
    rows = list(csv.reader(io.StringIO(t, newline="")))
    head = [h.strip() for h in rows[0]]
    if head[:len(need)] != need:
        raise ValueError(f"열이 다름: {head[:len(need)]}")
    return enc, head, [r for r in rows[1:] if any(x.strip() for x in r)]


def as_int(s, what):
    s = (s or "").replace(",", "").strip()
    if s == "":
        return None
    if not re.fullmatch(r"-?\d+", s):
        raise ValueError(f"{what}: 정수가 아님 {s!r}")
    return int(s)


def main():
    W = World()
    w = W.w
    cities = load_json(site("cities.json"))
    states = load_json(site("states.json"))
    nation = load_json(site("nation.json"))
    lenses = load_json(site("lenses.json"))
    resources = load_json(site("resources.json"))
    if resources.get("version") not in ("phase5d", VERSION):
        raise RuntimeError(f"resources.json 이 5d 결과가 아님 ({resources.get('version')}) — build_layers3.py 를 먼저 돌린다")
    dongs = load_json(build("dongs.json"))
    resolver = AddressResolver(w, cities)
    sido_name = {s["code"]: s["name"] for s in w["states"]}
    sido_short = {s["code"]: s["short"] for s in w["states"]}
    city_of_code = {s: c["id"] for c in cities for s in c["sgg"]}
    city_by_id = {c["id"]: c for c in cities}
    cur = set(W.codes)
    cidx = {c: k for k, c in enumerate(W.codes)}
    sido_codes = collections.defaultdict(list)
    for c in w["counties"]:
        sido_codes[c["sido"]].append(c["code"])

    # ---------- 시군구 단위 인구 가중 중심 칸 (5a–5d 와 같은 규칙) ----------
    _, _, f_emd, _ = popstats.latest_files()
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
            px, py = sum(i[0] * i[2] for i in items) / tw, sum(i[1] * i[2] for i in items) / tw
        else:
            px, py = W.centers[own].mean(0)
        k = int(own[np.argmin(((W.centers[own] - [px, py]) ** 2).sum(1))])
        center_cache[codes] = k
        return k

    def cnames(codes):
        return " · ".join(W.cname[c] for c in sorted(codes))

    def place_of(codes):
        codes = sorted(codes)
        sd = W.sido_of_code[codes[0]]
        if set(codes) == set(sido_codes[sd]) and len(codes) > 1:
            return sido_name[sd]
        cty = city_by_id.get(city_of_code.get(codes[0]))
        if cty and set(cty["sgg"]) == set(codes) and len(codes) > 1:
            return f"{sido_name[sd]} {cty['name']}"
        return f"{sido_name[sd]} {cnames(codes)}"

    def ukey(codes):
        return "+".join(sorted(codes))

    # =====================================================================
    # §2 돼지 (2026 시군별 전체두수)
    # =====================================================================
    pm = read_manifest(PIG_DIR)
    if len(pm) != 1:
        raise ValueError(f"돼지 manifest 가 {len(pm)}행")
    pm = pm[0]
    enc, head, prow = decode_csv(pm["data"], PIG_COLS)
    H = {h: k for k, h in enumerate(head)}
    years = sorted({r[H["년도"]].strip() for r in prow})
    ylatest = max(years, key=int)
    p26 = [r for r in prow if r[H["년도"]].strip() == ylatest]
    breeds = collections.Counter(r[H["품종"]].strip() for r in p26)
    if set(breeds) != {"일반"}:
        raise ValueError(f"돼지 원표 품종이 '일반' 말고도 있음: {dict(breeds)}")
    # 광역시 이름 행 = 그 광역시 전체. 광주는 옛 광주광역시(자치구 5개, crosswalk 29xxx -> 12xxx)
    METRO = {"부산": sido_codes["26"], "대구": sido_codes["27"], "인천": sido_codes["28"], "대전": sido_codes["30"],
             "울산": sido_codes["31"], "세종": sido_codes["36"],
             "광주": sorted(v for k, v in crosswalk.GWANGJU_JEONNAM.items() if k.startswith("29"))}
    pig_units, pig_meta, pig_unmatched, pig_blank_raw = {}, {}, [], []
    raw_total = 0
    for r in p26:
        sd_txt, sg_txt = r[H["시도"]].strip(), r[H["시군"]].strip()
        v = as_int(r[H["전체두수"]], f"돼지 {sd_txt} {sg_txt} 전체두수")
        farms = as_int(r[H["전체호수"]], f"돼지 {sd_txt} {sg_txt} 전체호수")
        if v is None:
            pig_blank_raw.append(f"{sd_txt} {sg_txt}")
        else:
            raw_total += v
        if sg_txt == sd_txt and sg_txt in METRO:
            codes, how = frozenset(METRO[sg_txt]), "metro"
        else:
            res = resolver.resolve(sg_txt, sido_hint=sd_txt)
            if res is None or (res.get("matched") or "") != nospace(sg_txt):
                pig_unmatched.append({"name": f"{sd_txt} {sg_txt}", "value": v})
                continue
            codes, how = res["codes"], ("city" if res["city_level"] else "sgg")
        if codes in pig_units:
            raise ValueError(f"돼지 원표에 같은 단위가 두 번: {sd_txt} {sg_txt}")
        if any(codes & k for k in pig_units):
            raise ValueError(f"돼지 원표 단위가 겹침: {sd_txt} {sg_txt}")
        pig_units[codes] = v
        pig_meta[codes] = {"raw": f"{sd_txt} {sg_txt}", "farms": farms, "how": how}
    unm_sum = sum(u["value"] or 0 for u in pig_unmatched)
    unit_sum = sum(v for v in pig_units.values() if v is not None)
    log(f"돼지 {ylatest}: 원표 {len(p26)}행 (인코딩 {enc}, 연도 {years[0]}–{years[-1]}), 단위 {len(pig_units)}, 대응 실패 {len(pig_unmatched)} "
        f"{[u['name'] for u in pig_unmatched]}; 단위 합 {unit_sum:,} + 대응 실패 {unm_sum:,} = {unit_sum + unm_sum:,} (원표 합 {raw_total:,}); 원표 빈 값 {pig_blank_raw}")
    if unit_sum + unm_sum != raw_total:
        raise ValueError("돼지 합이 원표 합과 다름")

    def item(kind, name, cell, precision, codes, **kw):
        codes = sorted(codes)
        sd = W.sido_of_code[codes[0]]
        same_city = all(city_of_code.get(c) == city_of_code.get(codes[0]) for c in codes)
        it = {"id": None, "kind": kind, "name": name, "cell": int(cell), "precision": precision, "sgg": codes, "sido": sd,
              "city": city_of_code.get(codes[0]) if same_city else None, "place": place_of(codes)}
        it.update(kw)
        return it

    ranked = sorted(((k, v) for k, v in pig_units.items() if v is not None), key=lambda kv: (-kv[1], ukey(kv[0])))
    PI = []
    for rk, (k, v) in enumerate(ranked[:PIG_N]):
        m = pig_meta[k]
        nm = place_of(k)
        short = nm.split(" ", 1)[1] if " " in nm else nm
        det = [f"{ylatest}년 일반돼지 {v:,}마리 · 사육 농가 {m['farms']:,}호" if m["farms"] is not None else f"{ylatest}년 일반돼지 {v:,}마리",
               f"원표 행: {m['raw']}" + (" (광역시 전체 한 행 — 자치구·군으로 나누지 않음)" if m["how"] == "metro" else
                                         " (시 전체 한 행 — 일반구로 나누지 않음)" if m["how"] == "city" else ""),
               f"가축위생방역지원본부 전국 시군별 일반돼지 사육규모 현황 — {PIG_NOTE}"]
        PI.append(item("pigs", f"돼지 · {short}", unit_center(k), "county", k, value=v, unit=f"마리 ({ylatest} 일반돼지)", year=ylatest,
                       source="layers3-pig", detail=det, rank=rk + 1))
    log(f"돼지 상위 {PIG_N}: {[(i['name'], i['value']) for i in PI]}")
    log(f"돼지 상위 10 단위: {[(place_of(k), v) for k, v in ranked[:10]]}")

    # 도시·시도 값
    metro_units = {k for k, m in pig_meta.items() if m["how"] == "metro"}
    by_city, metro_note = {}, {}
    for c in cities:
        v = E.agg(pig_units, c["sgg"])
        by_city[str(c["id"])] = v
        if v is None:
            mu = [k for k in metro_units if k & set(c["sgg"])]
            if mu:
                k = mu[0]
                metro_note[str(c["id"])] = {"value": pig_units[k], "scope": place_of(k) + (" 전체 (군 포함)" if any(W.cname[x].endswith("군") for x in k) else " 전체")}
    by_sido = {}
    for s in w["states"]:
        codes = set(sido_codes[s["code"]])
        parts = [v for k, v in pig_units.items() if k <= codes]
        by_sido[s["code"]] = {"sum": sum(v for v in parts if v is not None), "units": len(parts), "blank": sum(1 for v in parts if v is None)}
    farm = resources["farm"]
    P3 = farm.get("pigs_sido_2026") or {}
    cmp_rows = []
    for s in w["states"]:
        a_, b_ = by_sido[s["code"]]["sum"] if by_sido[s["code"]]["units"] else None, (P3.get("by_sido") or {}).get(s["code"])
        ratio = None if (a_ is None or not b_) else round(a_ / b_ - 1, 4)
        cmp_rows.append({"sido": s["code"], "county_sum": a_, "survey": b_, "diff_ratio": ratio})
    log("돼지 시도 합(방역본부 2026) vs 가축동향조사 2026년 3분기 (판정하지 않음): "
        + ", ".join(f"{sido_short[r['sido']]} {r['county_sum'] if r['county_sum'] is not None else '–'}/{r['survey'] if r['survey'] is not None else '–'}"
                    f"({'' if r['diff_ratio'] is None else f'{100 * r['diff_ratio']:+.1f}%'})" for r in cmp_rows))
    nat_a = sum(r["county_sum"] or 0 for r in cmp_rows)
    farm["pigs"] = {"by_city": by_city, "by_sido": by_sido, "year": ylatest, "unit": "마리", "label": "돼지 (일반돼지)",
                    "metro": metro_note, "units": {ukey(k): v for k, v in sorted(pig_units.items(), key=lambda kv: ukey(kv[0]))},
                    "unmatched": pig_unmatched, "raw_total": raw_total, "raw_rows": len(p26), "raw_blank": pig_blank_raw,
                    "note": PIG_NOTE, "sido_compare": cmp_rows,
                    "sido_compare_note": (f"방역본부 시군 값의 시도 합(전국 {nat_a:,}마리)과 가축동향조사 2026년 3분기 시도 값(전국 {P3.get('national') or 0:,}마리)은 "
                                          "조사 방법·기준 시점·대상(일반돼지만 / 전체 돼지)이 달라 차이를 판정하지 않고 비율만 적는다.")}
    pig_src = {"key": "layers3-pig", "title": pm["title"].split("_", 1)[1] if "_" in pm["title"] else pm["title"],
               "publisher": pm["title"].split("_", 1)[0], "retrieved": "", "file": f"layers3/pig/{pm['file']}", "license": "미확인", "url": pm["url"]}
    old_src = [s_ for s_ in resources["kinds"].get("pigs", {}).get("source", []) if s_.get("key") == "mtrace-pig-sido-2026q3"]
    metro_names = sorted(pig_meta[k]["raw"].split(" ")[1] for k in metro_units)
    resources["kinds"]["pigs"] = {
        "name": "돼지 (사육 상위)", "group": "farm", "count": len(PI), "placed": len(PI),
        "rule": (f"가축위생방역지원본부 「전국 시군별 일반돼지 사육규모 현황」 {ylatest}년 시군별 전체두수 상위 {PIG_N}곳(값이 있는 단위 {len(ranked)}곳 중)에 '돼지' 아이콘. "
                 f"기준 연도 {ylatest}. {PIG_NOTE}이라 가축동향조사의 전체 돼지 마릿수와 다르다. "
                 f"광역시는 원표에 시 전체 한 행({'·'.join(metro_names)})만 있어 그 광역시 전체(군 포함, 광주는 옛 광주광역시 자치구 5곳) 한 단위로 두고 자치구·군에 나누지 않는다. "
                 "일반구를 둔 시는 시 전체 한 행이라 시 전체 값. 원표에 행이 없는 시군은 자료 없음(0 이 아님). "
                 f"원표 {len(p26)}행 합 {raw_total:,}마리, 현재 시군구에 대응하지 못한 행 {len(pig_unmatched)}개. "
                 "5b 의 2019년 전국오염원조사 값을 대신한다. 시도 패널에는 시군 값의 시도 합과 함께 2026년 3분기 시도별 돼지(축산유통 통계누리 가축동향조사)를 따로 싣는다 "
                 "(조사가 달라 값이 다르다)."),
        "source": [pig_src] + old_src, "year": ylatest, "missing": [{"name": u["name"], "reason": "현재 시군구 이름표에 없음"} for u in pig_unmatched],
        "precision_note": "county"}
    if "cattle" in resources["kinds"]:
        resources["kinds"]["cattle"]["rule"] = resources["kinds"]["cattle"]["rule"].replace(
            "돼지는 시군구 값이 2019년(전국오염원조사)뿐이라 그대로 두고, 시도 패널에 2026년 3분기 시도별 돼지(가축동향조사)를 싣는다.",
            f"돼지는 5e 부터 {ylatest}년 가축위생방역지원본부 시군 값이다.")
    resources["unavailable"] = [u for u in resources.get("unavailable", []) if "돼지" not in u["name"]]
    resources["items"] = [i for i in resources["items"] if i["kind"] != "pigs"]
    for k, it in enumerate(PI):
        it["id"] = f"r5e-{k}"
    resources["items"] += PI
    resources["version"] = VERSION
    resources["precision_counts"] = dict(collections.Counter(i["precision"] for i in resources["items"]))

    # =====================================================================
    # §3 보훈대상자
    # =====================================================================
    vm = read_manifest(VET_DIR)
    state_by_name = {s["name"]: s["code"] for s in w["states"]}
    vfiles = []
    for e in vm:
        enc, head, rows = decode_csv(e["data"], VET_COLS)
        H = {h: k for k, h in enumerate(head)}
        periods = sorted({(as_int(r[H["연도"]], "연도"), as_int(r[H["분기"]], "분기")) for r in rows})
        last = periods[-1]
        lr = [r for r in rows if (as_int(r[H["연도"]], "연도"), as_int(r[H["분기"]], "분기")) == last]
        sds = {r[H["시도"]].strip() for r in lr}
        if len(sds) != 1:
            raise ValueError(f"{e['file']}: 최신 분기의 시도가 하나가 아님 {sds}")
        sd_txt = sds.pop()
        sd, rest = resolver.sido_of(sd_txt)
        if sd is None or rest:
            raise ValueError(f"{e['file']}: 시도 이름을 모름 {sd_txt}")
        by_name = collections.OrderedDict()
        cats = collections.defaultdict(set)
        blocks = collections.defaultdict(list)   # 이름 -> [묶음 합] (같은 이름 아래 대상구분 41개가 되풀이되면 묶음이 둘 이상)
        sum_mismatch = 0
        for r in lr:
            nm = r[H["시군구"]].strip()
            v = as_int(r[H["합계"]], f"{e['file']} {nm} 합계")
            a_, b_ = as_int(r[H["본인"]], "본인"), as_int(r[H["선순위유족"]], "선순위유족")
            if v is None:
                raise ValueError(f"{e['file']} {nm}: 합계 빈칸")
            if a_ is not None and b_ is not None and a_ + b_ != v:
                sum_mismatch += 1
            key = (r[H["대상구분_상"]].strip(), r[H["대상구분_하"]].strip())
            if key in cats[nm] or not blocks[nm]:
                blocks[nm].append(0)
                cats[nm] = set()
            cats[nm].add(key)
            blocks[nm][-1] += v
            by_name[nm] = by_name.get(nm, 0) + v
        uppers = list(dict.fromkeys(r[H["대상구분_상"]].strip() for r in lr))
        vfiles.append({"m": e, "enc": enc, "sido_txt": sd_txt, "uppers": uppers, "sido": sd, "period": last, "periods": len(periods), "by_name": by_name,
                       "blocks": {k: v for k, v in blocks.items() if len(v) > 1},
                       "ncat": sorted({len(v) for v in cats.values()}), "sum_mismatch": sum_mismatch,
                       "home": state_by_name.get(sd_txt) == sd})
    single = {sd: cs[0] for sd, cs in sido_codes.items() if len(cs) == 1}
    TAG_OK = re.compile(r"^(.*?)\s*\(([^()]+)\)$")

    def classify(f, nm):
        """-> ('total', None) | ('sgg', codes, 설명) | ('none', None, 이유)"""
        n0 = nospace(nm)
        if n0 == nospace(f["sido_txt"]) or "합계" in n0:
            return ("total", None, "")
        if f["sido"] in single:
            return ("sgg", frozenset([single[f["sido"]]]), "단층 시도의 읍면동 행")
        base, tag, note = nm, None, ""
        m = TAG_OK.match(nm)
        if m:
            base, tag = m.group(1), m.group(2).strip()
            if tag == "구":
                note = "옛 구역 표기 '(구)'"
            else:
                tsd, trest = resolver.sido_of(tag)
                if tsd != f["sido"]:
                    return ("none", None, f"괄호 속 시도 표기 '{tag}' 가 파일 시도와 다름")
        res = resolver.resolve(base, sido_hint=f["sido_txt"])
        if res is None or res["matched"] != nospace(base):
            return ("none", None, "현재 시군구 이름표·대응표에 없음")
        if f["sido"] == "28" and nospace(base) in ("중구", "동구", "서구"):
            note = f"인천 개편 전 {base} (대응표 {crosswalk.to_current({'중구': '28110', '동구': '28140', '서구': '28260'}[nospace(base)], cur)})"
        return ("sgg", res["codes"], note)

    # 파일별 시군구 행 -> 코드 집합
    assign = []   # (파일, 원표 이름, 코드 집합, 값, 설명)
    vet_unmatched, total_rows = [], {}
    for f in vfiles:
        rows_sum, tot = 0, 0
        for nm, v in f["by_name"].items():
            kind, codes, note = classify(f, nm)
            bl = f["blocks"].get(nm)
            if bl and kind != "total":
                raise ValueError(f"{f['m']['file']} {nm}: 시군구 이름 아래 대상구분 묶음이 {len(bl)}개")
            if kind == "total" and bl:
                # 시도 이름 아래 묶음이 둘 이상: 가장 큰 묶음이 합계 행, 나머지는 어느 시군구인지 이름으로 알 수 없는 행
                k_tot = max(range(len(bl)), key=lambda i: bl[i])
                tot += bl[k_tot]
                for i, b in enumerate(bl):
                    if i == k_tot:
                        continue
                    rows_sum += b
                    vet_unmatched.append({"file": f["m"]["no"], "sido": f["sido_txt"], "name": f"{nm} ({i + 1}번째 묶음)", "value": b,
                                          "reason": (f"시도 이름 행이 대상구분 41개씩 {len(bl)}묶음 — 큰 묶음({bl[k_tot]:,})을 합계 행으로 보고, 이 묶음은 이름이 시도 이름이라 "
                                                     "어느 시군구인지 원표로 정할 수 없어 시군구 값에 넣지 않음")})
                continue
            if kind == "total":
                tot += v
                continue
            rows_sum += v
            if kind == "none":
                vet_unmatched.append({"file": f["m"]["no"], "sido": f["sido_txt"], "name": nm, "value": v, "reason": note})
                continue
            assign.append((f, nm, codes, v, note))
        f["county_rows_sum"], f["total_row"] = rows_sum, tot
    # 같은 시군구가 두 파일에 나오면: 값이 같으면 하나, 다르면 소재 시도 파일(파일 시도 이름 = 현재 시도 이름)
    by_file_codes = collections.defaultdict(lambda: collections.defaultdict(int))
    for f, nm, codes, v, note in assign:
        for c in codes:
            by_file_codes[c][f["m"]["no"]] += 0
    fbyno = {f["m"]["no"]: f for f in vfiles}
    dup_report, drop_files_for_code = [], collections.defaultdict(set)
    for c, fs in by_file_codes.items():
        if len(fs) < 2:
            continue
        vals = {}
        for no in fs:
            vals[no] = sum(v for f, nm, codes, v, note in assign if f["m"]["no"] == no and c in codes)
        homes = [no for no in fs if fbyno[no]["home"] and fbyno[no]["sido"] == W.sido_of_code[c]]
        if len(homes) != 1:
            raise ValueError(f"{W.cname[c]}: 두 파일에 나오는데 소재 시도 파일을 정할 수 없음 {list(fs)}")
        keep = homes[0]
        same = len(set(vals.values())) == 1
        for no in fs:
            if no != keep:
                drop_files_for_code[c].add(no)
        dup_report.append({"code": c, "name": W.cname[c], "keep": keep, "keep_period": f"{fbyno[keep]['period'][0]}년 {fbyno[keep]['period'][1]}분기",
                           "values": {no: vals[no] for no in fs}, "same": same,
                           "periods": {no: f"{fbyno[no]['period'][0]}년 {fbyno[no]['period'][1]}분기" for no in fs}})
    assign2 = [(f, nm, codes, v, note) for f, nm, codes, v, note in assign if not any(f["m"]["no"] in drop_files_for_code[c] for c in codes)]
    dropped = [(f, nm, codes, v) for f, nm, codes, v, note in assign if any(f["m"]["no"] in drop_files_for_code[c] for c in codes)]
    dropped_files = sorted({f["m"]["no"] for f, *_ in dropped})
    # 한 코드짜리 행은 그 시군구에 더하고, 여러 코드 행은 그 코드에 따로 행이 없을 때만 한 단위(아니면 나눌 수 없어 '남는 옛 구역 행')
    single_val = collections.defaultdict(int)
    single_src = collections.defaultdict(list)
    for f, nm, codes, v, note in assign2:
        if len(codes) == 1:
            c = next(iter(codes))
            single_val[c] += v
            single_src[c].append((nm, v, note))
    multi_units, residual = {}, []
    for f, nm, codes, v, note in assign2:
        if len(codes) == 1:
            continue
        if any(c in single_val for c in codes) or any(codes & k and codes != k for k in multi_units):
            cid = {city_of_code[c] for c in codes}
            residual.append({"file": f["m"]["no"], "sido": W.sido_of_code[next(iter(codes))], "name": nm, "value": v, "codes": sorted(codes),
                             "city": cid.pop() if len(cid) == 1 else None, "reason": (note + " — " if note else "") + "현재 구 여럿으로 나뉘어 한 구에 넣을 수 없음"})
        else:
            multi_units[codes] = multi_units.get(codes, 0) + v
    units = {frozenset([c]): v for c, v in single_val.items()}
    units.update(multi_units)
    if any(a & b for a in units for b in units if a != b):
        raise ValueError("보훈 단위가 겹침")
    # 현재 구 행과 같은 구로 대응한 옛 구역 행 (인천 옛 동구 -> 제물포구). 세종 읍면동은 원래 여러 행이라 뺀다
    merged_old = {c: [(nm, v, note) for nm, v, note in lst if note] for c, lst in single_src.items()
                  if len(lst) > 1 and W.sido_of_code[c] not in single and any(note for _, _, note in lst)}
    # 인구 (주민등록 최신 월)
    pop = E.Population(cur)
    vet_unit = {}
    for k, v in units.items():
        p_, ym = pop.get(k, "2026")
        vet_unit[k] = (v, p_, (1000 * v / p_) if p_ else None)
    pop_ym = pop.latest_ym
    by_county = [None] * len(W.codes)
    for k, (v, p_, r_) in vet_unit.items():
        for c in k:
            by_county[cidx[c]] = rnd(r_, 2)
    have = sum(1 for x in by_county if x is not None)
    no_val = [W.codes[i] for i, x in enumerate(by_county) if x is None]
    # 시도 합계 행 대조
    sido_check = []
    for f in vfiles:
        used = f["m"]["no"] not in dropped_files
        sido_check.append({"file": f["m"]["no"], "sido_txt": f["sido_txt"], "period": f"{f['period'][0]}년 {f['period'][1]}분기",
                           "county_rows": f["county_rows_sum"], "total_row": f["total_row"], "diff": f["county_rows_sum"] - f["total_row"],
                           "used": used, "categories": f["ncat"], "sum_mismatch": f["sum_mismatch"]})
    raw_rows_used = sum(f["county_rows_sum"] for f in vfiles if f["m"]["no"] not in dropped_files)
    unit_total = sum(v for v, _, _ in vet_unit.values())
    res_total = sum(r_["value"] for r_ in residual)
    unm_total = sum(u["value"] for u in vet_unmatched if u["file"] not in dropped_files)
    log("보훈 파일별 기준 시점: " + ", ".join(f"{f['m']['no']} {f['sido_txt']} {f['period'][0]}Q{f['period'][1]}" for f in vfiles))
    log("보훈 시도 대조 (시군구 행 합 / 합계 행): " + "; ".join(
        f"{r_['sido_txt']} {r_['period']} {r_['county_rows']:,}/{r_['total_row']:,} (차 {r_['diff']:+,}){'' if r_['used'] else ' [중복 파일, 안 씀]'}" for r_ in sido_check))
    log(f"보훈 대상구분 행 수: {sorted({tuple(f['ncat']) for f in vfiles})}, 합계 ≠ 본인+선순위유족 행 {sum(f['sum_mismatch'] for f in vfiles)}")
    log(f"보훈 중복 시군구 {len(dup_report)}곳 (값이 다른 곳 {sum(1 for d in dup_report if not d['same'])}): "
        + ", ".join(f"{d['name']} {d['values']}→{d['keep']}" for d in dup_report[:40]))
    log(f"보훈 대응 실패 이름 {len(vet_unmatched)}: {[(u['sido'], u['name'], u['value'], u['reason']) for u in vet_unmatched]}")
    log(f"보훈 남는 옛 구역 행 {len(residual)}: {[(r_['name'], r_['value'], r_['codes']) for r_ in residual]}; 같은 구에 더한 옛 구역 행: "
        f"{ {W.cname[c]: v for c, v in merged_old.items()} }")
    log(f"보훈 시군구 값 합 {unit_total:,} + 남는 옛 구역 행 {res_total:,} + 대응 실패 {unm_total:,} = {unit_total + res_total + unm_total:,} "
        f"(원표 시군구 행 합, 중복 파일 제외 {raw_rows_used:,})")
    log(f"보훈 값이 있는 시군구 {have}/{len(W.codes)}, 값이 없는 시군구 {len(no_val)}: {[W.sido_of_code[c] + ' ' + W.cname[c] for c in no_val]}")
    if unit_total + res_total + unm_total != raw_rows_used:
        raise ValueError("보훈 합이 원표 시군구 행 합과 다름")

    # 렌즈
    N, land = W.N, W.land
    nl = int(land.sum())
    cells_v = [by_county[W.county[i]] for i in range(N) if land[i] and by_county[W.county[i]] is not None]
    cov = len(cells_v) / nl
    lo, hi = float(np.percentile(cells_v, 2)), float(np.percentile(cells_v, 98))
    per_file = collections.Counter(f"{f['period'][0]}년 {f['period'][1]}분기" for f in vfiles if f["m"]["no"] not in dropped_files)
    periods_txt = " · ".join(f"{k} {v}개 파일" for k, v in sorted(per_file.items()))
    dup_txt = ""
    if dropped_files:
        df = [fbyno[no] for no in dropped_files]
        keepers = sorted({d["keep"] for d in dup_report})
        dup_txt = (" " + ", ".join(f"{f['sido_txt']} 파일({f['period'][0]}년 {f['period'][1]}분기)" for f in df) + "은 "
                   + ", ".join(f"{fbyno[k]['sido_txt']} 파일({fbyno[k]['period'][0]}년 {fbyno[k]['period'][1]}분기)" for k in keepers)
                   + f"과 시군구 {len(dup_report)}곳이 겹쳐(값이 다른 곳 {sum(1 for d in dup_report if not d['same'])}곳) 소재 시도 파일의 값을 썼다.")
    res_txt = ""
    if residual:
        res_txt = (" 옛 구역 행(" + ", ".join(f"{sido_short[r_['sido']]} {r_['name']} {r_['value']:,}명" for r_ in residual)
                   + ")은 현재 구 여럿으로 나뉘어 시군구 값에 넣지 않고, 그 구들이 든 도시·시도 합에만 더했다.")
    mo_txt = ""
    if merged_old:
        mo_txt = " " + ", ".join(f"{', '.join(nm for nm, _, _ in lst)} 행은 대응표대로 {W.cname[c]}에 더했다" for c, lst in merged_old.items()) + "."
    nv_txt = ""
    if no_val:
        nv_txt = (" 값이 없는 시군구: " + ", ".join(f"{sido_short[W.sido_of_code[c]]} {W.cname[c]}" for c in no_val)
                  + "(그 시도 파일의 최신 분기에 행이 없음, 0 이 아님).")
    un_used = [u for u in vet_unmatched if u["file"] not in dropped_files]
    un_txt = ""
    if un_used:
        un_txt = (" 이름으로 시군구를 정할 수 없는 행: " + ", ".join(f"{u['sido']} '{u['name']}' {u['value']:,}명" for u in un_used)
                  + " — 시군구·도시 값에 넣지 않았다(0 이 아니라 대응 실패, 시도 합계 행에는 들어 있다).")
    sejong = [f for f in vfiles if f["sido"] in single]
    sj_txt = ""
    if sejong:
        f = sejong[0]
        sj_txt = (f" 세종은 읍면동 행의 합({f['county_rows_sum']:,}명, 시 합계 행 {f['total_row']:,}명"
                  + (" — 같다)." if f["county_rows_sum"] == f["total_row"] else f" — 차 {f['county_rows_sum'] - f['total_row']:+,})."))
    src_txt = f"국가보훈부 시도별 시군구별 보훈대상자 인원현황 ({periods_txt}), 주민등록 인구 {pop_ym}"
    lz = {"id": "veterans", "group": "people", "name": "보훈대상자", "emoji": "🎖️", "unit": "명/천 명", "format": "f1", "scale": "linear",
          "ramp": ["#fbf0e6", "#f3cfb3", "#e5a07c", "#cf6b55", "#a83d43", "#6e1f35"], "higher_is": "neutral",
          "basis": "보훈대상자 등록 주소지 (시군구)", "vintage": " · ".join(sorted(per_file)), "source": src_txt,
          "description": (f"보훈대상자 인원 ÷ {pop_ym} 주민등록 인구 × 1,000 (인구 천 명당 명). 인원 = 국가보훈부 「시도별 시군구별 보훈대상자 인원현황」에서 "
                          f"그 시군구의 대상구분 {'·'.join(str(x) for x in sorted({n for f in vfiles for n in f['ncat']}))}개 행(상위 구분 {len(vfiles[0]['uppers'])}개, 연감 참조) '합계'를 모두 더한 값. "
                          f"{VET_DUP_NOTE} 파일마다 가장 최신 분기({periods_txt}). 시도 합계 행은 뺐다."
                          + (f" 자료 없음(0 이 아님): {', '.join(sido_short[W.sido_of_code[c]] + ' ' + W.cname[c] for c in no_val)}." if no_val else "")
                          + " 겹친 파일·옛 구역 행·대응 실패는 연감 '렌즈 정의'의 원자료 대조."),
          "by_county": by_county, "coverage": round(cov, 4), "phase": "5e", "domain": [rnd(lo, 1), rnd(hi, 1)],
          "counts": {ukey(k): v for k, (v, _, _) in sorted(vet_unit.items(), key=lambda kv: ukey(kv[0]))},
          "audit": {"detail": f"파일마다 가장 최신 분기를 쓴다({periods_txt}). 시도 이름이거나 '합계'가 붙은 시도 합계 행은 시군구 값에서 뺐다.{sj_txt}{dup_txt}{res_txt}{mo_txt}{un_txt}{nv_txt}",
                    "pop_ym": pop_ym, "categories_upper": vfiles[0]["uppers"], "sido_check": sido_check, "duplicates": dup_report, "dropped_files": dropped_files,
                    "residual": residual, "unmatched": vet_unmatched, "no_value": no_val,
                    "merged_old": {c: [nm for nm, _, _ in lst] for c, lst in merged_old.items()},
                    "raw_county_rows": raw_rows_used, "unit_total": unit_total}}
    lenses["lenses"] = [l_ for l_ in lenses["lenses"] if l_["id"] != "veterans"] + [lz]
    note5e = "5e 렌즈: 보훈대상자는 국가보훈부 시군구 인원 ÷ 주민등록 인구 × 1,000, 시군구 값을 칸에 펼친다. 대상 사이 중복이 있어 실제 인원보다 많을 수 있다."
    lenses["notes"] = [n for n in lenses.get("notes", []) if not n.startswith("5e 렌즈")] + [note5e]
    log(f"렌즈 veterans: 값이 있는 육지 칸 {100 * cov:.1f}%, 색 범위 {lz['domain']}")
    rk = sorted(((W.sido_of_code[next(iter(k))], place_of(k), v, p_, r_) for k, (v, p_, r_) in vet_unit.items() if r_ is not None), key=lambda t: -t[4])
    log("보훈 천 명당 상위 5: " + ", ".join(f"{t[1]} {t[4]:.1f} ({t[2]:,}/{t[3]:,})" for t in rk[:5]))
    log("보훈 천 명당 하위 5: " + ", ".join(f"{t[1]} {t[4]:.1f} ({t[2]:,}/{t[3]:,})" for t in rk[-5:]))

    # 도시·시도 패널
    period_of_sido = {f["sido"]: f"{f['period'][0]}년 {f['period'][1]}분기" for f in vfiles if f["m"]["no"] not in dropped_files}
    for c in cities:
        sg = set(c["sgg"])
        v = E.agg({k: x[0] for k, x in vet_unit.items()}, sg)
        if v is None:
            miss = [W.cname[x] for x in sorted(sg) if by_county[cidx[x]] is None]
            c["veterans"] = {"count": None, "per_1000": None, "missing": miss, "period": period_of_sido.get(c["sido"])}
            continue
        rs = [r_ for r_ in residual if set(r_["codes"]) <= sg]
        tot = v + sum(r_["value"] for r_ in rs)
        p_, _ = pop.get(sg, "2026")
        c["veterans"] = {"count": tot, "per_1000": rnd(1000 * tot / p_, 2) if p_ else None, "period": period_of_sido.get(c["sido"]), "pop_ym": pop_ym}
        if rs:
            c["veterans"]["residual"] = [{"name": r_["name"], "value": r_["value"]} for r_ in rs]
    total_row_of = {f["sido"]: (f["total_row"], f"{f['period'][0]}년 {f['period'][1]}분기") for f in vfiles if f["m"]["no"] not in dropped_files}
    for s in states:
        codes = set(sido_codes[s["code"]])
        parts = [(k, x[0]) for k, x in vet_unit.items() if k <= codes]
        rs = [r_ for r_ in residual if set(r_["codes"]) <= codes]
        miss = [W.cname[x] for x in sorted(codes) if by_county[cidx[x]] is None]
        tot = sum(v for _, v in parts) + sum(r_["value"] for r_ in rs)
        p_, _ = pop.get(codes, "2026")
        tr = total_row_of.get(s["code"])
        s["veterans"] = {"count": tot, "complete": not miss, "missing": miss,
                         "per_1000": rnd(1000 * tot / p_, 2) if (p_ and not miss) else None, "period": period_of_sido.get(s["code"]), "pop_ym": pop_ym,
                         "sido_row": tr[0] if tr else None, "sido_row_per_1000": rnd(1000 * tr[0] / p_, 2) if (tr and p_) else None,
                         "residual": [{"name": r_["name"], "value": r_["value"]} for r_ in rs]}
    log("보훈 시도: " + ", ".join(f"{s['short']} {s['veterans']['count']:,}" + ("" if s["veterans"]["complete"] else f"(부분, {s['veterans']['missing']} 없음)")
                                 + f"/합계 행 {s['veterans']['sido_row']:,}" for s in states))
    nation["nation"]["veterans"] = {"count": sum(s["veterans"]["count"] for s in states), "period": lz["vintage"], "unmatched": unm_total,
                                    "sido_rows": sum(s["veterans"]["sido_row"] or 0 for s in states)}

    # =====================================================================
    # 저장
    # =====================================================================
    size = save_json(site("resources.json"), resources)
    log(f"resources.json {size / 1e3:.0f} KB, 아이콘 {len(resources['items'])}개")
    save_json(site("cities.json"), cities)
    save_json(site("states.json"), states)
    save_json(site("nation.json"), nation)
    size = save_json(site("lenses.json"), lenses)
    log(f"lenses.json {size / 1e3:.0f} KB")
    save_json(build("layers5e_audit.json"), {
        "pig": {"unmatched": pig_unmatched, "units": len(pig_units), "raw_total": raw_total, "top10": [(place_of(k), v) for k, v in ranked[:10]],
                "sido_compare": cmp_rows},
        "veterans": {"files": [{"no": f["m"]["no"], "sido": f["sido_txt"], "period": f["period"], "periods": f["periods"]} for f in vfiles],
                     "top5": [t[1:] for t in rk[:5]], "bottom5": [t[1:] for t in rk[-5:]], **lz["audit"]}}, compact=False)


if __name__ == "__main__":
    sys.exit(main())

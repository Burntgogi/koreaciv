"""전국·시도 공식값 (명세 5b §2.1): data/build/econ/official_totals.csv (읽기만).

행의 지역 이름(sido_now)을 현재 시도 코드로 옮긴다. 전남광주통합특별시(12)는 원표가 광주·전남을 따로 공표한 경우가 있어
'부분'(광주, 전남)으로 따로 두고, 더할 수 있는 값(금액·면적·인원)만 더해 '광주 + 전남 합'으로 쓴다. 비율은 더하지 않는다.
빈 값은 None 그대로 둔다 (0 으로 바꾸지 않는다).
"""
import collections
import csv
import os
import re

from .common import BUILD

PATH = os.path.join(BUILD, "econ", "official_totals.csv")

# 지역소득 33개 분류 (공백 제거) -> 표준 키. ('sub', 상위 키) 는 그 키의 세분, ('total', [구성 키]) 는 합계 분류.
# 표에 없는 이름이 나오면 빌드 오류.
GRDP33 = {
    "지역내총생산(시장가격)": "grdp", "순생산물세": "net_taxes", "총부가가치(기초가격)": "gva",
    "농업,임업및어업": "agriculture", "광업": "mining", "제조업": "manufacturing",
    "전기,가스,증기및공기조절공급업": "utilities", "건설업": "construction", "도매및소매업": "wholesale_retail",
    "운수및창고업": "transport", "숙박및음식점업": "accommodation", "정보통신업": "information",
    "금융및보험업": "finance", "부동산업": "real_estate", "사업서비스업": "business_services",
    "공공행정,국방및사회보장행정": "public_admin", "교육서비스업": "education", "보건업및사회복지서비스업": "health",
    "문화및기타서비스업": "culture_other",
    "광제조업": ("total", ["mining", "manufacturing"]),
    "서비스업": ("total", ["wholesale_retail", "transport", "accommodation", "information", "finance", "real_estate",
                        "business_services", "public_admin", "education", "health", "culture_other"]),
    "음식료품및담배제조업": ("sub", "manufacturing"), "섬유의복및가죽제품제조업": ("sub", "manufacturing"),
    "목재종이인쇄및복제업": ("sub", "manufacturing"), "석탄및석유화학제품제조업": ("sub", "manufacturing"),
    "비금속광물및금속제품제조업": ("sub", "manufacturing"), "전기전자및정밀기기제조업": ("sub", "manufacturing"),
    "기계운송장비및기타제품제조업": ("sub", "manufacturing"),
    "전문,과학및기술서비스업": ("sub", "business_services"), "사업시설관리,사업지원및임대서비스업": ("sub", "business_services"),
    # 시도 표의 '문화 및 기타서비스업'은 예술·협회와 함께 수도·하수·폐기물(E)을 품는다 (값으로 확인: 문화 = 예술 + 협회 + 수도)
    "수도,하수및폐기물처리,원료재생업": ("sub", "culture_other"), "예술,스포츠및여가관련서비스": ("sub", "culture_other"),
    "협회및단체,수리및기타개인서비스업": ("sub", "culture_other"),
}
# 전국사업체조사 대분류 이름 (괄호 속 산업코드 범위를 뗀 뒤) -> 문자
KSIC_OFFICIAL = {"전체산업": "total", "농업,임업및어업": "A", "광업": "B", "제조업": "C", "전기,가스,증기및공기조절공급업": "D",
                 "수도,하수및폐기물처리,원료재생업": "E", "건설업": "F", "도매및소매업": "G", "운수및창고업": "H",
                 "숙박및음식점업": "I", "정보통신업": "J", "금융및보험업": "K", "부동산업": "L", "전문,과학및기술서비스업": "M",
                 "사업시설관리,사업지원및임대서비스업": "N", "공공행정,국방및사회보장행정": "O", "교육서비스업": "P",
                 "보건업및사회복지서비스업": "Q", "예술,스포츠및여가관련서비스업": "R", "협회및단체,수리및기타개인서비스업": "S"}


def nospace(s):
    return re.sub(r"\s+", "", s or "")


def part_label(name):
    """'광주광역시'·'광주' -> '광주', '전라남도'·'전남' -> '전남' (시도 짧은 이름 규칙과 같다)."""
    n = nospace(name)
    m = re.fullmatch(r"(충청|전라|경상)(남|북)도", n)
    if m:
        return m.group(1)[0] + m.group(2)
    for suf in ("통합특별시", "특별자치시", "특별자치도", "특별시", "광역시", "도"):
        if n.endswith(suf) and len(n) > len(suf):
            return n[: -len(suf)]
    return n


def num(s):
    s = (s or "").replace(",", "").strip()
    return None if s == "" else float(s)


class Official:
    def __init__(self, world, resolver):
        self.states = {s["code"]: s for s in world["states"]}
        self.resolver = resolver
        with open(PATH, encoding="utf-8-sig", newline="") as f:
            self.rows = list(csv.DictReader(f))
        self.unknown = collections.Counter()
        self.raw_empty = sum(1 for r in self.rows if (r["value"] or "").strip() == "")
        for r in self.rows:
            r["_region"] = self.region(r)

    def region(self, r):
        """-> (시도 코드 또는 '00', 부분 이름 또는 None). 모르는 이름이면 None."""
        if nospace(r["sido_now"]) == "전국":
            return ("00", None)
        code, rest = self.resolver.sido_of(r["sido_now"])
        if code is None or rest:
            self.unknown[r["sido_now"]] += 1
            return None
        cur = nospace(self.states[code]["name"])
        part = None if nospace(r["sido_now"]) in (cur, self.states[code]["short"]) else part_label(r["sido_now"])
        return (code, part)

    def select(self, indicator, source=None):
        return [r for r in self.rows if r["indicator"] == indicator and (source is None or r["source_id"] == source)
                and r["_region"] is not None]

    # ---------- 지역소득 ----------
    def grdp(self):
        """-> {(지역 코드, 부분): {연도: {표준 키: 원}}}, 점검 결과"""
        out = collections.defaultdict(lambda: collections.defaultdict(dict))
        sub = collections.defaultdict(lambda: collections.defaultdict(lambda: collections.defaultdict(float)))
        tot = collections.defaultdict(dict)
        src = set()
        for r in self.select("grdp_current"):
            k = GRDP33.get(nospace(r["industry"]))
            if k is None:
                raise ValueError(f"지역소득 분류 대응표에 없는 이름: {r['industry']!r} (lib/official.py GRDP33)")
            if r["unit"] != "백만원":
                raise ValueError(f"지역소득 단위가 백만원이 아님: {r['unit']}")
            v = num(r["value"])
            v = None if v is None else v * 1e6
            key = r["_region"]
            src.add(r["source_id"])
            if isinstance(k, str):
                if k in out[key][r["year"]] and out[key][r["year"]][k] != v:
                    raise ValueError(f"같은 지역·연도·분류에 다른 값: {key} {r['year']} {k}")
                out[key][r["year"]][k] = v
            elif k[0] == "sub":
                sub[key][r["year"]][k[1]] += v if v is not None else float("nan")
            else:
                tot[(key, r["year"])][nospace(r["industry"])] = (k[1], v)
        # 점검: 세분 합 = 상위, 합계 분류 = 구성 합, 16 산업 + 순생산물세 = GRDP (±0.5%)
        from .econ import INDUSTRY_KEYS
        bad = []
        n = 0
        for key, ys in out.items():
            for y, d in ys.items():
                n += 1
                for parent, s in sub[key][y].items():
                    if d.get(parent) and abs(s / d[parent] - 1) > 0.005:
                        bad.append(f"{key} {y} {parent} 세분 합 {s:,.0f} != {d[parent]:,.0f}")
                for nm, (comp, v) in tot.get((key, y), {}).items():
                    s = sum(d[c] for c in comp)
                    if v and abs(s / v - 1) > 0.005:
                        bad.append(f"{key} {y} {nm} {v:,.0f} != 구성 합 {s:,.0f}")
                if all(d.get(k) is not None for k in INDUSTRY_KEYS + ["net_taxes", "grdp"]):
                    s = sum(d[k] for k in INDUSTRY_KEYS) + d["net_taxes"]
                    if abs(s / d["grdp"] - 1) > 0.005:
                        bad.append(f"{key} {y} 16 산업 + 순생산물세 {s:,.0f} != GRDP {d['grdp']:,.0f}")
        return out, {"checked": n, "bad": bad, "sources": sorted(src)}

    # ---------- 종사자 ----------
    def jobs(self):
        out = collections.defaultdict(lambda: collections.defaultdict(dict))
        for r in self.select("establishment_workers"):
            nm = re.sub(r"\([^()]*\)$", "", nospace(r["industry"]))
            L = KSIC_OFFICIAL.get(nm)
            if L is None:
                raise ValueError(f"사업체조사 대분류 이름을 모름: {r['industry']!r} (lib/official.py KSIC_OFFICIAL)")
            v = num(r["value"])
            out[r["_region"]][r["year"]][L] = None if v is None else int(v)
        return out

    # ---------- 고용률·실업률 (월) ----------
    def employment(self):
        """-> {지역: {'YYYY-MM': {'rate':, 'unemployment':}}}"""
        out = collections.defaultdict(lambda: collections.defaultdict(dict))
        survey = set()
        for ind, k in (("employment_rate", "rate"), ("unemployment_rate", "unemployment")):
            for r in self.select(ind):
                m = re.search(r"M(\d{4})(\d{2})$", r["basis"])
                if not m:
                    raise ValueError(f"고용 행의 기준 월을 읽지 못함: {r['basis']!r}")
                survey.add(r["basis"].split("·")[1] if "·" in r["basis"] else r["basis"])
                out[r["_region"]][f"{m.group(1)}-{m.group(2)}"][k] = num(r["value"])
        return out, sorted(survey)

    def fiscal(self):
        out = collections.defaultdict(dict)
        for ind, k in (("fiscal_independence", "avg"), ("fiscal_independence_headquarters", "hq")):
            for r in self.select(ind):
                out[r["_region"]][k] = num(r["value"])
                out[r["_region"]]["year"] = int(r["year"])
                out[r["_region"]].setdefault("basis", {})[k] = r["basis"]
        return out

    def farm(self):
        out = collections.defaultdict(dict)
        for ind, k in (("paddy_area", "paddy_ha"), ("upland_area", "field_ha"), ("cultivated_area", "cultivated_ha")):
            for r in self.select(ind):
                v = num(r["value"])
                out[r["_region"]][k] = None if v is None else v
                out[r["_region"]]["year"] = int(r["year"])
        return out

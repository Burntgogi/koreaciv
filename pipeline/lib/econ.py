"""경제 정리표(data/build/econ/*.csv, 읽기만) 읽기와 지역 단위 맞추기.

정리표 한 행은 다음 중 하나로 현재 시군구 코드 집합('단위')에 붙는다.
  - sgg_code_now 가 현재 코드      -> {그 코드}
  - sgg_code_now 가 비었고 이름이 일반구를 둔 시(수원시·창원시 …) -> 그 시의 일반구 전부 (시 값을 구에 나누지 않는다)
  - 인천의 개편 전 중구·동구·서구     -> 개편 후 구 묶음 (crosswalk.SPLITS)
  - 그 밖(폐지된 옛 군, 'OO군외' 같은 합친 항목, 시도 합계 행) -> 버리고 이유를 센다
빈 value 는 None(비공개·자료 없음)이다. 0 으로 바꾸지 않는다.
"""
import collections
import csv
import os
import re

from . import crosswalk, jumin, popstats
from .common import BUILD

ECON_DIR = os.path.join(BUILD, "econ")

# GRDP 산업 이름 -> 표준 키. 공백을 모두 지운 이름으로 찾는다. 없는 이름은 빌드 오류.
GRDP_INDUSTRY = {
    "농업,임업및어업": "agriculture", "농림어업": "agriculture",
    "광업": "mining",
    "제조업": "manufacturing",
    "전기,가스,증기및공기조절공급업": "utilities",
    "건설업": "construction",
    "도매및소매업": "wholesale_retail",
    "운수및창고업": "transport",
    "숙박및음식점업": "accommodation",
    "정보통신업": "information",
    "금융및보험업": "finance", "금융보험업": "finance",
    "부동산업": "real_estate",
    "사업서비스업": "business_services",
    "공공행정,국방및사회보장행정": "public_admin",
    "교육서비스업": "education",
    "보건업및사회복지서비스업": "health",
    "문화및기타서비스업": "culture_other",
    "순생산물세": "net_taxes",
    "총부가가치(기초가격)": "gva", "총부가가치": "gva",
    "지역내총생산(시장가격)": "grdp", "총생산액": "grdp",
}
INDUSTRY_KEYS = ["agriculture", "mining", "manufacturing", "utilities", "construction", "wholesale_retail",
                 "transport", "accommodation", "information", "finance", "real_estate", "business_services",
                 "public_admin", "education", "health", "culture_other"]
INDUSTRY_KO = {"agriculture": "농림어업", "mining": "광업", "manufacturing": "제조업", "utilities": "전기·가스·증기",
               "construction": "건설업", "wholesale_retail": "도소매업", "transport": "운수·창고업",
               "accommodation": "숙박·음식점업", "information": "정보통신업", "finance": "금융·보험업",
               "real_estate": "부동산업", "business_services": "사업서비스업", "public_admin": "공공행정·국방",
               "education": "교육서비스업", "health": "보건·사회복지", "culture_other": "문화·기타서비스업",
               "net_taxes": "순생산물세", "gva": "총부가가치", "grdp": "지역내총생산"}
# 한국표준산업분류 대분류. 정리표 이름은 대부분 맨 앞 문자(A~S)로 판별하고,
# 문자 없이 대분류 표제만 적은 출처(서울 데이터 허브)는 아래 표제표로 판별한다. 둘 다 아니면 빌드 오류.
KSIC = "ABCDEFGHIJKLMNOPQRS"
KSIC_KO = {"A": "농림어업", "B": "광업", "C": "제조업", "D": "전기·가스", "E": "수도·폐기물", "F": "건설업",
           "G": "도소매업", "H": "운수·창고업", "I": "숙박·음식점업", "J": "정보통신업", "K": "금융·보험업",
           "L": "부동산업", "M": "전문·과학·기술", "N": "사업시설관리·임대", "O": "공공행정·국방", "P": "교육서비스업",
           "Q": "보건·사회복지", "R": "예술·스포츠·여가", "S": "협회·수리·개인서비스"}
KSIC_TITLE = {"농업,임업및어업": "A", "광업": "B", "제조업": "C", "전기,가스,증기및공기조절공급업": "D",
              "수도,하수및폐기물처리,원료재생업": "E", "건설업": "F", "도매및소매업": "G", "운수및창고업": "H",
              "숙박및음식점업": "I", "정보통신업": "J", "금융및보험업": "K", "부동산업": "L",
              "전문,과학및기술서비스업": "M", "사업시설관리,사업지원및임대서비스업": "N",
              "공공행정,국방및사회보장행정": "O", "교육서비스업": "P", "보건업및사회복지서비스업": "Q",
              "예술,스포츠및여가관련서비스업": "R", "협회및단체,수리및기타개인서비스업": "S"}


def ksic_letter(name):
    """'C 제조업', 'C 제조업(10~34)', 'C 제  조  업' -> 'C'. '합계' -> 'total'."""
    m = re.match(r"^\s*([A-Z])\s*[가-힣]", name or "")
    if m:
        if m.group(1) not in KSIC:
            raise ValueError(f"대분류 문자가 A~S 밖: {name!r}")
        return m.group(1)
    n = nospace(name)
    if n in ("합계", "전산업", "계"):
        return "total"
    if n in KSIC_TITLE:
        return KSIC_TITLE[n]
    raise ValueError(f"산업 대분류 문자가 없는 이름: {name!r} (lib/econ.py KSIC_TITLE 에도 없음)")


def covered(umap, target):
    """umap 의 단위들이 target 을 빈틈·걸침 없이 덮는가"""
    target = frozenset(target)
    cov = set()
    for k in umap:
        if k <= target:
            cov |= k
        elif k & target:
            return False
    return cov == target


INCHEON_OLD = {"중구": "28110", "동구": "28140", "서구": "28260"}


def nospace(s):
    return re.sub(r"\s+", "", s or "")


def grdp_key(name):
    k = GRDP_INDUSTRY.get(nospace(name))
    if k is None:
        raise ValueError(f"GRDP 산업 이름 대응표에 없음: {name!r} (lib/econ.py GRDP_INDUSTRY 에 추가)")
    return k


def num(s):
    s = (s or "").replace(",", "").strip()
    if s == "":
        return None
    return float(s)


class Econ:
    def __init__(self, world, cities):
        self.cur = {c["code"] for c in world["counties"]}
        self.sido_of_name = {s["name"]: s["code"] for s in world["states"]}
        self.sgg_sido = {c["code"]: c["sido"] for c in world["counties"]}
        # 일반구를 둔 시: (시도 코드, 시 이름) -> 일반구 코드 집합
        self.city_units = {}
        for c in cities:
            if len(c["sgg"]) > 1 and c["name"].endswith("시"):
                self.city_units[(c["sido"], c["name"])] = frozenset(c["sgg"])
        # 인천 개편 전 구: 옛 코드 -> 현재 코드 집합. 중구·동구는 같은 제물포구로 이어지므로 한 묶음
        self.old_units = {k: frozenset(crosswalk.SPLITS[v]) for k, v in INCHEON_OLD.items()}
        self.old_groups = [(("중구", "동구"), self.old_units["중구"] | self.old_units["동구"]),
                           (("서구",), self.old_units["서구"])]
        self.ignored = collections.Counter()
        self.conflicts = []
        self.tables = {}

    # ---------- 읽기 ----------
    def table(self, name):
        if name in self.tables:
            return self.tables[name]
        path = os.path.join(ECON_DIR, f"{name}.csv")
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
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
            out.append({"kind": kind, "key": key, "codes": codes, "year": r["year"], "raw": (r.get("sgg_code_raw") or "").strip(), "indicator": r["indicator"],
                        "industry": r["industry"], "value": num(r["value"]), "raw_empty": (r["value"] or "").strip() == "",
                        "unit": r.get("unit", ""), "basis": r.get("basis", ""), "source": r.get("source_id", "")})
        self.tables[name] = out
        return out

    def resolve(self, r):
        code = (r.get("sgg_code_now") or "").strip()
        if code in self.cur:
            return ("sgg", code, frozenset([code]))
        sido = self.sido_of_name.get(r.get("sido_now", ""))
        name = nospace(r.get("sgg_name_raw", ""))
        if sido is None:
            return None
        if sido == "28":
            nm = re.sub(r"^인천", "", name)
            if nm in self.old_units:
                return ("old", nm, self.old_units[nm])
        if (sido, name) in self.city_units:
            return ("city", name, self.city_units[(sido, name)])
        return None

    @staticmethod
    def raw_is_current(kind, raw, key, codes):
        """원자료 지역 코드가 현재 행정구역의 코드인가 (옛 남구 28170·옛 창원시 48110 같은 폐지 코드가 아닌가)"""
        if kind == "sgg":
            return raw == key
        if kind == "city":
            return len(raw) == 5 and any(c[:4] == raw[:4] for c in codes)
        return False

    # ---------- 단위 ----------
    def unit_map(self, rows, additive):
        """한 (지표, 산업, 연도) 행들 -> {코드 집합: 값}. 단위끼리 겹치지 않는다.
        같은 단위가 여러 행이면 첫 값을 쓰되 값이 다르면 오류. 값이 None 이면 그대로 None."""
        direct, cityv, oldv, rawof = {}, {}, {}, {}
        for r in rows:
            d = {"sgg": direct, "city": cityv, "old": oldv}[r["kind"]]
            k = (r["kind"], r["key"])
            if r["key"] in d and d[r["key"]][1] != r["value"]:
                prev = d[r["key"]][1]
                if prev is not None and r["value"] is not None and abs(prev - r["value"]) > 1e-9 * max(1, abs(prev)):
                    # 옛 코드(폐지·편입 전) 행과 현재 코드 행이 같은 단위로 겹치면 현재 코드 행을 쓴다
                    cur_now = self.raw_is_current(r["kind"], r["raw"], r["key"], r["codes"])
                    cur_prev = self.raw_is_current(r["kind"], rawof[k], r["key"], r["codes"])
                    if cur_now != cur_prev:
                        if cur_now:
                            self.conflicts.append((r["indicator"], r["year"], r["key"], rawof[k], prev, "→", r["raw"], r["value"]))
                            d[r["key"]] = (r["codes"], r["value"])
                            rawof[k] = r["raw"]
                        else:
                            self.conflicts.append((r["indicator"], r["year"], r["key"], r["raw"], r["value"], "버림", rawof[k], prev))
                        continue
                    raise ValueError(f"같은 단위·연도에 다른 값: {r['indicator']} {r['industry']} {r['year']} {r['key']} {prev} / {r['value']}")
                if prev is None:
                    d[r["key"]] = (r["codes"], r["value"])
                    rawof[k] = r["raw"]
                continue
            d[r["key"]] = (r["codes"], r["value"])
            rawof[k] = r["raw"]
        out, used = {}, set()
        for name, (codes, v) in cityv.items():
            if codes <= set(direct):
                continue  # 구별 값이 다 있으면 구별 값을 쓴다
            out[codes] = v
            used |= codes
        for names, codes in self.old_groups:
            if codes <= set(direct):
                continue
            if all(n in oldv for n in names):
                vals = [oldv[n][1] for n in names]
                if len(vals) == 1:
                    out[codes] = vals[0]
                elif additive:
                    out[codes] = None if any(v is None for v in vals) else sum(vals)
                else:
                    out[codes] = None  # 비율은 더할 수 없다
                used |= codes
        for code, (codes, v) in direct.items():
            if code in used:
                continue
            out[codes] = v
        return out

    def series(self, table, indicator, industry=None, additive=True, years=None):
        """-> {연도: unit_map}"""
        def ok(r):
            if r["indicator"] != indicator:
                return False
            if industry is None:
                return True
            return industry(r["industry"]) if callable(industry) else r["industry"] == industry

        rows = [r for r in self.table(table) if ok(r)]
        by = collections.defaultdict(list)
        for r in rows:
            by[r["year"]].append(r)
        return {y: self.unit_map(rs, additive) for y, rs in sorted(by.items()) if years is None or y in years}


def agg(umap, target):
    """target(코드 집합)을 정확히 덮는 단위들의 합. 덮지 못하거나 None 이 섞이면 None."""
    if not umap:
        return None
    target = frozenset(target)
    parts = [(k, v) for k, v in umap.items() if k <= target]
    covered = set()
    for k, _ in parts:
        covered |= k
    if covered != target:
        return None
    if any(k & target and not k <= target for k in umap):
        return None
    vals = [v for _, v in parts]
    if any(v is None for v in vals):
        return None
    return sum(vals)


def single(umap, target):
    """target 이 단위 하나와 정확히 같을 때의 값 (비율·중위값처럼 더할 수 없는 값)."""
    return umap.get(frozenset(target)) if umap else None


def unit_of(umap, code):
    for k in umap:
        if code in k:
            return k
    return None


class Population:
    """주민등록 인구: 연도(12월) 또는 최신 월. 단위(코드 집합)의 인구를 과거 코드 대응표로 맞춰 낸다."""

    def __init__(self, cur):
        self.cur = cur
        self.by_year = {}
        for y, path in popstats.year_files().items():
            _, recs = jumin.read(path)
            leaf, _ = jumin.leaf_sgg(recs)
            self.by_year[str(y)] = [(frozenset(crosswalk.to_current(r["code"][:5], cur)), r["total"]) for r in leaf]
        ym, f_sgg, _, _ = popstats.latest_files()
        _, recs = jumin.read(f_sgg)
        leaf, _ = jumin.leaf_sgg(recs)
        self.latest_ym = f"{ym[:4]}-{ym[4:]}"
        self.by_year[self.latest_ym] = [(frozenset([r["code"][:5]]), r["total"]) for r in leaf]

    def get(self, codes, year):
        """단위 인구. 그 해 인구 행이 단위를 정확히 덮지 못하면 None. 2026 처럼 12월 자료가 없는 해는 최신 월."""
        y = str(year)
        if y not in self.by_year:
            y = self.latest_ym if y >= self.latest_ym[:4] else None
        if y is None:
            return None, None
        codes = frozenset(codes)
        tot, cov = 0, set()
        for k, v in self.by_year[y]:
            if k <= codes:
                tot += v
                cov |= k
            elif k & codes:
                return None, y
        return (tot if cov == codes else None), y

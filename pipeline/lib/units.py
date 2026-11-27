"""공표 단위 기록 (감사 01): 시군구 렌즈의 값이 현재 시군구 하나가 아니라 더 큰 공표 단위의 값일 때 그 단위를 렌즈에 적는다.

정리표의 한 값이 현재 시군구 여럿에 같은 값으로 칠해지는 경우는 두 가지다.
  - 일반구를 둔 시가 시 전체로만 공표한 값 (수원시 → 장안·권선·팔달·영통구)          → '수원시 전체 값'
  - 개편(일반구 신설·인천 행정체제 개편) 전 단위의 값 (화성시 → 만세·효행·병점·동탄구) → '개편 전 화성시 전체 값'
값을 구마다 나누거나 새로 만들지 않는다. 화면(툴팁·패널·렌즈 설명)은 이 기록(lens.units)을 읽어 그대로 적는다.

개편 시점은 손으로 적지 않고 주민등록 시군구 표(12월 표와 최신 월 표)에 새 코드가 처음 나온 해로 정한다.
값의 연도가 그 해보다 앞이면 '개편 전'이다.
"""
import re

from . import crosswalk, jumin, popstats

_CACHE = {}


def _codes_by_year():
    if "years" not in _CACHE:
        files = {int(y): p for y, p in popstats.year_files().items()}
        ym, f_sgg, _, _ = popstats.latest_files()
        files.setdefault(int(ym[:4]), f_sgg)
        out, names = {}, {}
        for y, p in sorted(files.items()):
            _, recs = jumin.read(p)
            leaf, parents = jumin.leaf_sgg(recs)
            out[y] = {r["code"][:5] for r in leaf}
            for r in recs:
                c = r["code"]
                if c[5:] == "00000" and not jumin.is_sido(c) and not jumin.is_nation(c):
                    names.setdefault(c[:5], r["name"])
        _CACHE["years"] = out
        _CACHE["names"] = names
    return _CACHE["years"], _CACHE["names"]


def split_first_year():
    """나뉜 옛 코드 -> 새 코드가 모두 주민등록 표에 처음 나온 해 (없으면 None)."""
    if "first" not in _CACHE:
        years, _ = _codes_by_year()
        _CACHE["first"] = {old: min((y for y, cs in years.items() if set(new) <= cs), default=None)
                           for old, new in crosswalk.SPLITS.items()}
    return _CACHE["first"]


def year_of(v):
    """'2023 (세종 2024)', '2025 상반기', 2025 -> 2025. 연도가 없으면 None."""
    if v is None:
        return None
    m = re.search(r"(19|20)\d{2}", str(v))
    return int(m.group(0)) if m else None


class Namer:
    """코드 집합 -> 공표 단위 이름과 개편 여부."""

    def __init__(self, world, cities):
        self.codes = [c["code"] for c in world["counties"]]
        self.idx = {c: i for i, c in enumerate(self.codes)}
        self.cname = {c["code"]: c["name"] for c in world["counties"]}
        self.short = {s["code"]: s["short"] for s in world["states"]}
        self.city_of = {frozenset(c["sgg"]): c["name"] for c in cities if len(c["sgg"]) > 1}
        _, self.old_names = _codes_by_year()
        self.first = split_first_year()

    def _old_label(self, olds):
        nm = []
        for o in sorted(olds):
            full = self.old_names.get(o, o)
            last = full.split(" ")[-1]
            nm.append((o[:2], last))
        sd = {s for s, _ in nm}
        if all(n.endswith("구") for _, n in nm) and len(sd) == 1:
            # 자치구는 이름이 겹치므로 시도를 붙인다: '인천 중구·동구'
            prefix = self.short.get(next(iter(sd)), "")
            return f"{prefix} {'·'.join(n for _, n in nm)}".strip()
        return "·".join(n for _, n in nm)

    def describe(self, codes, year):
        """-> {name, reorg, published_as} 또는 None (코드 하나면)."""
        K = frozenset(codes)
        if len(K) < 2:
            return None
        olds = {o for o, new in crosswalk.SPLITS.items() if set(new) & K}
        cover = set()
        for o in olds:
            cover |= set(crosswalk.SPLITS[o])
        y = year_of(year)
        if olds and cover == K:
            fy = [self.first[o] for o in olds if self.first.get(o)]
            reorg = y is not None and bool(fy) and y < min(fy)
            name = self.city_of.get(K) or self._old_label(olds)
            return {"name": name, "reorg": reorg, "old_codes": sorted(olds), "split_year": min(fy) if fy else None}
        name = self.city_of.get(K)
        if name is None:
            name = "·".join(self.cname.get(c, c) for c in sorted(K))
        return {"name": name, "reorg": False, "old_codes": [], "split_year": None}


def label(d, year=None, suffix=""):
    """'개편 전 화성시 전체 값 (2025)' / '수원시 전체 값 (2025)'. suffix 가 있으면 연도 대신 그것을 붙인다."""
    base = f"개편 전 {d['name']} 전체 값" if d["reorg"] else f"{d['name']} 전체 값"
    if suffix:
        return base + suffix
    y = year_of(year)
    return base + (f" ({y})" if y else "")


def annotate(lens, entries, namer, suffix=""):
    """entries: [(코드 집합, 값의 연도)] — 값이 있는 단위만. 여러 시군구에 걸친 단위를 lens['units'] 에 적고
    한 문장 요약을 lens['units_note'] 에 둔다. 걸친 단위가 없으면 두 키를 지운다."""
    units = []
    seen = set()
    for codes, year in entries:
        K = frozenset(codes)
        if len(K) < 2 or K in seen:
            continue
        seen.add(K)
        d = namer.describe(K, year)
        ks = sorted(namer.idx[c] for c in K if c in namer.idx)
        units.append({"name": d["name"], "label": label(d, year, suffix), "reorg": d["reorg"], "year": year_of(year),
                      "counties": ks})
    lens.pop("units", None)
    lens.pop("units_note", None)
    if not units:
        return lens
    units.sort(key=lambda u: (not u["reorg"], u["counties"][0]))
    cn = lambda k: namer.cname[namer.codes[k]].split(" ")[-1]  # noqa: E731
    reorg = [u for u in units if u["reorg"]]
    whole = [u for u in units if not u["reorg"]]
    parts = []
    if reorg:
        parts.append("개편 전 단위로만 공표되어 새 구마다 같은 값을 칠한 곳: "
                     + "; ".join(f"{u['name']} ({u['year']}) → {'·'.join(cn(k) for k in u['counties'])}" for u in reorg))
    if whole:
        parts.append("시 전체로만 공표되어 일반구마다 같은 값을 칠한 곳: " + ", ".join(u["name"] for u in whole))
    lens["units"] = units
    lens["units_note"] = ". ".join(parts) + ". 구별 값을 새로 만들지 않았다 (툴팁에 공표 단위를 적는다)."
    return lens

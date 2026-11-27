"""주소(또는 '시도 + 시군구' 표기) -> 현재 시군구 코드 집합.

외부 지오코딩을 쓰지 않는다. 1단계의 현재 행정구역 이름표(world.json 의 states·counties)와 crosswalk 만 쓴다.

규칙
  1. 공백을 모두 지운 문자열 앞에서 시도 이름을 찾는다. 시도 이름은 현재 이름, 짧은 이름(world.states.short),
     '짧은 이름 + 시/도'(서울시·제주도 …), 옛 이름(강원도·전라북도·전라남도·광주광역시, 짧은 '전남'·'광주')을 쓴다.
     옛 이름은 crosswalk 규칙(강원·전북 특별자치도 출범, 광주·전남 통합)과 같은 대응이다.
  2. 시도 뒤에서 그 시도의 시군구 이름(공백 제거)을 길이가 긴 것부터 찾는다 ('수원시장안구' 가 '수원시' 보다 먼저).
  3. 일반구를 둔 시 이름만 있고 구가 없으면(예: '청주시 오창읍 …') 그 시의 일반구 전부를 한 단위로 돌려준다 (city_level).
  4. 인천의 개편 전 구(중구·동구·서구)는 crosswalk.SPLITS 로 나뉜 뒤의 구 묶음으로 돌려준다.
  5. 시군구가 하나뿐인 시도(세종)는 시도만 맞으면 그 시군구다.
  6. 어느 것도 맞지 않으면 None (호출한 쪽이 '주소 대응 실패'로 센다).
"""
import re

from . import crosswalk

INCHEON_OLD = {"중구": "28110", "동구": "28140", "서구": "28260"}
# 옛 시도 이름 -> 현재 시도 코드 (crosswalk 의 시도 단위 변경과 같은 대응)
OLD_SIDO = {"강원도": "51", "강원": "51", "전라북도": "52", "전북": "52", "전라남도": "12", "전남": "12",
            "광주광역시": "12", "광주": "12"}


def nospace(s):
    return re.sub(r"\s+", "", s or "")


class AddressResolver:
    def __init__(self, world, cities):
        self.states = {s["code"]: s for s in world["states"]}
        self.counties = world["counties"]
        self.cur = {c["code"] for c in self.counties}
        alias = {}
        for s in world["states"]:
            alias[nospace(s["name"])] = s["code"]
            alias[s["short"]] = s["code"]
            if s["name"].endswith("특별시") or s["name"].endswith("광역시") or s["name"].endswith("특별자치시"):
                alias[s["short"] + "시"] = s["code"]
            else:
                alias[s["short"] + "도"] = s["code"]
        for k, v in OLD_SIDO.items():
            alias.setdefault(k, v)
        self.alias = sorted(alias.items(), key=lambda kv: -len(kv[0]))
        # 시도별 시군구 이름 (공백 제거) -> 코드 집합
        self.names = {}
        for c in self.counties:
            self.names.setdefault(c["sido"], []).append((nospace(c["name"]), frozenset([c["code"]]), False))
        for c in cities:  # 일반구를 둔 시
            if len(c["sgg"]) > 1 and c["name"].endswith("시"):
                self.names.setdefault(c["sido"], []).append((nospace(c["name"]), frozenset(c["sgg"]), True))
        for nm, old in INCHEON_OLD.items():
            self.names.setdefault("28", []).append((nm, frozenset(crosswalk.to_current(old, self.cur)), False))
        for k in self.names:
            self.names[k].sort(key=lambda t: -len(t[0]))

    def sido_of(self, text):
        s = nospace(text)
        for a, code in self.alias:
            if s.startswith(a):
                return code, s[len(a):]
        return None, s

    def resolve(self, text, sido_hint=None):
        """-> dict(codes=frozenset, sido=코드, city_level=bool, matched=이름) 또는 None"""
        if sido_hint:
            sd, _ = self.sido_of(sido_hint)
            if sd is None:
                return None
            rest = nospace(text)
            # 시군 칸에 시도 이름이 다시 붙어 있으면 뗀다 (단 '제주시'처럼 시군구 이름이 시도 이름으로 시작하면 그대로)
            sd2, rest2 = self.sido_of(rest)
            if sd2 == sd and not any(rest.startswith(nm) for nm, _, _ in self.names.get(sd, [])):
                rest = rest2
        else:
            sd, rest = self.sido_of(text)
            if sd is None:
                return None
        cands = self.names.get(sd, [])
        for nm, codes, city in cands:
            if rest.startswith(nm):
                return {"codes": codes, "sido": sd, "city_level": city, "matched": nm}
        single = [c for c in self.counties if c["sido"] == sd]
        if len(single) == 1:
            return {"codes": frozenset([single[0]["code"]]), "sido": sd, "city_level": False, "matched": ""}
        return None

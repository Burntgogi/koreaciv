"""과거 시군구 코드(5자리, 행정안전부 행정기관코드 앞 5자리) -> 현재(2026-10-01 경계) 코드.

규칙 (2020-12 이후 변경):
  1. 강원특별자치도 출범 (2023-06-11): 42xxx -> 51xxx, 뒤 3자리 그대로
  2. 전북특별자치도 출범 (2024-01-18): 45xxx -> 52xxx, 뒤 3자리 그대로
  3. 군위군 대구 편입 (2023-07-01): 47720 경북 군위군 -> 27720 대구 군위군
  4. 부천시 일반구 설치 (2024-01-01): 41190 부천시 -> 원미·소사·오정구 (나뉨)
  5. 화성시 일반구 설치: 41590 화성시 -> 만세·효행·병점·동탄구 (나뉨)
  6. 인천 행정체제 개편: 28110 중구 -> 제물포구·영종구, 28140 동구 -> 제물포구, 28260 서구 -> 서해구·검단구 (나뉨)
  7. 전남광주통합특별시: 광주광역시 29xxx, 전라남도 46xxx -> 12xxx (아래 표)

나뉜 경우는 과거 인구를 새 구로 나눌 근거가 없으므로, 과거와 현재를 비교할 때 '비교 단위'(나뉜 구들의 묶음)로 묶어
비교한다. 대응표에 없는 과거 코드는 빌드 오류다.
"""

GWANGJU_JEONNAM = {
    # 광주광역시 자치구
    "29110": "12210", "29140": "12240", "29155": "12270", "29170": "12300", "29200": "12330",
    # 전라남도 시군
    "46110": "12110", "46130": "12130", "46150": "12150", "46170": "12170", "46230": "12190",
    "46710": "12710", "46720": "12720", "46730": "12730", "46770": "12740", "46780": "12750",
    "46790": "12760", "46800": "12770", "46810": "12780", "46820": "12790", "46830": "12800",
    "46840": "12810", "46860": "12820", "46870": "12830", "46880": "12840", "46890": "12850",
    "46900": "12860", "46910": "12870",
}

SPLITS = {
    "41190": ["41192", "41194", "41196"],
    "41590": ["41591", "41593", "41595", "41597"],
    "28110": ["28125", "28155"],
    "28140": ["28125"],
    "28260": ["28275", "28290"],
}

MOVES = {"47720": "27720"}


class CrosswalkError(Exception):
    pass


def to_current(code, current):
    """과거 코드 -> 현재 코드 목록. current: 현재 시군구 코드 집합."""
    if code in SPLITS:
        out = SPLITS[code]
    elif code in MOVES:
        out = [MOVES[code]]
    elif code in GWANGJU_JEONNAM:
        out = [GWANGJU_JEONNAM[code]]
    elif code[:2] == "42":
        out = ["51" + code[2:]]
    elif code[:2] == "45":
        out = ["52" + code[2:]]
    elif code in current:
        out = [code]
    else:
        raise CrosswalkError(f"대응표에 없는 과거 시군구 코드: {code}")
    bad = [c for c in out if c not in current]
    if bad:
        raise CrosswalkError(f"{code} -> {out}: 현재 코드에 없음 {bad}")
    return out


def check_names(old_name, new_names):
    """1:1 대응의 이름 확인: 시군구 이름(마지막 낱말)이 같아야 한다."""
    toks = old_name.split(" ")
    if len(toks) == 1:  # 세종특별자치시처럼 시도 아래 시군구 이름이 없는 단층 행
        return
    o = toks[-1]
    if len(new_names) == 1 and new_names[0].split(" ")[-1] != o:
        raise CrosswalkError(f"이름이 다른 1:1 대응: {old_name} -> {new_names[0]}")


def comparable_units(current, past_codes):
    """현재 코드를 '비교 단위'로 묶는다 (나뉜 구는 한 단위). -> {현재 코드: 단위 id(대표 코드)}"""
    parent = {c: c for c in current}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for pc in past_codes:
        outs = to_current(pc, current)
        for o in outs[1:]:
            ra, rb = find(outs[0]), find(o)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    # 서로 다른 과거 코드가 같은 현재 코드로 들어가면(중구·동구 -> 제물포구) 그 과거 코드들의 대상도 한 단위
    target_of = {}
    for pc in past_codes:
        for o in to_current(pc, current):
            target_of.setdefault(o, []).append(pc)
    for o, pcs in target_of.items():
        for pc in pcs:
            for o2 in to_current(pc, current):
                ra, rb = find(o), find(o2)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    return {c: find(c) for c in current}

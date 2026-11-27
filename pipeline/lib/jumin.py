"""주민등록 인구 CSV (jumin.mois.go.kr downloadCsvAge.do) 읽기.

원자료는 신뢰할 수 없는 입력으로 다룬다: 머리글 순서와 합계를 확인하고 어긋나면 오류를 낸다.
"""
import csv
import re

AGE_LABELS = [f"{a}~{a + 4}세" for a in range(0, 100, 5)] + ["100세 이상"]
AGE_MID = [a + 2.5 for a in range(0, 100, 5)] + [102.5]  # 계급 중간값 (100세 이상은 102.5 로 둔다)
NAME_RE = re.compile(r"^(.*?)\s*\((\d{10})\)$")


def _int(s):
    s = s.replace(",", "").strip()
    if not re.fullmatch(r"\d+", s):
        raise ValueError(f"숫자가 아님: {s!r}")
    return int(s)


def read(path):
    """-> (ym 'YYYY-MM', [rec]). rec = {name, code, total, male[21], female[21], ages[21]}"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    head = rows[0]
    m = re.match(r"(\d{4})년(\d{2})월_계_총인구수", head[1])
    if head[0] != "행정구역" or not m:
        raise ValueError(f"{path}: 머리글이 예상과 다름")
    ym = f"{m.group(1)}-{m.group(2)}"
    pre = f"{m.group(1)}년{m.group(2)}월_"
    idx = {}
    for sex in ("계", "남", "여"):
        idx[sex] = [head.index(pre + f"{sex}_{a}") for a in AGE_LABELS]
        idx[sex + "_tot"] = head.index(pre + f"{sex}_총인구수")
    out = []
    for r in rows[1:]:
        if not r or len(r) != len(head):
            if r:
                raise ValueError(f"{path}: 열 수가 다른 행 {r[:2]}")
            continue
        nm = NAME_RE.match(r[0].strip())
        if not nm:
            raise ValueError(f"{path}: 행정구역 칸 형식 {r[0]!r}")
        ages = [_int(r[i]) for i in idx["계"]]
        male = [_int(r[i]) for i in idx["남"]]
        female = [_int(r[i]) for i in idx["여"]]
        total = _int(r[idx["계_tot"]])
        if sum(ages) != total or any(a != b + c for a, b, c in zip(ages, male, female)):
            raise ValueError(f"{path}: 합계가 맞지 않는 행 {r[0]}")
        out.append({"name": re.sub(r"\s+", " ", nm.group(1)).strip(), "code": nm.group(2), "total": total,
                    "male": male, "female": female, "ages": ages})
    return ym, out


def is_nation(code):
    return code == "0000000000"


def is_sido(code):
    return code[2:] == "00000000" and code != "0000000000"


def leaf_sgg(recs):
    """시군구 행 중 '말단'만 고른다: 일반구가 있는 시의 상위 행(예: 수원시 4111000000)은 뺀다.
    읍면동 행(뒤 5자리가 0이 아님)도 뺀다. 세종처럼 시도 아래 같은 인구의 단일 행은 그대로 둔다."""
    sgg = [r for r in recs if not is_sido(r["code"]) and not is_nation(r["code"]) and r["code"][5:] == "00000"]
    tot = {r["code"][:5]: r["total"] for r in sgg}
    parents = set()
    for c in tot:
        # 상위 시: 끝자리가 0이고, 앞 4자리가 같은 다른 행들의 합이 자기 인구와 같다
        # (영동군 43740 과 증평군 43745 처럼 앞 4자리만 같은 별개 군을 상위 시로 오인하지 않게)
        kids = [o for o in tot if o[:4] == c[:4] and o != c]
        if c[4] == "0" and kids and sum(tot[k] for k in kids) == tot[c]:
            parents.add(c)
    return [r for r in sgg if r["code"][:5] not in parents], parents


def emd_rows(recs):
    return [r for r in recs if r["code"][5:] != "00000"]

"""국가 토지피복 통계(공공데이터포털 15163128, 공공누리 제1유형)로 시군구별 중분류 면적표를 만든다.

도시·시도·전국 패널의 '땅' 구역이 읽는 data/build/layers/landcover_stats_open.csv 를 쓴다.
열 구성은 예전 landcover_stats_sgg.csv(환경공간정보서비스 내려받기, 이용허락 미확인)와 같다.
기준년도가 가장 늦은 해의 '면적(㎡)' 행만 쓰고, 41개 세분류를 22개 중분류로 더한다(대응표는 collect_landcover_me.FINE_TO_MID).
"""
import csv
import io
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from collect_econ_normalize import FIELDS as STAT_FIELDS, Regions  # noqa: E402
from lib import crosswalk  # noqa: E402

ROOT = HERE.parent
SRC = ROOT / "data/raw/layers5/files/p2-15163128.csv"
OUT = ROOT / "data/build/layers/landcover_stats_open.csv"
SOURCE_ID = "data-15163128"

# collect_landcover_me 를 import 하면 네트워크용 패키지까지 읽으므로 대응표만 같은 내용으로 둔다(아래 check 에서 대조).
FINE_TO_MID = {
    "단독주거시설": "주거지역", "공동주거시설": "주거지역", "공업시설": "공업지역", "상업업무시설": "상업지역", "혼합지역": "상업지역",
    "문화체육휴양시설": "문화·체육·휴양지역", "공항": "교통지역", "항만": "교통지역", "철도": "교통지역", "도로": "교통지역",
    "기타교통통신시설": "교통지역", "환경기초시설": "공공시설지역", "교육행정시설": "공공시설지역", "기타공공시설": "공공시설지역",
    "경지정리가 된 논": "논", "경지정리가 안 된 논": "논", "경지정리가 된 밭": "밭", "경지정리가 안 된 밭": "밭",
    "시설재배지": "시설재배지", "과수원": "과수원", "목장양식장": "기타재배지", "기타재배지": "기타재배지",
    "활엽수림": "활엽수림", "침엽수림": "침엽수림", "혼효림": "혼효림", "자연초지": "자연초지",
    "골프장": "인공초지", "묘지": "인공초지", "기타초지": "인공초지", "내륙습지": "내륙습지", "갯벌": "연안습지", "염전": "연안습지",
    "해변": "자연나지", "강기슭": "자연나지", "암벽바위": "자연나지", "채광지역": "인공나지", "운동장": "인공나지", "기타나지": "인공나지",
    "하천": "내륙수", "호소": "내륙수", "해양수": "해양수",
}
NON_CLASS = {"지역구분", "기준년도", "데이터기준일", "지역명", "통계구분", "학습데이터활용면적", "녹지면적", "불투수면"}
SPLIT_RAW = {("인천광역시", "중구"), ("인천광역시", "동구"), ("인천광역시", "서구"), ("경기도", "화성시")}


def to_ha(m2):
    d = (m2 / Decimal("10000")).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    s = format(d, "f").rstrip("0").rstrip(".")
    return s or "0"


def main():
    rows = list(csv.DictReader(io.StringIO(SRC.read_text(encoding="utf-8-sig"))))
    cols = [c for c in rows[0].keys() if c not in NON_CLASS]
    if set(cols) != set(FINE_TO_MID):
        raise SystemExit(f"세분류 열이 대응표와 다름: {sorted(set(cols) ^ set(FINE_TO_MID))}")
    years = sorted({r["기준년도"] for r in rows})
    year = years[-1]
    use = [r for r in rows if r["기준년도"] == year and r["통계구분"].startswith("면적")]
    mids = sorted(set(FINE_TO_MID.values()))
    regions = Regions()
    out, n_sgg, n_split = [], 0, 0
    basis = f"{year[:4]} 기준·국가 토지피복 통계(세분류 41항목) 중분류 합산"
    for r in use:
        kind = r["지역구분"]
        if kind == "시도":
            continue
        if kind == "전국":
            name, sido_now, code = "전국", "전국", ""
        else:
            sido_raw, _, sgg_raw = r["지역명"].partition(" ")
            code, sido_now, _ = regions.resolve(sgg_raw, sido_raw)
            name = sgg_raw
            if code:
                if crosswalk.to_current(code, set(regions.by_code)) != [code]:
                    raise SystemExit(f"대응 이상: {r['지역명']} -> {code}")
                n_sgg += 1
            elif (sido_raw, sgg_raw) in SPLIT_RAW:
                code, n_split = "", n_split + 1
                sido_now = sido_now or sido_raw
            else:
                raise SystemExit(f"현재 시군구로 대응하지 못함: {r['지역명']}")
        vals = {c: Decimal(r[c] or "0") for c in cols}
        total = sum(vals.values())
        base = ["", name, code, sido_now, year[:4]]
        out.append(base + ["총합계", "", to_ha(total), "ha", basis, SOURCE_ID])
        for m in mids:
            out.append(base + [m, "", to_ha(sum(v for c, v in vals.items() if FINE_TO_MID[c] == m)), "ha", basis, SOURCE_ID])
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(STAT_FIELDS)
        w.writerows(out)
    print(f"[landstats] {OUT.name}: {len(out):,}행 · 기준 {year} · 전국 1 + 시군구 {n_sgg} + 개편 전 단위 {n_split}")


if __name__ == "__main__":
    main()

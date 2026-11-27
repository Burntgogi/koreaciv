"""주민등록 인구 추가 수집 (행정안전부 jumin.mois.go.kr, 키 불필요).

받는 것
  1. 읍면동 × 성별 × 5세 계급, 기준 월 (기본: 기존 시군구 파일과 같은 월) — 시군구마다 한 번
  2. 시군구 × 성별 × 5세 계급, 2020–2025년 각 12월 — 연도마다 시도별로 한 번
  3. 전국·시도 행 (위 각 시점) — 검증의 '원자료 전국 행'

방식은 collect_keyless.collect_jumin 과 같다: ageStatMonth.do 에서 세션 쿠키를 받고
downloadCsvAge.do 에 POST, 응답은 CP949. 요청 사이 0.4초 이상 쉬고 병렬로 보내지 않는다.
읍면동은 sltOrgType=2, sltOrgLvl1=시도 코드, sltOrgLvl2=시군구 코드 조합이다
(페이지의 selectHangkikcdListAjax.do 가 돌려주는 levels=2 목록의 hangkikcd).

기록은 data/raw/population/manifest.json 에 따로 남긴다 (data/raw/manifest.json 은 건드리지 않음).
실행:  python pipeline/collect_population.py [emd] [years] [--month YYYYMM]
"""
import datetime
import hashlib
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "raw", "population")
MANIFEST = os.path.join(OUT, "manifest.json")
BASE = "https://jumin.mois.go.kr"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"
PAUSE = 0.5  # 요청 사이 쉬는 시간 (명세: 0.4초 이상)
YEARS = range(2020, 2026)
ROW_RE = re.compile(r'^"([^"]*)\((\d{10})\)"((,"[\d,\-]*")+)$')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_manifest(m):
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1, sort_keys=True)


class Jumin:
    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.op.addheaders = [("User-Agent", UA), ("Referer", BASE + "/ageStatMonth.do")]
        self.last = 0.0
        self._open(BASE + "/ageStatMonth.do")

    def _open(self, url, body=None, tries=3):
        err = None
        for i in range(tries):
            wait = PAUSE - (time.monotonic() - self.last)
            if wait > 0:
                time.sleep(wait)
            try:
                with self.op.open(url, body, timeout=120) as r:
                    data = r.read()
                self.last = time.monotonic()
                return data
            except Exception as e:  # noqa: BLE001 - 재시도 후 마지막 오류를 올린다
                self.last = time.monotonic()
                err = e
                time.sleep(3 + 5 * i)
        raise err

    def locations(self):
        raw = self._open(BASE + "/selectHangkikcdListAjax.do", b"")
        locs = json.loads(raw.decode("utf-8"))["locations"]
        for loc in locs:  # 신뢰할 수 없는 응답: 형식을 확인한다
            if not re.fullmatch(r"\d{10}", str(loc.get("hangkikcd", ""))):
                raise ValueError(f"예상하지 못한 지역 코드: {loc!r}")
        return locs

    def csv(self, org_type, lvl1, lvl2, year, month):
        q = {"sltOrgType": org_type, "sltOrgLvl1": lvl1, "sltOrgLvl2": lvl2, "gender": "gender", "sum": "sum",
             "sltUndefType": "", "searchYearStart": year, "searchMonthStart": f"{month:02d}", "searchYearEnd": year,
             "searchMonthEnd": f"{month:02d}", "sltOrderType": "1", "sltOrderValue": "ASC", "sltArgTypes": "5",
             "sltArgTypeA": "0", "sltArgTypeB": "100", "category": "month", "nowYear": datetime.date.today().year,
             "searchYearMonth": "month", "xlsStats": "1"}
        raw = self._open(BASE + "/downloadCsvAge.do", urllib.parse.urlencode(q).encode())
        lines = [ln for ln in raw.decode("cp949", "replace").splitlines() if ln.strip()]
        if not lines or not lines[0].startswith('"행정구역"'):
            raise ValueError(f"CSV 머리글이 아님: {lines[:1]!r}")
        want = f"{year}년{month:02d}월_계_총인구수"
        if want not in lines[0]:
            raise ValueError(f"요청한 시점({year}-{month:02d})이 아닌 자료: {lines[0][:80]!r}")
        bad = [ln for ln in lines[1:] if not ROW_RE.match(ln)]
        if bad:
            raise ValueError(f"형식이 다른 행 {len(bad)}개: {bad[0][:80]!r}")
        return lines


def write(m, key, rel, lines, title, extra):
    data = ("\n".join(lines) + "\n").encode("utf-8-sig")
    path = os.path.join(OUT, rel)
    with open(path, "wb") as f:
        f.write(data)
    m[key] = {"title": title, "publisher": "행정안전부", "file": "population/" + rel,
              "url": BASE + "/ageStatMonth.do", "retrieved": now(),
              "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), **extra}
    save_manifest(m)
    print(f"  ok  {rel}  {len(lines) - 1} 행  {len(data):,} B")


def latest_month():
    """기존 시군구 파일(collect_keyless 가 받은 것)과 같은 월을 기본으로 쓴다."""
    names = sorted(n for n in os.listdir(OUT) if re.fullmatch(r"jumin_age5_sgg_\d{6}\.csv", n))
    ym = names[-1][-10:-4]
    return int(ym[:4]), int(ym[4:])


def collect_nation(j, m, year, month):
    lines = j.csv("1", "A", "A", year, month)
    write(m, f"jumin_age5_nation_{year}{month:02d}", f"jumin_age5_nation_{year}{month:02d}.csv", lines,
          f"주민등록 인구: 전국·시도 × 성별 × 5세 계급 ({year}-{month:02d})", {"vintage": f"{year}-{month:02d}"})
    return [c for c in re.findall(r"\((\d{10})\)", "\n".join(lines[1:])) if c != "0000000000"]


def collect_emd(j, m, year, month):
    collect_nation(j, m, year, month)
    locs = [loc for loc in j.locations() if loc["levels"] == "2"]
    sido = {loc["sidonm"]: loc["hangkikcd"] for loc in j.locations() if loc["levels"] == "1"}
    header, rows, failed = None, [], []
    for i, loc in enumerate(locs):
        lvl1 = sido.get(loc["sidonm"])
        try:
            lines = j.csv("2", lvl1, loc["hangkikcd"], year, month)
        except Exception as e:  # noqa: BLE001 - 한 시군구 실패가 전체를 막지 않게
            failed.append(f"{loc['sidonm']} {loc['sikunkunm']} ({loc['hangkikcd']}): {e}")
            print("  !!", failed[-1])
            continue
        header = header or lines[0]
        rows += lines[1:]
        if i % 20 == 0:
            print(f"  .. {i + 1}/{len(locs)} {loc['sidonm']} {loc['sikunkunm']}")
    if header is None:
        raise RuntimeError("읍면동 자료를 하나도 받지 못함")
    n_emd = sum(1 for r in rows if ROW_RE.match(r).group(2)[5:] != "00000")
    write(m, "jumin_age5_emd", f"jumin_age5_emd_{year}{month:02d}.csv", [header] + rows,
          f"주민등록 인구: 읍면동 × 성별 × 5세 계급 ({year}-{month:02d})",
          {"vintage": f"{year}-{month:02d}", "queries": len(locs), "failed": failed, "emd_rows": n_emd})
    return failed


def collect_years(j, m):
    failed = []
    for y in YEARS:
        codes = collect_nation(j, m, y, 12)
        header, rows = None, []
        for c in codes:
            try:
                lines = j.csv("2", c, "A", y, 12)
            except Exception as e:  # noqa: BLE001
                failed.append(f"{y}-12 {c}: {e}")
                print("  !!", failed[-1])
                continue
            header = header or lines[0]
            rows += lines[1:]
        write(m, f"jumin_age5_sgg_{y}12", f"jumin_age5_sgg_{y}12.csv", [header] + rows,
              f"주민등록 인구: 시군구 × 성별 × 5세 계급 ({y}-12)", {"vintage": f"{y}-12", "sido": len(codes)})
    return failed


if __name__ == "__main__":
    args = sys.argv[1:]
    year, month = latest_month()
    if "--month" in args:
        ym = args[args.index("--month") + 1]
        year, month = int(ym[:4]), int(ym[4:])
    groups = [a for a in args if a in ("emd", "years")] or ["emd", "years"]
    manifest = load_manifest()
    j = Jumin()
    problems = []
    for g in groups:
        print(f"[{g}]")
        try:
            problems += collect_emd(j, manifest, year, month) if g == "emd" else collect_years(j, manifest)
        except Exception as e:  # noqa: BLE001 - 막힌 묶음은 보고하고 다음으로
            problems.append(f"{g}: {e}")
            print("  !!", problems[-1])
    print(f"manifest: {len(manifest)} 건 -> {MANIFEST}")
    if problems:
        print("문제:", *problems, sep="\n  ")

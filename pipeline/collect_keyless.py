"""1단계 수집기: API 키 없이 받을 수 있는 공공데이터 원자료를 data/raw/ 에 저장한다.

표준 라이브러리만 사용. 실행:  python pipeline/collect_keyless.py [그룹 ...]
그룹: boundary terrain naturalearth heritage datagokr jumin   (생략하면 전부)

받은 파일마다 data/raw/manifest.json 에 출처·URL·수집시각·sha256·크기를 기록한다
(원본 usaciv 의 sources.json `files[]` 와 같은 구조).
"""
import datetime
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import netguard as NG  # noqa: E402  (감사 08·09: 허용 호스트·HTTPS·리디렉션·크기 상한·RAW 밖 경로)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
MANIFEST = os.path.join(RAW, "manifest.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

# data.go.kr 파일데이터 (로그인·키 불필요). (id, 폴더, 설명)
DATAGOKR = [
    ("15046076", "energy", "원자력안전위원회_국내 원자력발전소 현황"),
    ("15049846", "energy", "한국수자원공사_댐별 제원 정보"),
    ("15002610", "transport", "한국공항공사_공항별 여객실적"),
    ("15067652", "transport", "국가철도공단_철도역 정보"),
    ("15085874", "industry", "한국산업단지공단_전국산업단지현황통계_국가산업단지"),
    ("15085886", "industry", "한국산업단지공단_전국산업단지현황통계_일반"),
    ("15085881", "industry", "한국산업단지공단_전국산업단지현황통계_시도별현황"),
    ("3077829", "minerals", "한국광해광업공단_전국광산 통계 현황(금속광산)"),
    ("15067760", "minerals", "한국광해광업공단_전국광산 통계 현황(비금속광산)"),
    ("15067761", "minerals", "한국광해광업공단_전국광산 통계 현황(광종별 현황)"),
    ("15059868", "specialty", "해양수산부_어촌 어항 현황"),
    ("15143826", "population", "국가보훈부_국가보훈대상자 시군구별 인원현황"),
    ("15107577", "wonders", "국립공원공단_국립공원 시간별 일별 탐방객 통계"),
    ("15017313", "wonders", "국립공원공단_국립공원 공원경계"),
    ("15107994", "wonders", "국가유산청_한국의 유네스코 세계유산 정보"),
    ("15087524", "wonders", "국가유산청_세계유산 관람객 현황"),
]

# 아래는 data.go.kr 에서 '바로가기'(제공기관 사이트 연결)형이라 파일이 직접 내려오지 않는다.
# 제공기관 사이트·OpenAPI 로 받는다 (docs/DESIGN.md 의 출처표 참조). 주민등록 인구는 collect_jumin 이 대신 받는다.
    # ("15046119", "energy", "한국전력거래소_연도별 발전기별 발전설비"),
    # ("15092537", "transport", "국토교통부_공항별 항공통계"),
    # ("15050707", "transport", "해양수산부_화물처리실적통계(화물수송_총괄)"),
    # ("15050720", "transport", "해양수산부_항만별_선박입출항실적"),
    # ("15112762", "transport", "한국도로공사_고속도로 출입시설 위치정보"),
    # ("15045608", "transport", "한국도로공사_도로중심선_이정_좌표"),
    # ("3055334", "specialty", "국립농산물품질관리원_지리적표시 관리정보"),
    # ("15142047", "specialty", "국립수산물품질관리원_지리적표시 등록현황"),
    # ("3033304", "population", "행정안전부_지역별 연령별 주민등록 인구현황"),
    # ("3033301", "population", "행정안전부_지역별 주민등록 성별 인구현황"),
    # ("3033255", "population", "행정안전부_지역별 주민등록 인구 평균연령"),
    # ("3033295", "population", "행정안전부_지역별 주민등록 세대수 현황"),

NATURAL_EARTH = [
    "10m/physical/ne_10m_rivers_lake_centerlines.zip",
    "10m/physical/ne_10m_lakes.zip",
    "10m/cultural/ne_10m_roads.zip",
    "10m/cultural/ne_10m_railroads.zip",
    "10m/cultural/ne_10m_admin_0_countries.zip",
]

# 국가유산청 종목코드: 11 국보, 13 사적, 15 명승, 16 천연기념물
HERITAGE_KINDS = {"11": "국보", "13": "사적", "15": "명승", "16": "천연기념물"}

BBOX = (124.0, 33.0, 132.0, 39.0)  # 경도/위도: 독도·마라도·백령도 포함, 북쪽은 39°N 까지


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def load_manifest():
    if os.path.exists(MANIFEST):
        with open(MANIFEST, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_manifest(m):
    os.makedirs(RAW, exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=1, sort_keys=True)


def fetch(url, timeout=180, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            # 첫 주소와 모든 리디렉션을 허용 호스트·HTTPS 로 검사하고(평문 HTTP 로 내려가는 이동도 막음) 본문은 상한까지만
            _, body = NG.urllib_open(req, timeout=timeout)
            return body, {}
        except NG.GuardError:
            raise
        except Exception as e:  # noqa: BLE001 - 재시도 후 마지막 오류를 올린다
            last = e
            time.sleep(2 + 3 * i)
    raise last


def record(manifest, key, rel, data, url, title, publisher, extra=None):
    path = str(NG.check_path(RAW, rel))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    manifest[key] = {
        "title": title, "publisher": publisher, "file": rel.replace("\\", "/"), "url": url,
        "retrieved": now(), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
    }
    if extra:
        manifest[key].update(extra)
    save_manifest(manifest)
    print(f"  ok  {rel}  {len(data):,} B")


def safe_name(s):
    return re.sub(r'[\\/:*?"<>|\s]+', "_", s).strip("_")


def collect_boundary(m):
    api = "https://api.github.com/repos/vuski/admdongkor/contents/"
    dirs = sorted(d["name"] for d in json.loads(fetch(api)[0]) if d["name"].startswith("ver"))
    ver = dirs[-1]
    files = json.loads(fetch(api + ver)[0])
    for f in files:
        if f["name"].endswith(".geojson"):
            data, _ = fetch(f["download_url"], timeout=600)
            record(m, "boundary_admdong", os.path.join("boundary", f["name"]), data, f["download_url"],
                   f"행정동 경계 ({ver})", "행정안전부·통계청 자료 기반, vuski/admdongkor 정리본", {"vintage": ver})


def collect_terrain(m):
    w, s, e, n = BBOX
    url = ("https://coastwatch.pfeg.noaa.gov/erddap/griddap/srtm30plus_LonPM180.csv?"
           f"z%5B({s}):1:({n})%5D%5B({w}):1:({e})%5D")
    data, _ = fetch(url, timeout=900)
    record(m, "terrain_srtm30plus", os.path.join("terrain", "srtm30plus_korea.csv"), data, url,
           "SRTM30+ 표고·수심 (30 arc-sec, 약 0.9 km)", "Scripps / NOAA ERDDAP", {"bbox": BBOX})


def collect_naturalearth(m):
    for p in NATURAL_EARTH:
        url = "https://naciscdn.org/naturalearth/" + p
        data, _ = fetch(url, timeout=600)
        name = os.path.basename(p)
        record(m, "ne_" + name[:-4], os.path.join("naturalearth", name), data, url,
               "Natural Earth " + name[:-4], "Natural Earth")


def collect_heritage(m):
    for code, label in HERITAGE_KINDS.items():
        pages, page, total = [], 1, None
        while True:
            url = ("https://www.khs.go.kr/cha/SearchKindOpenapiList.do?"
                   f"pageUnit=500&pageIndex={page}&ccbaKdcd={code}&ccbaCncl=N")
            data, _ = fetch(url)
            text = data.decode("utf-8", "replace")
            if total is None:
                t = re.search(r"<totalCnt>(\d+)</totalCnt>", text)
                total = int(t.group(1)) if t else 0
            pages.append(text)
            if page * 500 >= total:
                break
            page += 1
        blob = "\n<!--page-->\n".join(pages).encode("utf-8")
        record(m, f"heritage_{code}", os.path.join("heritage", f"khs_{code}_{label}.xml"), blob,
               f"https://www.khs.go.kr/cha/SearchKindOpenapiList.do?ccbaKdcd={code}",
               f"국가유산 목록: {label}", "국가유산청", {"count": total})


def collect_datagokr(m):
    base = "https://www.data.go.kr"
    for pk, folder, title in DATAGOKR:
        try:
            page = fetch(f"{base}/data/{pk}/fileData.do")[0].decode("utf-8", "replace")
            d = re.search(r"fn_fileDataDown\('\d+',\s*'([^']+)'", page)
            if not d:
                print(f"  !!  {pk} {title}: 다운로드 버튼을 찾지 못함")
                continue
            org = re.search(r'"creator"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"', page)
            mod = re.search(r'"dateModified"\s*:\s*"([^"]+)"', page)
            q = urllib.parse.urlencode({"publicDataPk": pk, "publicDataDetailPk": d.group(1), "fileDetailSn": "1"})
            info = fetch(f"{base}/tcs/dss/selectFileDataDownload.do?{q}")[0].decode("utf-8", "replace")
            a = re.search(r'"atchFileId"\s*:\s*"([^"]+)"', info)
            if not a:
                print(f"  !!  {pk} {title}: atchFileId 없음")
                continue
            ext = re.search(r'"atchFileExtsn"\s*:\s*"([^"]+)"', info)
            url = f"{base}/cmm/cmm/fileDownload.do?atchFileId={a.group(1)}&fileDetailSn=1"
            data, hdr = fetch(url, timeout=600)
            ext = (ext.group(1) if ext else "bin").lower().lstrip(".")
            if data[:2] == b"PK" and ext not in ("zip", "xlsx", "docx", "hwpx"):
                ext = "zip"  # 확장자가 shp 로 표시돼도 실제로는 묶음 파일인 경우
            rel = os.path.join("datagokr", folder, f"{pk}_{safe_name(title)}.{ext}")
            record(m, f"datagokr_{pk}", rel, data, f"{base}/data/{pk}/fileData.do", title,
                   org.group(1) if org else title.split("_")[0], {"modified": mod.group(1) if mod else None})
        except Exception as e:  # noqa: BLE001 - 한 건 실패가 전체를 막지 않게
            print(f"  !!  {pk} {title}: {e}")
        time.sleep(0.5)


def collect_jumin(m, year=None, month=None):
    """행정안전부 주민등록 인구통계: 시도별로 시군구 × 성별 × 5세 계급 인구 (세션 쿠키만 필요, 키 불필요)."""
    import http.cookiejar
    today = datetime.date.today()
    if year is None:  # 전월 자료는 매월 초 공표되므로 두 달 전을 기본값으로 쓴다
        first = (today.replace(day=1) - datetime.timedelta(days=40)).replace(day=1)
        year, month = first.year, first.month
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders = [("User-Agent", UA), ("Referer", "https://jumin.mois.go.kr/ageStatMonth.do")]
    op.open("https://jumin.mois.go.kr/ageStatMonth.do", timeout=60).read()

    def pull(org_type, lvl1):
        q = {"sltOrgType": org_type, "sltOrgLvl1": lvl1, "sltOrgLvl2": "A", "gender": "gender", "sum": "sum",
             "sltUndefType": "", "searchYearStart": year, "searchMonthStart": f"{month:02d}", "searchYearEnd": year,
             "searchMonthEnd": f"{month:02d}", "sltOrderType": "1", "sltOrderValue": "ASC", "sltArgTypes": "5",
             "sltArgTypeA": "0", "sltArgTypeB": "100", "category": "month", "nowYear": today.year,
             "searchYearMonth": "month", "xlsStats": "1"}
        body = urllib.parse.urlencode(q).encode()
        return op.open("https://jumin.mois.go.kr/downloadCsvAge.do", body, timeout=120).read()

    nat = pull("1", "A")
    text = nat.decode("cp949", "replace")
    codes = [c for c in re.findall(r"\((\d{10})\)", text) if c != "0000000000"]
    rows = [text.splitlines()[0]]
    for c in codes:
        t = pull("2", c).decode("cp949", "replace").splitlines()
        rows += t[1:]
        time.sleep(0.4)
    blob = ("\n".join(rows) + "\n").encode("utf-8-sig")
    record(m, "jumin_age5_sgg", os.path.join("population", f"jumin_age5_sgg_{year}{month:02d}.csv"), blob,
           "https://jumin.mois.go.kr/ageStatMonth.do", f"주민등록 인구: 시군구 × 성별 × 5세 계급 ({year}-{month:02d})",
           "행정안전부", {"vintage": f"{year}-{month:02d}", "sido": len(codes), "rows": len(rows) - 1})


GROUPS = {"boundary": collect_boundary, "terrain": collect_terrain, "naturalearth": collect_naturalearth,
          "heritage": collect_heritage, "datagokr": collect_datagokr, "jumin": collect_jumin}

if __name__ == "__main__":
    manifest = load_manifest()
    for g in (sys.argv[1:] or list(GROUPS)):
        print(f"[{g}]")
        try:
            GROUPS[g](manifest)
        except Exception as e:  # noqa: BLE001
            print(f"  !!  {g}: {e}")
    print(f"manifest: {len(manifest)} 건 -> {MANIFEST}")

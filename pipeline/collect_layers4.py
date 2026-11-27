"""공식 출처 스냅샷 수집. 프로젝트 루트에서 python -I pipeline/collect_layers4.py 실행."""
import csv
import hashlib
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import netguard as NG  # noqa: E402  (감사 08: key 문자·RAW 밖 경로·허용 호스트·HTTPS·리디렉션·크기 상한)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/layers4"
RAW.mkdir(exist_ok=True, parents=True)
MANIFEST = RAW / "manifest.json"
SOURCES = json.loads((ROOT / "site/data/sources.json").read_text("utf8"))["sources"]
SESSION = NG.guarded_session_class(requests.Session)()
SESSION.headers["User-Agent"] = "Mozilla/5.0"
SESSION.max_bytes = 64 * 1024 * 1024     # 출처 쪽 스냅샷(HTML·약관 문서) 하나의 상한


def read_json(path, default):
    return json.loads(path.read_text("utf8")) if path.exists() else default


def save_json(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), "utf8")
    tmp.replace(path)


def collect(items):
    manifest = read_json(MANIFEST, {})
    failures = read_json(RAW / "failures.json", {})
    for name, url in items:
        try:
            # 출처 목록에서 온 이름·주소는 신뢰하지 않는다: 파일 이름 문자, RAW 아래 경로, 허용 호스트·HTTPS 를 먼저 본다
            NG.check_key(name)
            path = NG.check_path(RAW, name)
            NG.check_url(url)
        except NG.GuardError as err:
            failures[name] = dict(url=url, reason=f"안전장치: {err}")
            print(name, "막음", err, flush=True)
            save_json(RAW / "failures.json", failures)
            continue
        old = manifest.get(name, {})
        if old.get("url") == url and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == old.get("sha256"):
            continue
        try:
            time.sleep(1)
            # 리디렉션은 한 번씩 직접 따라가며 매번 허용 호스트·HTTPS 를 검사하고(6회까지), 본문은 상한까지만 읽는다
            resp, data = NG.fetch(SESSION, "GET", url, limit=SESSION.max_bytes, max_redirects=6, timeout=(6, 20))
            resp.raise_for_status()
            path.write_bytes(data)
            manifest[name] = dict(url=url, final_url=resp.url, retrieved=datetime.now(timezone.utc).isoformat(), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            save_json(MANIFEST, manifest)
            failures.pop(name, None)
            print(name, len(data), flush=True)
        except (requests.RequestException, NG.GuardError) as err:
            failures[name] = dict(url=url, reason=str(err))
            print(name, type(err).__name__, flush=True)
        save_json(RAW / "failures.json", failures)


def primary():
    yield "address-search.html", "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=" + quote("전국대학및전문대학정보표준데이터")
    yield "kosis-home.html", "https://kosis.kr/index/index.do"
    yield "jumin.html", "https://jumin.mois.go.kr/ageStatMonth.do"
    yield "molit.html", "https://rt.molit.go.kr/pt/xls/xls.do?mobileAt="
    yield "worldcover.html", "https://esa-worldcover.org/en/data-access"
    yield "naturalearth.html", "https://www.naturalearthdata.com/about/terms-of-use/"
    yield "osm.html", "https://www.openstreetmap.org/copyright/en"
    yield "boundary.html", "https://raw.githubusercontent.com/vuski/admdongkor/master/README.md"
    yield "terrain.html", "https://coastwatch.pfeg.noaa.gov/erddap/info/srtm30plus_LonPM180/index.html"
    for s in SOURCES:
        url = s.get("url") or ""
        if urlsplit(url).hostname == "www.data.go.kr":
            for n in re.findall(r"/data/(\d+)/", url) or [f["no"] for f in s.get("files", [])]:
                yield f"portal-{n}.html", f"https://www.data.go.kr/data/{n}/fileData.do"
        elif urlsplit(url).hostname not in {"raw.githubusercontent.com","naciscdn.org","esa-worldcover.org","download.geofabrik.de","kosis.kr","jumin.mois.go.kr","rt.molit.go.kr","coastwatch.pfeg.noaa.gov"} and url and not any(x in url for x in ["geoserver", "downloadExcel"]):
            try:
                yield NG.check_key(s["key"]) + ".html", NG.check_url(url.replace("http://www.khs.", "https://www.khs."))
            except NG.GuardError as err:
                print("출처 목록의 key·주소를 쓰지 않음:", err, flush=True)


@lru_cache(maxsize=12)
def soup(name):
    data = (RAW / name).read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return BeautifulSoup(data.decode(enc), "html.parser")
        except UnicodeDecodeError:
            pass
    return BeautifulSoup(data, "html.parser")


REVIEW_URLS = {
    "campuses.html": "https://www.data.go.kr/data/15107736/standard.do",
    "kosis-policy.html": "https://kosis.kr/serviceInfo/useGuide.do",
    "boundary-license.txt": "https://raw.githubusercontent.com/vuski/admdongkor/master/LICENSE-DATA",
    "naturalearth-readme.txt": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/README.md",
    "mois-policy.html": "https://www.mois.go.kr/frt/sub/a08/copyrightPolicy/screen.do",
    "address-export.csv": "https://www.data.go.kr/tcs/dss/stdFileDown.do?publicDataPk=15107736&file=csv&publicDataSj=%EC%A0%84%EA%B5%AD%EB%8C%80%ED%95%99%EB%B0%8F%EC%A0%84%EB%AC%B8%EB%8C%80%ED%95%99%EC%A0%95%EB%B3%B4%ED%91%9C%EC%A4%80%EB%8D%B0%EC%9D%B4%ED%84%B0",
    "campus-file-search.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%ED%95%9C%EA%B5%AD%EB%8C%80%ED%95%99%EA%B5%90%EC%9C%A1%ED%98%91%EC%9D%98%ED%9A%8C%20%EB%8C%80%ED%95%99%EB%B0%8F%EC%A0%84%EB%AC%B8%EB%8C%80%ED%95%99%EC%A0%95%EB%B3%B4",
    "jumin-portal.html": "https://www.data.go.kr/data/3033304/fileData.do",
    "copyright-act.html": "https://www.law.go.kr/법령/저작권법/제7조",
    "khs-policy.html": "https://www.khs.go.kr/html/HtmlPage.do?pg=/newHtml/policy/copyright.jsp&mn=NS_09_03",
    "policy-www-chungbuk-go-kr.html": "https://www.chungbuk.go.kr/www/contents.do?key=703",
    "policy-data-gg-go-kr.html": "https://data.gg.go.kr/portal/termsPolicyPage.do",
    "policy-www-jeju-go-kr.html": "https://www.jeju.go.kr/help/policy/copyright.htm",
    "policy-www-jeonnam-go-kr.html": "https://www.jeonnam.go.kr/contentsView.do?menuId=jeonnam0816000000",
    "policy-www-korea-kr.html": "https://www.korea.kr/guide/copyRight.do",
    "policy-www-keco-or-kr.html": "https://www.keco.or.kr/web/lay1/S1T6C1349/contents.do",
    "policy-www-forest-go-kr.html": "https://www.forest.go.kr/kfsweb/kfi/kfs/cms/cmsView.do?mn=NKFS_07_07&cmsId=FC_000367",
    "policy-www-knps-or-kr.html": "https://www.knps.or.kr/portal/main/contents.do?menuNo=8000186",
    "policy-www-lofin365-go-kr.html": "https://www.lofin365.go.kr/portal/LF9820000.do",
    "policy-www-mof-go-kr.html": "https://www.mof.go.kr/index.do?menuSeq=303",
    "policy-www-mois-go-kr.html": "https://www.mois.go.kr/frt/sub/a08/copyrightPolicy/screen.do",
    "policy-coast-mof-go-kr.html": "https://coast.mof.go.kr/coastNews/policy/copyright_policy.do",
    "policy-www-gb-go-kr.html": "https://www.gb.go.kr/Main/page.do?mnu_uid=6995&LARGE_CODE=720&MEDIUM_CODE=80&SMALL_CODE=50&",
    "policy-www-komir-or-kr.html": "https://www.komir.or.kr/kor/contents/1",
    "campus-download-js.txt": "https://www.data.go.kr/js/biz/mvc/std/std-download-manager.js",
    "farm-portal.html": "https://www.data.go.kr/data/3055334/fileData.do",
    "fishgi-portal.html": "https://www.data.go.kr/data/15142047/fileData.do",
    "airports-portal.html": "https://www.data.go.kr/data/15092537/fileData.do",
    "generators-portal.html": "https://www.data.go.kr/data/15046119/fileData.do",
    "ports-portal.html": "https://www.data.go.kr/data/15050720/fileData.do",
    "its-search.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EC%A0%84%EA%B5%AD%ED%91%9C%EC%A4%80%EB%85%B8%EB%93%9C%EB%A7%81%ED%81%AC",
    "khs-search.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EA%B5%AD%EA%B0%80%EC%9C%A0%EC%82%B0%20%EA%B8%B0%EB%B3%B8%EC%A0%95%EB%B3%B4%20%EA%B5%AD%EA%B0%80%EC%9C%A0%EC%82%B0%EC%B2%AD",
    "wamis-search.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%ED%95%98%EC%B2%9C%EC%9C%A0%EB%A1%9C%EC%84%A0",
    "keco-search.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EC%97%90%EC%96%B4%EC%BD%94%EB%A6%AC%EC%95%84%20%EC%B8%A1%EC%A0%95%EC%86%8C%20%EC%A0%95%EB%B3%B4",
    "research-search.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EB%8C%80%ED%95%99%20%EC%97%B0%EA%B5%AC%EB%B9%84%20%EC%88%98%ED%98%9C%20%EC%8B%A4%EC%A0%81",
    "mcee-search.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%ED%86%A0%EC%A7%80%ED%94%BC%EB%B3%B5%EC%A7%80%EB%8F%84%20%EC%A4%91%EB%B6%84%EB%A5%98",
    "campus-header.json": "https://www.data.go.kr/download/columList.json?pk=15107736&ext=JSON",
    "copyright-text.html": "https://www.law.go.kr/LSW/lsInfoR.do?lsiSeq=285693&lsId=000798&chrClsCd=010202&urlMode=lsInfoR",
    "khs-api.html": "https://www.heritage.go.kr/heri/html/HtmlPage.do?pg=/openapi/openApiInfo.jsp&pageNo=1_1_1_0",
    "khs-portal.html": "https://www.data.go.kr/data/15034324/openapi.do",
    "its-portal.html": "https://www.data.go.kr/data/15025526/fileData.do",
    "stations-portal.html": "https://www.data.go.kr/data/15073877/openapi.do",
    "university-addresses.json": "https://www.data.go.kr/download/standard.json?publicDataPk=15107736&colNmList=SCHL_NM&colNmList=SCHL_ENG_NM&colNmList=MAINBRANCH_NM&colNmList=UNIV_SE_NM&colNmList=SCHL_SE_NM&colNmList=FNDN_FORM_SE_NM&colNmList=CTPV_CD&colNmList=CTPV_NM&colNmList=LCTN_ROAD_NM_ADDR&colNmList=LCTN_LOTNO_ADDR&colNmList=STR_NM_ZIP&colNmList=LCTN_ZIP&colNmList=HMPG_ADDR&colNmList=RPRS_TEL_NO&colNmList=RPRS_FXNO&colNmList=FNDN_YMD&colNmList=CRTR_YR&colNmList=CRTR_YMD&totalCount=1995&svcTableNm=tn_pubr_public_univ_info_svc&perPage=10000&page=1",
    "copyright-article.html": "https://www.law.go.kr/LSW/lsLawLinkInfo.do?lsJoLnkSeq=&lsId=000798&chrClsCd=010202&print=print&lsJoLnkNm=%EC%A0%80%EC%9E%91%EA%B6%8C%EB%B2%95%20%EC%A0%9C7%EC%A1%B0&joNo=000700000",
    "copyright-mobile.html": "https://www.law.go.kr/LSW/lsSideInfoP.do?docCls=jo&joBrNo=00&joNo=0007&lsiSeq=285693&urlMode=lsScJoRltInfoR",
    "academy-mark.jpg": "https://www.academyinfo.go.kr/resources/images/main/kogl_mark.jpg",
    "khs-copyright.html": "https://www.khs.go.kr/html/HtmlPage.do?pg=/guide/copyright.jsp&mn=NS_08_03",
    "khs-api-doc.html": "https://www.khs.go.kr/html/HtmlPage.do?pg=/publicinfo/pbinfo3_0201.jsp&mn=NS_04_04_04",
    "law-art7.html": "https://www.law.go.kr/lsLinkProc.do?lsNm=%EC%A0%80%EC%9E%91%EA%B6%8C%EB%B2%95&joNo=000700&mode=11",
    "law-section.html": "https://www.law.go.kr/LSW/lsScJoRltInfoR.do?lsiSeq=285693&lsId=000798&joNo=0007&joBrNo=00&efYd=20261029&chrClsCd=010202",
    "airbook-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EB%8C%80%EA%B8%B0%ED%99%98%EA%B2%BD%EC%97%B0%EB%B3%B4",
    "forest-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EC%9E%84%EC%82%B0%EB%AC%BC%20%EC%A7%80%EB%A6%AC%EC%A0%81%ED%91%9C%EC%8B%9C",
    "nlic-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%ED%95%AD%EB%A7%8C%EB%B3%84%20%EB%AC%BC%EB%8F%99%EB%9F%89",
    "lofin-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EC%9E%AC%EC%A0%95%EC%9E%90%EB%A6%BD%EB%8F%84%20%EB%8B%B9%EC%B4%88",
    "e-history-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=2024%EB%85%84%20%EC%9E%90%EC%97%B0%EC%9E%AC%ED%95%B4%EC%83%81%ED%99%A9%ED%86%B5%EA%B3%84",
    "customs-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EA%B4%80%EC%84%B8%EC%B2%AD%20%EC%8B%9C%EA%B5%B0%EA%B5%AC%EB%B3%84%20%EC%88%98%EC%B6%9C%EC%9E%85%EC%8B%A4%EC%A0%81",
    "tasis-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EA%B7%BC%EB%A1%9C%EC%86%8C%EB%93%9D%20%EC%97%B0%EB%A7%90%EC%A0%95%EC%82%B0%20%EC%8B%A0%EA%B3%A0%ED%98%84%ED%99%A9%20%EC%A3%BC%EC%86%8C%EC%A7%80",
    "wamis2-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EA%B5%AD%EA%B0%80%EC%88%98%EC%9E%90%EC%9B%90%EA%B4%80%EB%A6%AC%EC%A2%85%ED%95%A9%EC%A0%95%EB%B3%B4%EC%8B%9C%EC%8A%A4%ED%85%9C%20%ED%95%98%EC%B2%9C",
    "power-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EB%B0%9C%EC%A0%84%EA%B8%B0%20%ED%98%84%ED%99%A9",
    "nlic-road-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EB%8F%84%EB%A1%9C%20%EC%88%98%EC%86%A1%EC%8B%A4%EC%A0%81",
    "landcover-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%ED%86%A0%EC%A7%80%ED%94%BC%EB%B3%B5%EC%A7%80%EB%8F%84%20WMS",
    "mof-find.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=2025%EB%85%84%20%EC%A0%84%EA%B5%AD%20%ED%95%AD%EB%A7%8C%20%EB%AC%BC%EB%8F%99%EB%9F%89",
    "customs1-details.html": "https://www.data.go.kr/data/15134344/openapi.do",
    "customs2-details.html": "https://www.data.go.kr/data/15134343/openapi.do",
    "landcover-details.html": "https://www.data.go.kr/data/3045398/openapi.do",
    "lofin-details.html": "https://www.data.go.kr/data/15058998/openapi.do",
    "nlic-road-details.html": "https://www.data.go.kr/data/3047704/fileData.do",
    "nlic-total-details.html": "https://www.data.go.kr/data/15050707/fileData.do",
    "airbook-details.html": "https://www.data.go.kr/data/15049240/fileData.do",
    "mcee-policy.html": "https://aid.mcee.go.kr/bbs/copyright.do",
    "customs-index.txt": "https://tradedata.go.kr/cts/js/ets/cmmn/indexMain.js",
    "customs-main.txt": "https://tradedata.go.kr/cts/js/ets/hmpg/main/main.js",
    "khs-link.json": "https://www.data.go.kr/tcs/dss/selectApiLinkUrl.do?publicDataPk=15034324",
    "landcover-link.json": "https://www.data.go.kr/tcs/dss/selectApiLinkUrl.do?publicDataPk=3045398",
    "lofin-link.json": "https://www.data.go.kr/tcs/dss/selectApiLinkUrl.do?publicDataPk=15058998",
    "customs-policy.html": "https://tradedata.go.kr/cts/openETS0100224Q.do",
    "landcover-api-guide.html": "https://aid.mcee.go.kr/api/land.do",
    "mcee-intro.html": "https://aid.mcee.go.kr/api/intro.do",
    "mcee-stats.html": "https://aid.mcee.go.kr/intro/stats.do",
    "aip-foreword.html": "https://aim.koca.go.kr/eaipPub/Package/2026-11-25-AIRAC/html/eAIP/KR-GEN-0.1-en-GB.html",
    "mcee-terms.doc": "https://aid.mcee.go.kr/files/me_openapi_terms_of_use.doc",
    "port-change-lookup.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%ED%99%94%EB%AC%BC%EC%B2%98%EB%A6%AC%EC%8B%A4%EC%A0%81%ED%86%B5%EA%B3%84%20%EC%A0%84%EB%85%84%EB%8C%80%EB%B9%84%EC%B6%94%EC%9D%B4",
    "generator-all-lookup.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EB%B0%9C%EC%A0%84%EA%B8%B0%EB%B3%84%20%EB%B0%9C%EC%A0%84%EC%84%A4%EB%B9%84",
    "welfare-lookup.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=2025%EB%85%84%20%EA%B5%AD%EB%AF%BC%EA%B8%B0%EC%B4%88%EC%83%9D%ED%99%9C%EB%B3%B4%EC%9E%A5%20%EC%88%98%EA%B8%89%EC%9E%90%20%ED%98%84%ED%99%A9",
    "trace-lookup.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=%EC%B6%95%EC%82%B0%EB%AC%BC%EC%9D%B4%EB%A0%A5%EC%A0%9C%20%EC%86%8C%20%EC%82%AC%EC%9C%A1%EB%91%90%EC%88%98",
    "disaster-latest-lookup.html": "https://www.data.go.kr/tcs/dss/selectDataSetList.do?keyword=2024%EB%85%84%20%EC%9E%90%EC%97%B0%EC%9E%AC%ED%95%B4%EC%83%81%ED%99%A9%ED%86%B5%EA%B3%84%20%EC%84%A0%EA%B3%B5%EA%B0%9C",
    "wamis-home.html": "https://www.wamis.go.kr/",
    "mtrace-home.html": "https://www.mtrace.go.kr/",
    "current-nts.html": "https://www.nts.go.kr/nts/main.do",
    "jeonbuk-home.html": "https://www.jeonbuk.go.kr/",
    "sejong-home.html": "https://www.sejong.go.kr/",
    "mohw-page.html": "https://www.mohw.go.kr/search.es?mid=a10610000000&searchTerm=2025%EB%85%84%20%EA%B5%AD%EB%AF%BC%EA%B8%B0%EC%B4%88%EC%83%9D%ED%99%9C%EB%B3%B4%EC%9E%A5%20%EC%88%98%EA%B8%89%EC%9E%90%20%ED%98%84%ED%99%A9",
    "mtrace-policy.html": "https://www.mtrace.go.kr/etc/copyrightPopup.do",
    "nts-policy.html": "https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?mi=6791&cntntsId=8169",
    "mohw-results.html": "https://www.mohw.go.kr/react/search/search.jsp?searchTerm=2025%EB%85%84%20%EA%B5%AD%EB%AF%BC%EA%B8%B0%EC%B4%88%EC%83%9D%ED%99%9C%EB%B3%B4%EC%9E%A5%20%EC%88%98%EA%B8%89%EC%9E%90%20%ED%98%84%ED%99%A9",
    "mohw-1491455.html": "https://www.mohw.go.kr/board.es?mid=a10411010300&bid=0019&act=view&list_no=1491455",
    "mohw-1492519.html": "https://www.mohw.go.kr/board.es?mid=a10411010300&bid=0019&act=view&list_no=1492519",
    "mohw-source-check.pdf": "https://www.mohw.go.kr/boardDownload.es?bid=0019&list_no=1491455&seq=2"
}


def write_csv(path, fields, rows):
    with path.open("w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def universities(manifest):
    with (ROOT / "data/build/layers/university_research_funding.csv").open(encoding="utf-8-sig", newline="") as f:
        funding = list(csv.DictReader(f))
    chosen = sorted((r for r in funding if (r["year"], r["kind"], r["unit"]) == ("2025", "연구비 지원 계", "천원")), key=lambda r: Decimal(r["value"]), reverse=True)
    if len(set(r["name"] for r in chosen)) != len(chosen):
        raise ValueError("연구비 학교별 중복행 확인 필요")
    addresses = read_json(RAW / "university-addresses.json", [])
    if len(addresses) != read_json(RAW / "campus-header.json", {})["totalCount"]:
        raise ValueError("전국 주소 파일 행 수 불일치")
    rows = []
    for rank, f in enumerate(chosen[:40], 1):
        base, _, tag = f["name"].partition("_")
        campus = tag or "본교"
        source_tag = {"제2캠퍼스": "제2캠퍼"}.get(campus, campus)
        matches = [a for a in addresses if a["SCHL_NM"] == base and a["CRTR_YR"] == f["year"] and a["MAINBRANCH_NM"] == source_tag and a["UNIV_SE_NM"] == "대학"]
        row = dict(rank=rank, name=f["name"], campus="", value_thousand_krw=f["value"], year=f["year"], address="", sido="", sigungu="", lon="", lat="", address_source_url="", funding_source_id=f["source_id"], note="학교명·연도·본분교구분이 일치하는 단일 대학 주소를 찾지 못함")
        if len(matches) == 1:
            a = matches[0]
            addr = a["LCTN_ROAD_NM_ADDR"].strip()
            parts = addr.split()
            if parts and parts[0] == a["CTPV_NM"]:
                district = parts[1:2]
                if parts[1].endswith("시") and parts[2].endswith("구"):
                    district.append(parts[2])
                note = f'공시 학교명과 주소표 {base}({source_tag}) 일치.' if tag else "연구비 학교명에 캠퍼스 구분이 없어 주소표의 같은 이름 본교 행 선택."
                if f["address"] == "전남광주":
                    note += " 공시 소재지는 전남광주, 주소는 2025 기준 원문 행정명."
                row.update(campus=campus, address=addr, sido=a["CTPV_NM"], sigungu=" ".join(district), address_source_url=manifest["campuses.html"]["url"], note=note)
        rows.append(row)
    write_csv(ROOT / "data/build/layers/universities.csv", list(rows[0]), rows)
    return rows, funding


# Reviewed passages must remain present before a named condition is exported.
# An empty license with a policy URL records a policy found without an item-level grant.
def license_rows(manifest):
    policies = {
        "kosis.kr": ("kosis-policy.html", "site_policy", "이용자는 KOSIS 통계정보를 자유롭게 사용, 재사용 및 재배포할 수 있으며 통계정보의 비상업적 또는 상업적 활용이 모두 가능합니다.", "국내 통계표. 출처 명시, 무가공 유료 판매 금지. 국제·북한통계와 간행물은 별도 조건."),
        "rt.molit.go.kr": ("molit.html", "dataset_page", "외부 공개시에는 반드시 신고일 기준으로 집계되는 공식통계를 이용하여 주시기 바랍니다.", "계약일 기준 다운로드 자료는 참고용. 이 문구는 외부 공개 조건이며 별도 공공누리 유형은 확인되지 않음."),
        "esa-worldcover.org": ("worldcover.html", "dataset_page", "Creative Commons Attribution 4.0 International License", "제품·논문 인용 및 출처 표기."),
        "naciscdn.org": ("naturalearth-readme.txt", "license_doc", "public domain", "Natural Earth Vector 공식 저장소 설명."),
        "download.geofabrik.de": ("osm.html", "license_doc", "Open Data Commons Open Database License", "ODbL 1.0. 기여자 출처와 라이선스 표시, 파생 데이터베이스 공개 시 동일조건."),
        "raw.githubusercontent.com": ("boundary-license.txt", "license_doc", "Creative Commons Attribution 4.0 International (CC BY 4.0)", "가공물에 적용. 원자료 SGIS의 공공누리 제1유형 출처표시도 유지. 문서의 출처 표기 참조."),
        "coastwatch.pfeg.noaa.gov": ("terrain.html", "dataset_page", "for educational, research and non-profit purposes", "SRTM30+ 30초 격자. 복제 시 원문의 고지와 지정 문단을 포함. 상업 제품·상업 목적 이용은 UC San Diego와 협의."),
        "www.law.go.kr": ("law-art7.html", "license_doc", "보호받지 못하는 저작물", "저작권법 제7조 제1호. 법률·명령 본문에 적용."),
        "tradedata.go.kr": ("customs-policy.html", "site_policy", "영리 목적의 이용을 포함한 자유로운 활용이 보장됩니다.", "관세청 공공데이터 정책. 비공개·제3자 권리 정보 제외."),
        "data.gg.go.kr": ("policy-data-gg-go-kr.html", "site_policy", "경기도의 명시적 승인 없이 상업적으로 사용할 수 없으며", "서비스 이용약관 제12조. 저작자·출처표시, 제3자 조건 우선, 상업 이용은 승인 필요."),
        "komir.kmrgis.or.kr": ("policy-www-komir-or-kr.html", "site_policy", "KOMIR와 사전에 별도의 협의를 하거나 허락을 득하여야 하며", "출처표시. 상업 이용·웹을 통한 제3자 제공은 사전 협의 또는 허락, 단순 오류 정정 외 무단변경 금지."),
    }
    single = {
        "incheon-aip": ("aip-foreword.html", "site_policy", "prior permission or consultation with the MOLIT is needed", "AIP GEN 0.1 §5. 영리 이용 사전 허가·협의, 출처표시, 무단 복제·배포와 오류 정정 외 무단 변경 제한."),
        "seoul-business-census-2024": ("seoul-business-census-2024.html", "dataset_page", "공공누리 1유형 : 출처표시 (상업적 이용 및 변경 가능)", ""),
        "gyeongbuk-business-2024": ("gyeongbuk-business-2024.html", "dataset_page", "공공누리 제3유형(출처표시 + 변경금지)", ""),
        "sejong-business-2024": ("sejong-business-2024.html", "dataset_page", "공공누리 4유형 출처표시 + 상업적 이용금지 + 변경금지", ""),
        "mohw-welfare-2025": ("mohw-1491455.html", "dataset_page", "출처표시+상업적이용금지+변경금지", "보건복지부 원 게시물 공공누리 제4유형. 첨부 PDF SHA-256이 프로젝트 PDF와 일치."),
        "mtrace-hanwoo-202610": ("mtrace-policy.html", "site_policy", "저작권자의 사전승낙 없이 복제, 전송, 출판, 배포, 방송등을 통해 영리목적으로 이용하거나 제3자에게 제공해서는 안됩니다.", "축산물이력제 홈페이지의 쇠고기이력추적제 저작권보호정책. 영리 이용·제3자 제공 사전승낙."),
        "academyinfo-research-funding-2026": ("academyinfo-research-funding-2026.html", "dataset_page", "출처표시", "공시DATA 다운로드 영역의 공공누리 이미지(academy-mark.jpg)에 적힌 조건."),
    }
    portal_alias = {"jumin.mois.go.kr":"jumin-portal.html", "www.khs.go.kr":"khs-portal.html","www.nfqs.go.kr":"fishgi-portal.html","www.airportal.go.kr":"airports-portal.html","data.mafra.go.kr":"farm-portal.html","www.its.go.kr":"its-portal.html"}
    portal_key = {"nlic-road-od-2024":"nlic-road-details.html","landcover-me-wms-lv2-2025y":"landcover-details.html"}
    partial = {
        "tasis.nts.go.kr":"nts-policy.html","www.mtrace.go.kr":"mtrace-policy.html",
        "www.chungbuk.go.kr":"policy-www-chungbuk-go-kr.html","www.jeju.go.kr":"policy-www-jeju-go-kr.html","www.jeonnam.go.kr":"policy-www-jeonnam-go-kr.html","www.knps.or.kr":"policy-www-knps-or-kr.html","www.forest.go.kr":"policy-www-forest-go-kr.html","www.mof.go.kr":"policy-www-mof-go-kr.html","www.mois.go.kr":"mois-policy.html","coast.mof.go.kr":"policy-coast-mof-go-kr.html","aid.mcee.go.kr":"mcee-policy.html","www.airkorea.or.kr":"policy-www-keco-or-kr.html","www.heritage.go.kr":"khs-copyright.html",
    }
    reasons = {
        "air-yearbook-2025":"2025년 연보의 이용표시 미확인. 포털의 2019년 연보 조건을 이월하지 않음.",
        "airkorea-stations":"웹 측정소 표의 표시 미확인. 별도 포털 API에는 출처표시·변경금지(제3유형).",
        "lofin-fiscal-2026":"지방재정365 이용정책 본문이 응답에 없음. 포털의 API 조건을 웹 조회표에 적용할 수 있는지 미확인.",
        "epsis-generators":"포털 발전설비 등록건의 메뉴 ID와 내려받은 표의 ID가 다름.",
        "institution":"여러 대학·연구기관의 연락처 페이지를 합친 기록으로 전체에 적용할 이용조건 미확인.",
        "khs":"여러 해설·왕릉 일람표를 합친 자료로 각각의 공공누리 표시 미확인.",
        "seoul-business-10160":"데이터 허브 응답의 라이선스 항목 값이 비어 있음.",
        "wamis-dam-observations":"OGC 서비스 설명에서 댐 관측소 재배포 조건 미확인.",
        "tasis-4-2-15-2022":"통계 페이지는 JavaScript 화면으로, 해당 표의 이용조건 원문을 확보하지 못함.",
        "mtrace-hanwoo-202610":"KAPE 통계표에 이용허락 표시를 찾지 못함.",
        "mtrace-pig-sido-2026q3":"축산물이력제의 정책 문구는 쇠고기이력추적제에 한정된다. 돼지 통계표에 적용되는 허락 미확인.",
    }
    failures = read_json(RAW/"failures.json", {})
    result = []
    for s in SOURCES:
        key, url = s["key"], s.get("url") or ""
        host = urlsplit(url).hostname
        item = single.get(key) or policies.get(host)
        names = []
        if host == "www.data.go.kr":
            ids = re.findall(r"/data/(\d+)/", url) or [f["no"] for f in s.get("files", [])]
            names = [f"portal-{n}.html" for n in ids]
        elif host in portal_alias or key in portal_key:
            names = [portal_key.get(key) or portal_alias[host]]
        if names:
            terms = []
            for n in names:
                if n in manifest:
                    label = soup(n).find(string=lambda x: x and x.strip()=="이용허락범위")
                    if label:
                        field = label.parent.find_next_sibling()
                        if field:
                            terms.append(" ".join(field.get_text(" ",strip=True).split()))
            if len(terms)==len(names) and len(set(terms))==1 and terms[0]:
                note = "동일 자료를 안내하는 포털 등록 페이지." if host != "www.data.go.kr" else ""
                if key == "landcover-me-wms-lv2-2025y":
                    note = "포털은 제1유형. 제공기관 Open API 약관 제4·5조에는 비상업적 사용 및 실시간 연동 외 검색결과 복제·저장·전송 제한도 명시. " + manifest["mcee-terms.doc"]["url"]
                if len(names)>1:
                    note = f"구성 파일 {len(names)}개 상세 페이지의 조건이 모두 같음. 나머지 상세 페이지(입력 파일 순) " + " ".join(manifest[f]["url"] for f in names[1:])
                item = (names[0], "dataset_page", terms[0], note)
        row = dict(key=key, license="", license_url="", basis="", checked_at=datetime.now().astimezone().date().isoformat(), note="")
        if item:
            n,basis,term,note=item
            if n in manifest:
                b=soup(n)
                text=" ".join(b.get_text(" ",strip=True).split())
                image_mark = key=="academyinfo-research-funding-2026" and b.select_one('img[src$="/kogl_mark.jpg"]') and manifest.get("academy-mark.jpg",{}).get("sha256")==ACADEMY_MARK_SHA
                if image_mark or (key != "academyinfo-research-funding-2026" and term in text):
                    row.update(license=term, license_url=manifest[n]["url"], basis=basis, note=note)
        if key == "mohw-welfare-2025" and manifest.get("mohw-source-check.pdf",{}).get("sha256") != s.get("sha256"):
            row.update(license="", note="게시문 텍스트는 공공누리 제4유형(출처표시+상업적 이용금지+변경금지). 실제 이용한 첨부 PDF의 통계표까지 적용되는 허락은 미확인.")
        if not row["license"] and not row["note"]:
            n=partial.get(host)
            if n and n in manifest:
                row.update(license_url=manifest[n]["url"],basis="site_policy")
            elif key+".html" in manifest:
                row["license_url"] = manifest[key+".html"]["url"]
            row["note"]=reasons.get(key) or ("자체 수작업 표로 출판된 원자료와 이용허락 원문을 특정하지 못함." if not url else "사이트 정책은 자료별 공공누리 표시를 요구하나 해당 자료의 표시를 확인하지 못함." if n else "공식 페이지에서 해당 자료의 이용허락 문구를 확인하지 못함.")
            if key+".html" in failures and key not in reasons:
                row["note"]="공식 페이지를 받지 못함. "+failures[key+".html"]["reason"]
        result.append(row)
    write_csv(ROOT/"data/build/licenses.csv",list(result[0]), result)
    return result
ACADEMY_MARK_SHA = "5627a26c4d84ee1cc9f8720aa4e49b464891f962cead6f7eb553f36f835f5926"

def report(manifest, licenses, schools, funding):
    counts = Counter(r["license"] for r in licenses)
    missing = [r for r in licenses if not r["license"]]
    duplicates = [k for k,n in Counter(r["key"] for r in licenses).items() if n > 1]
    failures = read_json(RAW / "failures.json", {})
    matched = [s for s in schools if s["address"]]
    lines = [
        "# 이용허락과 연구비 상위 대학 소재지", "",
        f"출처 {len(licenses)}행 중 {len(licenses)-len(missing)}행에서 이용조건을 확인했다. 여기에는 공개 방법만 규정한 실거래가 자료도 포함된다. {len(missing)}행({len(set(r['key'] for r in missing))}개 key)은 허락을 확정하지 못했다. 2025년 연구비 상위 {len(schools)}개 공시 단위 중 {len(matched)}개의 캠퍼스 도로명주소를 확인했다.", "",
        "## 대학 주소", "",
        f"연구비 파일 {len(funding)}행의 kind는 모두 ‘연구비 지원 계’, 단위는 천원, 연도는 2025다. 학교명 전체 문자열 기준으로 중복이 없다. 한 대학의 본교와 분교 또는 제2캠퍼스가 별도 이름으로 등장한다. 공시 단위별 총액을 그대로 숫자 내림차순으로 정렬하고 상위 40행을 취했다. 출력 금액의 소수점 표기까지 원본과 같다.", "",
        f"한국대학교육협의회의 [전국대학및전문대학정보표준데이터]({manifest['campuses.html']['url']})에서 공개 다운로드용 JSON {read_json(RAW/'campus-header.json',{})['totalCount']:,}행을 받았다. 대학구분명 ‘대학’과 기준연도 2025를 선택했다. 연구비의 학교명·캠퍼스를 기준으로 주소표에서 단일 행만 연결했다. 학교 대표 소재지이므로 같은 대학의 연구비가 그 주소 한 곳에서만 집행됐다는 뜻으로 해석할 수 없다.", "",
        "가톨릭대학교_제2캠퍼스는 주소표의 ‘제2캠퍼’와 연결했다. 서울 서초구 반포대로 222다. 한양대학교(ERICA)_분교는 안산시 상록구 한양대학로 55, 한양대학교는 서울 성동구 왕십리로 222다. 표시가 없는 학교는 본교 행을 선택했다. 전남대·광주과학기술원·조선대의 시도는 주소 원문에 있는 광주광역시를 유지했다. 일반구가 있는 도시는 시와 구를 함께 남겼다.", "",
        "주소 미확인 대학 " + (" · ".join(s["name"] for s in schools if not s["address"]) or "없음") + ". 위도·경도는 주소표에 제공되지 않아 모두 비어 있다.", "",
        "## 이용조건별 출처 수", "",
        f"입력 배열 순서대로 {len(licenses)}행을 기록했다. 고유 key는 {len(set(r['key'] for r in licenses))}개다. 두 번 등장한 " + ", ".join(f"`{k}`" for k in duplicates) + "도 각각 두 행으로 계산했다. 기준은 자료 상세 페이지의 문구, 공식 라이선스 문서, 해당 자료에 적용되는 사이트 정책이다. 사이트가 개별 공공누리 표시를 요구할 때는 정책 문서만으로 유형을 부여하지 않았다.", "",
        "| 원문에 표시된 이용조건 또는 해당 조항 | 출처 행 |", "| --- | ---: |",
    ]
    lines.extend(f"| {label or '미확인'} | {count} |" for label,count in counts.most_common())
    lines += ["", "## 상업 이용·변경·재배포에 제약이 있거나 별도 확인이 필요한 자료", ""]
    groups = [
        ("KOSIS 국내 통계표", lambda r: "KOSIS 통계정보" in r["license"], "출처 명시. 가공 절차 없이 유료 판매하는 행위를 금지한다. 국제·북한통계의 비상업·재배포 금지 예외는 별도 조항이다."),
        ("국토교통부 아파트 매매·전월세", lambda r: r["key"].startswith("molit-apartment"), "계약일 기준 다운로드는 참고용이다. 외부 공개에는 신고일 기준 공식통계를 사용하라는 문구가 있다. 상업·변경을 포괄 허용하는 라이선스는 확인하지 못했다."),
        ("경기도 사업체조사", lambda r: r["key"].startswith("gyeonggi-business"), "서비스 약관은 가공·판매 등 상업 이용에 경기도의 명시적 승인을 요구한다."),
        ("경북 사업체조사", lambda r: r["key"]=="gyeongbuk-business-2024", "제3유형. 변경 금지."),
        ("세종 사업체조사", lambda r: r["key"]=="sejong-business-2024", "제4유형. 상업 이용 및 변경 금지."),
        ("보건복지부 수급자 현황", lambda r: r["key"]=="mohw-welfare-2025", "제4유형. 보건복지부 게시물의 PDF를 다시 받아 프로젝트 원자료와 SHA-256이 같은지 확인했다."),
        ("SRTM30+", lambda r: r["key"]=="terrain_srtm30plus", "교육·연구·비영리 목적 복제 등은 지정 고지문 포함이 조건이다. 상업적 사용자는 UC San Diego에 연락하도록 명시한다."),
        ("OpenStreetMap", lambda r: r["key"]=="osm-water", "ODbL 1.0. 출처와 라이선스 표시 및 파생 데이터베이스 동일조건."),
        ("행정동 경계",lambda r:r["key"]=="boundary_admdong","CC BY 4.0 가공물. 재배포 시 SGIS 공공누리 제1유형의 출처표시도 유지한다."),
        ("광해광업공단 광산검색",lambda r:r["key"]=="komir-mine-grid","상업 이용·웹을 통한 제3자 제공에 사전 협의 또는 허락 필요. 출처표시, 오류 정정 외 무단변경 금지."),
        ("한우 이력 통계",lambda r:r["key"]=="mtrace-hanwoo-202610","쇠고기이력추적제 저작물은 영리 이용이나 제3자 제공 시 사전승낙 필요."),
        ("인천공항 AIP",lambda r:r["key"]=="incheon-aip","영리 이용 사전 허가 또는 협의. 무단 복제·배포 및 단순 오류 정정 외 무단 변경 제한."),
        ("중분류 토지피복 WMS",lambda r:r["key"]=="landcover-me-wms-lv2-2025y","포털의 제1유형 표기와 제공기관의 API 사용 조건이 병존한다. API 약관 제4조는 비상업적 사용만 허용하고 제5조는 실시간 연동 외 복제·저장·전송을 제한한다. [제공기관 약관 문서]("+manifest["mcee-terms.doc"]["url"]+")"),
    ]
    for title,test,summary in groups:
        records=[r for r in licenses if test(r)]
        if not records:
            continue
        keys=list(dict.fromkeys(r["key"] for r in records))
        lines.append(f"- **{title}** ({len(records)}행) {summary} [원문]({records[0]['license_url']})")
        if len(keys) > 15:
            lines.extend(["", f"  <details><summary>해당 key {len(keys)}개</summary>", ""])
            lines.extend("  - " + ", ".join(f"`{k}`" for k in keys[i:i+4]) for i in range(0,len(keys),4))
            lines.extend(["", "  </details>", ""])
        else:
            lines.append("  " + ", ".join(f"`{k}`" for k in keys))
    lines += ["", "## 이용허락을 확인하지 못한 출처", "", "빈 칸은 재배포 허락을 뜻하지 않는다. 사이트 정책 링크가 있어도 개별 파일의 유형을 확인할 수 없는 경우가 있다.", "", "| key | 확인하지 못한 이유 |", "| --- | --- |"]
    for r in missing:
        note=r["note"].split("HTTPSConnectionPool")[0].rstrip(". ")
        if r["key"].startswith("wamis-rivline"):
            note="WAMIS 지도 페이지가 HTTP 500을 반환했고 해당 레이어의 허락 원문을 확보하지 못함."
        lines.append(f"| `{r['key']}` | {note} |")
    lines += ["","## 원자료와 재현", "",
        f"공식 페이지·파일 응답 {len(manifest)}건을 저장했다. 각 URL, 최종 응답 URL, UTC 수신 시각, SHA-256, 바이트 수는 `data/raw/layers4/manifest.json`에 있다. 검색결과·화면 구성 스크립트·오류 안내가 담긴 HTTP 200 응답도 보존했다. 허락의 근거로 인용한 문서는 CSV의 URL에서 구분할 수 있다. 보훈대상자 묶음은 17개 상세 페이지를 개별 확인하여 첫 근거 URL은 license_url에, 나머지 16개는 note에 입력 순서대로 기록했다.", "",
        "받지 못한 요청은 다음과 같다. Natural Earth는 공식 저장소 문서로 대조했고, 대학 주소는 표준데이터 다운로드 화면이 실제 사용하는 JSON으로 받았다. 로그인·자료 신청·인증키 발급·외부 지오코딩은 사용하지 않았다.", "",
    ]
    for n,v in failures.items():
        msg = v["reason"]
        cause = next((human for needle,human in [("CERTIFICATE_VERIFY_FAILED","TLS 인증서를 검증할 수 없었다."),("ConnectionResetError","서버가 연결을 종료했다."),("406 Client","HTTP 406 응답"),("404 Client","HTTP 404 응답"),("500 Server","HTTP 500 응답")] if needle in msg),msg)
        lines.append(f"- `{n}` — {cause}")
    lines += ["", "프로젝트 루트에서 `python -I pipeline/collect_layers4.py`로 수집과 출력을 재현한다. `--offline`은 이미 받은 파일의 바이트 수와 SHA-256을 검사한 뒤 두 CSV와 이 보고서를 다시 만든다. Python 패키지 requests와 beautifulsoup4를 사용한다.", ""]
    (ROOT/"docs/LAYERS4_DATA_REPORT.md").write_text("\n".join(lines), "utf8")


def main():
    if not sys.flags.isolated or Path.cwd().resolve().is_relative_to(RAW):
        raise SystemExit("프로젝트 루트에서 python -I 로 실행하세요.")
    if sys.argv[1:] not in ([], ["--offline"]):
        raise SystemExit("python -I pipeline/collect_layers4.py [--offline]")
    if "--offline" not in sys.argv:
        collect(primary())
        collect(REVIEW_URLS.items())
    manifest = read_json(MANIFEST,{})
    for name, meta in manifest.items():
        data = (RAW/name).read_bytes()
        if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise ValueError(f"원자료 무결성 오류 {name}")
    schools,funding = universities(manifest)
    licenses = license_rows(manifest)
    report(manifest, licenses, schools, funding)


if __name__ == "__main__":
    main()

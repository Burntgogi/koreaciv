"""Collect public source files for the fifth layer data pass."""

import argparse
import datetime as dt
import hashlib
import json
import re
import site
import sys
import time
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

from collect_layers import ROOT
from collect_econ_web import PublicSession
from lib import netguard as NG  # noqa: E402  (감사 08·09: 허용 호스트·HTTPS·리디렉션·크기 상한·RAW 밖 경로)
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError

RAW = ROOT / "data/raw/layers2"
ROAD = "https://www.nlic.go.kr/nlic/frghtRoad0010.action"
PARK = "https://www.knps.or.kr/front/portal/stats/statsDtl.do?menuNo=8000627&refId=REFM000902"
PARK_PDF = ("https://www.knps.or.kr/portal/file/cdown.do?"
            "tfId=TF030&fileId=POMxo6eh0JayRIgt3HnGIA%3D%3D&fileNo=0")
WAMIS = "https://map.wamis.go.kr:8444/geoserver/mbrf/wfs"
WAMIS_CAPABILITIES = WAMIS + "?service=WFS&request=GetCapabilities"
WAMIS_DAMS = (WAMIS + "?service=WFS&version=1.0.0&request=GetFeature"
              "&typeName=mbrf:dm_obsvtr&srsName=EPSG:4326&outputFormat=application/json")
HERITAGE_BASE = "https://www.heritage.go.kr/heri/html/HtmlPage.do?pg=/unesco/"
HERITAGE_INDEX = HERITAGE_BASE + "korHeritageInfo.jsp"
HERITAGE_PAGES = {
    "khs-gyeongju": (HERITAGE_BASE + "Heritage/Heritage_06.jsp", "경주역사유적지구"),
    "khs-dolmens": (HERITAGE_BASE + "Heritage/Heritage_07.jsp", "고창ㆍ화순ㆍ강화 고인돌 유적"),
    "khs-jeju-volcanic": (HERITAGE_BASE + "Heritage/Heritage_08.jsp", "제주 화산섬과 용암동굴"),
    "khs-tombs": ("https://royal.khs.go.kr/ROYAL/contents/R106010000.do", "조선왕릉"),
    "khs-historic-villages": (HERITAGE_BASE + "Heritage/Heritage_10.jsp", "한국의 역사마을"),
    "khs-baekje": (HERITAGE_BASE + "Heritage/Heritage_12.jsp", "백제역사유적지구"),
    "khs-sansa": (HERITAGE_BASE + "Heritage/Heritage_13.jsp", "산사, 한국의 산지 승원"),
    "khs-seowon": (HERITAGE_BASE + "Heritage/Heritage_14.jsp", "한국의 서원"),
    "khs-tidal-flats": (HERITAGE_BASE + "Heritage/Heritage_15.jsp", "한국의 갯벌"),
    "khs-gaya": (HERITAGE_BASE + "Heritage/Heritage_16.jsp", "가야고분군"),
    "khs-bangucheon": (HERITAGE_BASE + "Heritage/Heritage_17.jsp", "반구천의 암각화"),
    "khs-seokguram-bulguksa": (HERITAGE_BASE + "Heritage/Heritage_01.jsp", "석굴암"),
    "khs-haeinsa": (HERITAGE_BASE + "Heritage/Heritage_02.jsp", "해인사 장경판전"),
    "khs-jongmyo": (HERITAGE_BASE + "Heritage/Heritage_03.jsp", "종묘"),
    "khs-changdeokgung": (HERITAGE_BASE + "Heritage/Heritage_04.jsp", "창덕궁"),
    "khs-hwaseong": (HERITAGE_BASE + "Heritage/Heritage_05.jsp", "수원화성"),
    "khs-namhansanseong": (HERITAGE_BASE + "Heritage/Heritage_11.jsp", "남한산성"),
}
MINE_BASE = "https://komir.kmrgis.or.kr/kmrgis/"
MINE_PAGE = MINE_BASE + "search-service/mine.do"
MINE_QUERY = MINE_BASE + "100/system/map/search-footer.do"
MINE_FIELDS = ("FID", "MN_NM", "MN_STT", "MNRL_LCLSF", "MNRL_MCLSF", "RPRS_ORE", "MN_RGN", "LCTN", "CDARNO")
DAEGU_BUSINESS = "https://stat.daegu.go.kr/information/notice/selectBoardArticle.do?bbsId=BBSMSTR_NOTICE&nttId=567"
ULSAN_BUSINESS = "https://www.ulsan.go.kr/s/statData/public/list.ulsan?codeId=PBL003&mId=001004003000000000"
SEOUL_BUSINESS = "https://data.seoul.go.kr/dataList/OA-20326/F/1/datasetView.do"
SEOUL_FILES = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
INSTITUTIONS = {
    "kaist": ("한국과학기술원", "과학기술원", "https://www.kaist.ac.kr/kr/", "대전광역시 유성구"),
    "gist": ("광주과학기술원", "과학기술원", "https://www.gist.ac.kr/kr/main.html", "전남광주통합특별시 북구"),
    "dgist": ("대구경북과학기술원", "과학기술원", "https://www.dgist.ac.kr/", "대구광역시 달성군"),
    "unist": ("울산과학기술원", "과학기술원", "https://www.unist.ac.kr/unist/main.do", "울산광역시 울주군"),
    "kist": ("한국과학기술연구원", "정부출연연구기관", "https://kist.re.kr/ko/index.do", "서울특별시 성북구"),
    "etri": ("한국전자통신연구원", "정부출연연구기관", "https://www.etri.re.kr/kor/main/main.etri", "대전광역시 유성구"),
    "yonsei": ("연세대학교", "대학", "https://www.yonsei.ac.kr/sc/index.do", "서울특별시 서대문구"),
    "korea": ("고려대학교", "대학", "https://www.korea.ac.kr/sites/ko/index.do", "서울특별시 성북구"),
}
ACADEMY = "https://www.academyinfo.go.kr/popup/main0810/"
GYEONGBUK_BUSINESS = "https://www.gb.go.kr/Sub/datastat/page.do?mnu_uid=7878&cmd=2&B_STEP=260567300&V_NUM=102"
SEJONG_BUSINESS = "https://www.sejong.go.kr/stat/bbs/view.do?bbsSn=705&key=1910168796725"
CHUNGNAM_BUSINESS = ("https://alldam.chungnam.go.kr/board/view.chungnam?boardId=BBS_0000026"
                     "&menuCd=DOM_000000202007001006&paging=ok&startPage=1&dataSid=2323")


class LayerArchive:
    def __init__(self):
        self.path = RAW / "manifest.json"
        self.entries = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def has(self, source_id):
        if source_id not in self.entries:
            return False
        entry = self.entries[source_id]
        content = NG.check_path(RAW, entry["file"]).read_bytes()
        if len(content) != entry["bytes"] or hashlib.sha256(content).hexdigest() != entry["sha256"]:
            raise ValueError(f"Changed archive file: {entry['file']}")
        return True

    def save(self, source_id, file, content, **metadata):
        path = NG.check_path(RAW, file)
        if path.exists():
            raise FileExistsError(path)
        if not content:
            raise ValueError(f"Empty source: {source_id}")
        path.parent.mkdir(parents=True, exist_ok=True)
        incoming = path.with_suffix(path.suffix + ".tmp")
        incoming.write_bytes(content)
        incoming.replace(path)
        self.entries[source_id] = dict(
            metadata, file=file, retrieved=dt.datetime.now(dt.timezone.utc).isoformat(),
            bytes=len(content), sha256=hashlib.sha256(content).hexdigest(),
        )
        pending = self.path.with_suffix(".tmp")
        pending.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pending.replace(self.path)
        print(f"{source_id} {file} {len(content):,} bytes", flush=True)


def direct(session, archive, source, file, url, title, publisher, year, signature,
           *, license_type="미확인", catalog=None):
    if archive.has(source):
        return
    response = session.get(url, timeout=60)
    response.raise_for_status()
    if not response.content.startswith(signature):
        raise ValueError(f"Unexpected file format: {response.url}")
    archive.save(source, file, response.content, title=title, publisher=publisher, url=response.url,
                 vintage=year, license=license_type, catalog_url=catalog)


def road(session, archive):
    direct(session, archive, "nlic-road-od-2024", "02/road-od-2024.xls",
           ROAD + "?command=DWLOAD&S_TOYEAR=2024&S_FRYEAR=2024",
           "도로 O·D별 수송실적", "국가물류통합정보센터 (국가교통DB)", "2024",
           bytes.fromhex("D0CF11E0A1B11AE1"), catalog=ROAD)


def park(session, archive):
    direct(session, archive, "knps-area-2025", "05/knps-basic-statistics-2026-rev.pdf", PARK_PDF,
           "2026 국립공원기본통계 수정 공표", "국립공원공단", "2025",
           b"%PDF", license_type="공공누리 제1유형", catalog=PARK)


def dam(session, archive):
    direct(session, archive, "wamis-wfs-capabilities", "04/wamis-capabilities.xml", WAMIS_CAPABILITIES,
           "WAMIS 공개 WFS GetCapabilities", "국가수자원관리종합정보시스템", None,
           b"<?xml", catalog=WAMIS_CAPABILITIES)
    if b"<Name>mbrf:dm_obsvtr</Name>" not in (RAW / "04/wamis-capabilities.xml").read_bytes():
        raise ValueError("WAMIS capabilities no longer lists the dam observation layer")
    direct(session, archive, "wamis-dam-observations", "04/wamis-dam-observations.geojson", WAMIS_DAMS,
           "WAMIS 댐 관측소", "국가수자원관리종합정보시스템", None,
           b'{"type":"FeatureCollection"', catalog=WAMIS_CAPABILITIES)


def heritage_years(content):
    page = BeautifulSoup(content, "html.parser")
    years = {}
    for link in page.select('a[href*="/Heritage/Heritage_"]'):
        page_no = re.search(r"/Heritage_(\d{2})\.jsp", link["href"])
        listing = link.find_parent("li")
        year = re.search(r"\((\d{4})년\)", listing.get_text(" ", strip=True)) if listing else None
        if page_no and year:
            years[page_no[1]] = int(year[1])
    return years


def heritage_year(source, url, years):
    number = "09" if source == "khs-tombs" else re.search(r"Heritage_(\d{2})\.jsp", url)[1]
    return years[number]


def heritage(session, archive):
    index = "khs-world-heritage-index"
    if not archive.has(index):
        response = session.get(HERITAGE_INDEX, timeout=40)
        response.raise_for_status()
        if len(heritage_years(response.content)) < len(HERITAGE_PAGES):
            raise ValueError("Incomplete public World Heritage index")
        archive.save(index, "08/khs-world-heritage-index.html", response.content, title="한국의 세계유산",
                     publisher="국가유산청", vintage=None, url=response.url, license="미확인")
    years = heritage_years((RAW / archive.entries[index]["file"]).read_bytes())
    for source, (url, title) in HERITAGE_PAGES.items():
        if archive.has(source):
            continue
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if title not in BeautifulSoup(response.content, "html.parser").get_text(" ", strip=True):
            raise ValueError(f"World Heritage page did not contain {title}")
        archive.save(source, f"08/{source}.html", response.content, title=title, publisher="국가유산청",
                     vintage=heritage_year(source, url, years), url=response.url, license="미확인")


def mines(session, archive):
    # Use only the columns displayed by the public results grid and its row identifier.
    first = "komir-mine-grid-001"
    if archive.has(first):
        grid = json.loads((RAW / archive.entries[first]["file"]).read_bytes())
        pages = (int(grid["recordsTotal"]) + 9) // 10
        if all(archive.has(f"komir-mine-grid-{page:03d}") for page in range(1, pages + 1)):
            return
    session.get(MINE_PAGE, timeout=30).raise_for_status()
    headers = {"Referer": MINE_PAGE, "X-Requested-With": "XMLHttpRequest"}
    options = dict(dataName="V_N_DMSTC_MN_100", resourceDataName="",
                   resourceLayerTypeCode="1001", layerTypeCode="1001")
    response = session.post(MINE_BASE + "100/system/map/get-footer-resource.do",
                            json=options, headers=headers, timeout=30)
    response.raise_for_status()
    definition = response.json()
    if definition.get("isReadData") is False:
        raise ValueError("Mine catalog access is restricted")
    fields = tuple(field["FIELD_NAME"] for field in definition["fldList"]
                   if field["IS_VIEW_GRID"] or field["FIELD_NAME"] == "FID")
    if fields != MINE_FIELDS:
        raise ValueError(f"Unexpected mine grid schema: {fields}")
    params = dict(options, length=10, colSize=len(fields), csSearchVal=json.dumps({"mineName": ""}))
    for i, field in enumerate(fields):
        params[f"columns[{i}][name]"] = field
        params[f"columns[{i}][data]"] = ""
        params[f"columns[{i}][searchable]"] = "false"
    total = None
    offset = 0
    while total is None or offset < total:
        page = offset // 10 + 1
        source = f"komir-mine-grid-{page:03d}"
        query = dict(params, draw=page, start=offset)
        if archive.has(source):
            result = json.loads((RAW / archive.entries[source]["file"]).read_bytes())
        else:
            response = session.post(MINE_QUERY, data=query, headers=headers, timeout=40)
            response.raise_for_status()
            result = response.json()
        count = int(result["recordsTotal"])
        grid = result["data"]
        if count <= 0 or (total is not None and total != count) or len(grid) != min(10, count - offset):
            raise ValueError("The public mine grid changed between pages")
        if any(len(row) != len(fields) for row in grid):
            raise ValueError("Mine response included unexpected fields")
        if source not in archive.entries:
            archive.save(source, f"04/mines/komir-mine-grid-{page:03d}.json", response.content,
                         title=f"국내광산검색 결과 {page}쪽", publisher="한국광해광업공단",
                         vintage=None, url=response.url, license="미확인", catalog_url=MINE_PAGE,
                         method="POST", page=page, columns=fields)
        total = count
        offset += len(grid)


def business(session, archive):
    direct(session, archive, "daegu-business-2024", "03/daegu-business-2024.pdf",
           "https://stat.daegu.go.kr/cmm/fms/FileDown.do?atchFileId=FILE_000000000022281&fileSn=1",
           "2024년 기준 사업체조사 보고서", "대구광역시", 2024, b"%PDF", catalog=DAEGU_BUSINESS)
    direct(session, archive, "ulsan-business-2024", "03/ulsan-business-2024.pdf",
           "https://www.ulsan.go.kr/s/cmm/fms/FileDown.do?atchFileId=FILE_000000000187505&fileSn=0",
           "2024년 기준 사업체조사 보고서", "울산광역시", 2024, b"%PDF", catalog=ULSAN_BUSINESS)
    source = "incheon-manufacturing-2022"
    if archive.has(source):
        return
    catalog = "https://www.data.go.kr/data/15055167/fileData.do"
    response = session.get("https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003646708&fileDetailSn=1",
                           headers={"Referer": catalog}, timeout=40)
    response.raise_for_status()
    if not response.content.decode("cp949").startswith("군구별,제조업중분류별,"):
        raise ValueError("Unexpected Incheon manufacturing download")
    archive.save(source, "03/incheon-manufacturing-2022.csv", response.content,
                 title="제조업 중분류별 사업체수 및 종사자수_20221231", publisher="인천광역시",
                 url=response.url, vintage=2022, license="이용허락범위 제한 없음", catalog_url=catalog)


def seoul_business(session, archive):
    source = "seoul-business-census-2024"
    if archive.has(source):
        return
    params = {"infId": "OA-20326", "seqNo": "", "seq": "34", "infSeq": "3"}
    response = session.post(SEOUL_FILES, data=params, headers={"Referer": SEOUL_BUSINESS}, timeout=75)
    response.raise_for_status()
    if not response.content.startswith(b"PK\x03\x04"):
        raise ValueError("Seoul business survey download did not return a ZIP")
    archive.save(source, "03/seoul-business-census-2024.zip", response.content,
                 title="서울시 사업체조사 결과 정보(2024년 기준)", publisher="서울특별시",
                 url=response.url, vintage=2024, license="미확인", catalog_url=SEOUL_BUSINESS,
                 method="POST", query=params)


def regional_publications(session, archive):
    direct(session, archive, "gyeongbuk-business-2024", "03/gyeongbuk-business-2024.xlsx",
           "https://www.gb.go.kr/invest/Common/board_egov/download.jsp?B_STEP=260567300&B_ORDER=1",
           "2024년 기준 시군별 산업세세분류별 현황", "경상북도", 2024, b"PK\x03\x04",
           catalog=GYEONGBUK_BUSINESS)
    direct(session, archive, "chungnam-business-2024", "03/chungnam-business-2024.pdf",
           "https://alldam.chungnam.go.kr/board/download.chungnam?boardId=BBS_0000026"
           "&menuCd=DOM_000000202007001006&paging=ok&startPage=1&dataSid=2323&command=update&fileSid=3118",
           "2024년 기준 사업체조사 보고서", "충청남도", 2024, b"%PDF", catalog=CHUNGNAM_BUSINESS)
    source = "sejong-business-2024"
    if archive.has(source):
        return
    page = session.get(SEJONG_BUSINESS, timeout=30)
    page.raise_for_status()
    form = BeautifulSoup(page.content, "html.parser").select_one('form[name="fileFrm"]')
    params = {field["name"]: field.get("value", "") for field in form.select("input[name]")}
    params.update(key="2111", type="bbs", accSn="705")
    response = session.post("https://www.sejong.go.kr/stat/cmm/fileDown.do", data=params,
                            headers={"Referer": SEJONG_BUSINESS}, timeout=40)
    response.raise_for_status()
    if not response.content.startswith(b"PK\x03\x04"):
        raise ValueError("Sejong business survey did not return a ZIP")
    archive.save(source, "03/sejong-business-2024.zip", response.content,
                 title="2024년 기준 전국사업체조사 통계표", publisher="세종특별자치시",
                 url=response.url, vintage=2024, license="미확인", catalog_url=SEJONG_BUSINESS,
                 method="POST", query={key: params[key] for key in ("key", "type", "accSn")})


def institutions(session, archive):
    failures = []
    for source, (title, kind, url, locality) in INSTITUTIONS.items():
        source = f"institution-{source}"
        if archive.has(source):
            continue
        try:
            try:
                response = session.get(url, timeout=30)
            except ConnectionError:
                time.sleep(1.2)
                response = session.get(url, timeout=30)
            response.raise_for_status()
            page = BeautifulSoup(response.content, "html.parser")
            if locality not in " ".join(page.stripped_strings):
                raise ValueError(f"Published address not found: {title}")
            archive.save(source, f"04/institutions/{source}.html", response.content,
                         title=title, publisher=title, url=response.url, vintage=None,
                         license="미확인", kind=kind)
        except (ValueError, OSError, RuntimeError) as error:
            failures.append(f"{title}: {error}")
    if failures:
        raise ValueError(" | ".join(failures))


def research_funding(session, archive):
    source = "academyinfo-research-funding-2026"
    if archive.has(source):
        return
    page_url = ACADEMY + "list.do"
    session.get(page_url, timeout=30).raise_for_status()
    headers = {"Referer": page_url, "X-Requested-With": "XMLHttpRequest"}
    # Item 150, school-level view, four-year universities, disclosure year 2026.
    query = {"itemDivCd": "01", "svyYr": "", "fp": "", "fn": "", "sn": "",
             "all": ["150^^10", "150^^2026", "150^^02^^2026"]}
    response = session.post(ACADEMY + "selectReqList.do", data=query, headers=headers, timeout=35)
    response.raise_for_status()
    item, = response.json()["resultList1"]
    if item["colvalue1"] != "2026" or "연구비 수혜 실적_학교별자료.xlsx" not in item["colvalue13"]:
        raise ValueError("University funding item missing from the public file selection")
    selected = f"{item['colvalue2']}^^{item['colvalue12']}^^{item['colvalue13']}"
    # The public download asks for category and use. It accepts these generic options.
    form = dict(schlDivCd="02", itemDivCd="02", svyYr="", all="02", fp="", fn="", sn="",
                dwldUsrDivCd="004", dwldPrpsCd="003", sel=selected)
    response = session.post(ACADEMY + "selectReqRst.do", data=form, headers=headers, timeout=45)
    response.raise_for_status()
    state = response.json()["resultList"]
    if str(state["exist"]) != "1":
        raise ValueError("University funding file is unavailable for public download")
    form.update({key: state[key] for key in ("fp", "fn", "sn")})
    response = session.post(ACADEMY + "download.do", data=form, headers={"Referer": page_url}, timeout=45)
    response.raise_for_status()
    if not response.content.startswith(b"PK\x03\x04"):
        raise ValueError("University funding download was not a ZIP")
    archive.save(source, "06/university-research-funding-disclosure-2026.zip", response.content,
                 title="2026년 대학 연구비 수혜 실적 학교별자료", publisher="대학알리미",
                 url=response.url, vintage="2026년 공시", license="미확인", catalog_url=page_url,
                 method="POST", query=query, workbook=item["colvalue13"])


def main():
    collectors = {"road": road, "park": park, "dam": dam, "heritage": heritage, "mines": mines,
                  "business": business, "seoul": seoul_business, "institutions": institutions,
                  "funding": research_funding, "regional": regional_publications}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("groups", nargs="*", metavar="GROUP")
    args = parser.parse_args()
    groups = args.groups or list(collectors)
    if set(groups) - collectors.keys():
        parser.error("Groups: " + ", ".join(collectors))
    archive = LayerArchive()
    failures = []
    with PublicSession() as session:
        session.delay = 1.2
        for group in groups:
            try:
                collectors[group](session, archive)
            except (ValueError, OSError, RuntimeError) as error:
                failures.append((group, str(error)))
    for group, error in failures:
        print(f"{group}: {error}", file=sys.stderr)
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())

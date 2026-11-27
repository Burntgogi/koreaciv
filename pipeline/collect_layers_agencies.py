"""Download files exposed by publisher sites linked from the national catalog."""
import argparse
import re
import site
import sys
from pathlib import Path
from urllib.parse import urljoin

if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

from collect_layers import AIRKOREA, Archive, DIRECT, LAW, PublicSession, direct_file

EPSIS = "https://epsis.kpx.or.kr/epsisnew/"
MAFRA = "https://data.mafra.go.kr/opendata/data/"
AIRPORTAL = "https://www.airportal.go.kr"
FISH = "https://www.nfqs.go.kr/hpmg/data/actionMarineGeographicForm.do?menuId=M0000230"
ROADS = "https://www.its.go.kr"
NLIC = "https://www.nlic.go.kr/nlic/"
AIP = "https://aim.koca.go.kr/eaipPub/Package/2026-11-25-AIRAC/html/eAIP/KR-AD-2.RKSI-en-GB.html"
DIRECT["fish-gi"] = ("C6/fish-gi.html", FISH, "수산물 지리적표시 등록현황",
                     "국립수산물품질관리원", "2024-09-05", None, FISH)
DIRECT["incheon-aip"] = ("C3/incheon-aip-20261125.html", AIP, "AIP RKSI AD 2",
                        "국토교통부 항공정보관리", "2026-11-25", None, AIP)


def generators(session, archive):
    source_id = "epsis-generators"
    if archive.has(source_id):
        return
    page_url = EPSIS + "selectEkpoBcrGrid.do?menuId=020901"
    page = session.get(page_url, timeout=30)
    date = re.search(r"기준일자:\s*(\d{4}-\d{2}-\d{2})", page.text)[1]
    if date != "2026-08-05":
        raise ValueError(f"EPSIS snapshot changed: {date}")
    method_url = re.search(r"url\s*:\s*'([^']*selectEkpoBcr\.ajax[^']*)'", page.text)[1]
    response = session.post(urljoin(page_url, method_url), data={
        "menuId": "020901", "srchDate": "", "selMemgubun": "", "selTelgramform": "",
        "selGensource": "", "selGentype": "", "selRegion": "", "selBusiType": "",
    }, headers={"Referer": page_url, "X-Requested-With": "XMLHttpRequest"}, timeout=60)
    if b"gridData.push" not in response.content:
        raise ValueError("EPSIS did not return any generator records")
    archive.save(source_id, "C1/generators-20260805.txt", response.content,
                 title="발전기 현황", publisher="한국전력거래소",
                 url=EPSIS + "selectEkpoBcr.ajax", vintage=date, catalog_url=page_url,
                 method="POST", license_note="공공데이터포털 이용허락범위 제한 없음")


def farm_gi(session, archive):
    source_id = "mafra-farm-gi"
    if archive.has(source_id):
        return
    data_id = "20220204000000001691"
    page_url = MAFRA + f"indexOpenDataDetail.do?data_id={data_id}"
    page = session.get(page_url, timeout=30)
    if f"filedownload('{data_id}', 'file', '9')" not in page.text:
        raise ValueError("2026-03-17 file is no longer offered")
    response = session.post(MAFRA + "downloadOpenDataWebFile.do", data={
        "data_id": data_id, "file_ty_code": "file", "file_sn": "9", "preview_ty_code": "prew",
    }, headers={"Referer": page_url}, timeout=30)
    if not response.headers.get("Content-Disposition"):
        raise ValueError("Publisher did not return the CSV attachment")
    archive.save(source_id, "C6/farm-gi-20260317.csv", response.content,
                 title="지리적표시 관리정보", publisher="국립농산물품질관리원",
                 url=response.url, vintage="2026-03-17", catalog_url=page_url,
                 method="POST", file_sn=9, license_note="공공데이터포털 이용허락범위 제한 없음")


def fish_gi(session, archive):
    direct_file(session, archive, "fish-gi")
    missing = [page for page in (2, 3) if not archive.has(f"fish-gi-{page}")]
    if not missing:
        return
    session.get(FISH, timeout=30)
    for page in missing:
        params = {"MENU_ID": "M0000230", "page": str(page), "CERT_SEARCH_TYPE": "3", "CERT_SEARCH": ""}
        response = session.post(FISH, data=params, headers={"Referer": FISH}, timeout=30)
        if "등록번호" not in response.text:
            raise ValueError(f"Fisheries registration page {page} did not contain its table")
        archive.save(f"fish-gi-{page}", f"C6/fish-gi-{page}.html", response.content,
                     title="수산물 지리적표시 등록현황", publisher="국립수산물품질관리원",
                     url=response.url, vintage="2024-09-05", catalog_url=FISH,
                     method="POST", query=params)


def airport_traffic(session, archive):
    direct_file(session, archive, "incheon-aip")
    source_id = "airportal-2025"
    if archive.has(source_id):
        return
    page_url = AIRPORTAL + "/stats/transport/chartDetail2.do"
    session.get(page_url, timeout=30)
    query = {
        "last_yearmonth": "202501", "this_yearmonth": "202512", "sn_gubun": "total",
        "pass_gubun": "4", "carge_gubun": "total", "airport_gubun": "total",
        "di_gubun": "total", "pyn_gubun": "total", "arvl_type": "total",
    }
    response = session.post(AIRPORTAL + "/stats/transport/getDetailedAirTransportStats2Excel.do",
                            json=query, headers={"Referer": page_url, "request-call": "web-rest"},
                            timeout=60)
    if not response.content.startswith(b"PK\x03\x04"):
        raise ValueError("Public export did not return an XLSX")
    archive.save(source_id, "C3/airport-2025.xlsx", response.content,
                 title="항공통계 상세조회(공항)", publisher="국토교통부 항공정보포털",
                 url=response.url, vintage="2025", catalog_url=page_url,
                 method="POST", query=query, license_note="공공데이터포털 이용허락범위 제한 없음")


def roads(session, archive):
    import truststore

    truststore.inject_into_ssl()
    source_id = "its-nodelink-20261111"
    page_url = ROADS + "/nodelink/nodelinkRef"
    DIRECT[source_id] = (
        "C4/nodelink-20261111.zip", ROADS + "/opendata/nodelinkFileSDownload/DF_222/0",
        "전국표준노드링크", "국토교통부 국가교통정보센터", "2026-11-11", None, page_url,
    )
    session.get(page_url, timeout=30)
    session.headers["Referer"] = page_url
    direct_file(session, archive, source_id)


def laws(session, archive):
    editions = (
        ("border-article", "C11/border-article.html", "접경지역지원특별법시행령",
         "접경지역 지원 특별법 시행령", "269703", "20250311", "고양시"),
        ("border-act", "C11/border-act.html", "접경지역지원특별법",
         "접경지역 지원 특별법", None, None, "접경지역"),
        ("special-city-act", "B7/special-city-act.html", "전남광주통합특별시설치를위한특별법",
         "전남광주통합특별시 설치를 위한 특별법", "285923", "20261113", "무안청사"),
    )
    for source_id, file, slug, title, sequence, date, check in editions:
        if archive.has(source_id):
            continue
        page_url = LAW + slug
        page = session.get(page_url, timeout=30)
        if sequence is None:
            from bs4 import BeautifulSoup

            document = BeautifulSoup(page.content, "html.parser")
            sequence = document.select_one("#frm_lsiSeq")["value"]
            date = document.select_one("#frm_efYd")["value"]
        payload = {
            "lsiSeq": sequence, "efYd": date, "efYn": "Y", "chrClsCd": "010202",
            "nwJoYnInfo": "Y", "ancYnChk": "0", "netPrivateYn": "N",
        }
        response = session.post("https://www.law.go.kr/LSW/lsInfoR.do", data=payload,
                                headers={"Referer": page.url}, timeout=30)
        if check not in response.text or len(response.content) < 1000:
            raise ValueError(f"Official law text missing: {title}")
        archive.save(source_id, file, response.content, title=title,
                     publisher="법제처 국가법령정보센터", url=response.url,
                     vintage=date, catalog_url=page.url, method="POST", query=payload)


def air_stations(session, archive):
    source_id = "airkorea-stations"
    if archive.has(source_id):
        return
    page_url = AIRKOREA + "/web/stationInfo?pMENU_NO=93"
    session.get(page_url, timeout=30)
    query = {"action": "station", "districtnum": "", "stationCode": "", "numValue": "",
             "loading": "yes", "leftShow": "realTime", "pMENU_NO": "93", "mang_code": "1",
             "district": ""}
    result = session.post(AIRKOREA + "/web/stationInfo/getRealExcel", data=query,
                          headers={"Referer": page_url}, timeout=30)
    if not result.content.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        raise ValueError("Station list did not download as XLS")
    archive.save(source_id, "D2/stations-network-1.xls", result.content, title="에어코리아 측정소 정보(측정망 1)",
                 publisher="한국환경공단 에어코리아", url=result.url,
                 catalog_url=page_url, method="POST", query=query)


def port_tonnage(session, archive):
    source_id = "nlic-ports-2025"
    if archive.has(source_id):
        return
    page_url = NLIC + "seaHarborGtqy.action"
    session.get(page_url, timeout=30)
    query = {"srchYear": "2025", "srchMonth": "12", "srchHbCode": ""}
    result = session.post(NLIC + "seaHbGtqyExcel.action", data=query,
                          headers={"Referer": page_url}, timeout=30)
    if not result.headers.get("Content-Disposition"):
        raise ValueError("NLIC port-tonnage export did not return an attachment")
    archive.save(source_id, "C2/port-tonnage-2025.xls", result.content,
                 title="항만별 물동량 통계", publisher="해양수산부 국가물류통합정보센터",
                 url=result.url, catalog_url=page_url, vintage="2025-12", method="POST", query=query)


def fiscal_independence(session, archive):
    source_id = "lofin-fiscal-2026"
    if archive.has(source_id):
        return
    base = "https://www.lofin365.go.kr"
    page_url = base + "/portal/LF3110300.do?tab=retvLstBysdSitu&jiPyo=01&srchYr=2026&rgnzDvCd=02"
    session.get(page_url, timeout=30)
    endpoint = base + "/lf/lnncGramStst/pfinIndc/firSvi/retvLstFirBysdSitu.do"
    query = {"srchYr": "2026", "rgnzDvCd": "02", "jiPyo": "01", "srchDvCd": "01"}
    response = session.post(endpoint, json=query,
                            headers={"Referer": page_url, "X-Requested-With": "XMLHttpRequest"},
                            timeout=30)
    if not response.json().get("firBysdSituIxInqRsltDto"):
        raise ValueError("Lofin did not return province fiscal-independence rates")
    archive.save(source_id, "../econ/official_totals/fiscal-independence-2026.json", response.content,
                 title="재정자립도[당초] 시도별 현황", publisher="행정안전부 지방재정365",
                 url=response.url, vintage="2026", catalog_url=page_url, method="POST", query=query)


def main():
    actions = {"generators": generators, "farm-gi": farm_gi, "airports": airport_traffic,
               "fish-gi": fish_gi, "roads": roads, "laws": laws, "air-stations": air_stations,
               "port-tonnage": port_tonnage, "fiscal-independence": fiscal_independence}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("targets", nargs="*", metavar="TARGET")
    args = parser.parse_args()
    failed = False
    for name in args.targets or actions:
        try:
            with PublicSession() as session:
                actions[name](session, Archive())
        except (OSError, ValueError, TypeError, KeyError) as error:
            failed = True
            print(f"{name}: {error}", flush=True)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())

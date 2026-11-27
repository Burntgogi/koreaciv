"""Archive official Sejong, Seoul and Welfare Ministry publications and files."""
import argparse
import io
import re
import zipfile
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import RequestException

from collect_econ_web import Archive, PublicSession, SiteBlocked

PAGE = "https://www.sejong.go.kr/stat/bbs/statsYearList.do?key=1910168795947"
WELFARE_PAGE = "https://www.korea.kr/archive/expDocView.do?docId=41874"
SEOUL_PAGE = "https://data.seoul.go.kr/bsp/wgs/dataView/data300View/10160.do"
SEOUL_DOWNLOAD = "https://data.seoul.go.kr/bsp/wgs/dataset/download/"
JEONNAM_SURVEY = "https://www.jeonnam.go.kr/M4703/boardView.do?menuId=jeonnam0508010000&seq="
JEONNAM_POSTS = {2024: ("1863943", "사업체조사 결과 보고서.zip"), 2019: ("1863938", "통계표(엑셀).zip")}
CHUNGBUK_SURVEY = "https://www.chungbuk.go.kr/stat/selectBbsNttView.do?key=1409&bbsNo=184&nttNo="
CHUNGBUK_POSTS = {2024: ("415240", "사업체조사 통계표.zip"), 2019: ("171325", "사업체조사(통계표).zip")}
JEONBUK_SURVEY = "https://stat.jeonbuk.go.kr/html/sub3/index3_2.jsp?b_idx=9&gubun=view&page=1&bd_idx="
JEONBUK_POSTS = {2024: ("1569", "사업체조사 통계표.zip")}
JEJU_SURVEY = "https://www.jeju.go.kr/stats/mdis/report/company.htm?act=view&seq="
JEJU_POSTS = {2024: ("2002614", "사업체조사 통계표 1~9.zip"), 2019: ("1304415", "사업체조사 통계표(확정).zip")}
GG_REPORT = "https://data.gg.go.kr/portal/stat/dataMng/"
GG_BUSINESS_PAGE = GG_REPORT + "publicationPage.do?infId=542"
GG_BUSINESS_YEARS = {2024: "10635", 2019: "5434"}


def download():
    with PublicSession() as session:
        page = session.get(PAGE, timeout=45)
        page.raise_for_status()
        buttons = BeautifulSoup(page.content, "html.parser").select("button.annual-btn.file")
        button = next(b for b in buttons if "제13회" in b.get("title", ""))
        link = re.search(r"window\.open\('([^']+)'", button["onclick"])[1]
        url = urljoin(PAGE, link)
        response = session.get(url, timeout=120)
        response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as container:
        names = container.namelist()
        print(*(name for name in names if re.search(r"총생산|사업체|재정|의료|농림", name)), sep="\n")
    Archive().save("sejong-yearbook-2024", "grdp/sejong-yearbook-2024.zip", response.content,
                   title="제13회 세종통계연보", publisher="세종특별자치시", url=url, catalog_url=PAGE,
                   vintage=2024, table_id="208002")


def download_welfare():
    with PublicSession() as session:
        page = session.get(WELFARE_PAGE, timeout=45)
        page.raise_for_status()
        attachment = next(a for a in BeautifulSoup(page.content, "html.parser").select("a[href]")
                          if "2025년 국민기초생활보장 수급자 현황.pdf" in a.get_text())
        url = urljoin(WELFARE_PAGE, attachment["href"])
        result = session.get(url, timeout=90)
        result.raise_for_status()
    if not result.content.startswith(b"%PDF-"):
        raise ValueError("Expected the PDF attachment")
    Archive().save("mohw-welfare-2025", "assistance/mohw-welfare-2025.pdf", result.content,
                   title="2025년 국민기초생활보장 수급자 현황", publisher="보건복지부",
                   url=url, catalog_url=WELFARE_PAGE, vintage=2025,
                   license_note="정책브리핑 게시문 텍스트에 공공누리 제4유형 표시. 첨부의 별도 조건 미확인")


def download_seoul():
    with PublicSession() as session:
        page = session.get(SEOUL_PAGE, timeout=35)
        page.raise_for_status()
        session.headers.update({"Referer": SEOUL_PAGE, "Accept": "application/json",
                                "X-Requested-With": "XMLHttpRequest"})
        listing = session.get(SEOUL_DOWNLOAD + "list/10160", timeout=35)
        listing.raise_for_status()
        if len(listing.json()["downloadList"]) != 1:
            raise ValueError("Unexpected Seoul download list")
        response = session.get(SEOUL_DOWNLOAD + "10160", timeout=35)
        response.raise_for_status()
        url = response.json()["downloadURL"]
        with PublicSession() as files:
            result = files.get(url, timeout=100)
            result.raise_for_status()
    if not zipfile.is_zipfile(io.BytesIO(result.content)):
        raise ValueError("Expected a Seoul ZIP attachment")
    Archive().save("seoul-business-10160", "business/seoul-business-10160.zip", result.content,
                   title="사업소 특성별 산업대분류별 구·동별 현황", publisher="서울특별시",
                   url=url.split("?")[0], catalog_url=SEOUL_PAGE, vintage=[2015, 2023],
                   table_id="10160", license="자유이용 불가")


def download_regional_business(slug, publisher, base, posts):
    with PublicSession() as session:
        for year, (post, attachment) in posts.items():
            source = f"{slug}-business-{year}"
            archive = Archive()
            if archive.has(source):
                continue
            page_url = base + post
            page = session.get(page_url, timeout=40)
            page.raise_for_status()
            soup = BeautifulSoup(page.content, "html.parser")
            button = next(a for a in soup.select("a[href]")
                          if attachment in a.get("title", "") or attachment in a.get_text(" ", strip=True))
            url = urljoin(page_url, button["href"])
            response = session.get(url, timeout=90)
            response.raise_for_status()
            if not zipfile.is_zipfile(io.BytesIO(response.content)):
                raise ValueError(f"Expected a ZIP attachment for {year}")
            with zipfile.ZipFile(io.BytesIO(response.content)) as container:
                print(year, container.namelist()[:20], flush=True)
            archive.save(source, f"business/{source}.zip", response.content,
                         title=f"{year}년 기준 {publisher} 사업체조사 통계표",
                         publisher=publisher, vintage=year, url=url, catalog_url=page_url,
                         table_id=post)


def download_business_surveys():
    download_regional_business("jeonnam", "전라남도", JEONNAM_SURVEY, JEONNAM_POSTS)
    download_regional_business("chungbuk", "충청북도", CHUNGBUK_SURVEY, CHUNGBUK_POSTS)
    download_regional_business("jeonbuk", "전북특별자치도", JEONBUK_SURVEY, JEONBUK_POSTS)
    download_regional_business("jeju", "제주특별자치도", JEJU_SURVEY, JEJU_POSTS)
    download_gyeonggi_business()


def download_gyeonggi_business():
    with PublicSession() as session:
        page = session.get(GG_BUSINESS_PAGE, timeout=40)
        page.raise_for_status()
        soup = BeautifulSoup(page.content, "html.parser")
        purpose = soup.select_one('input[name="statDsUsePurpsCd"][data-action-name="연구·학습 활용"]')
        for year, category in GG_BUSINESS_YEARS.items():
            source = f"gyeonggi-business-{year}"
            archive = Archive()
            if archive.has(source):
                continue
            report = session.get(GG_REPORT + "searchStatReportSubMenuList.do",
                                 params={"infId": category}, timeout=40)
            report.raise_for_status()
            table = next(row for row in report.json()
                         if row["pubFname"].startswith("2. 산업소분류") and row["pubFileNm"].endswith(".xls"))
            table_id = str(table["pubSeq"])
            confirmation = session.post(
                "https://data.gg.go.kr/portal/data/sheet/saveInfUsePurp.do",
                data={"infId": table_id, "dsUsePurpsCd": purpose["data-action-code"], "dsUsePurps": ""},
                headers={"Origin": "https://data.gg.go.kr", "Referer": GG_BUSINESS_PAGE}, timeout=40,
            )
            confirmation.raise_for_status()
            url = GG_REPORT + "publicationFileDownload.do?infId=" + table_id
            response = session.get(url, timeout=60)
            response.raise_for_status()
            if not response.content.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
                raise ValueError(f"Expected the published XLS workbook for {year}")
            archive.save(source, f"business/{source}.xls", response.content,
                         title=table["pubFname"], publisher="경기도", vintage=year,
                         url=url, catalog_url=GG_BUSINESS_PAGE, table_id=table_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--business-surveys", action="store_true")
    args = parser.parse_args()
    failed = False
    collectors = (download_business_surveys,) if args.business_surveys else (download, download_welfare, download_seoul)
    for collect in collectors:
        try:
            collect()
        except (OSError, RequestException, SiteBlocked, ValueError) as error:
            failed = True
            print(f"{collect.__name__}: {error}", flush=True)
    raise SystemExit(int(failed))

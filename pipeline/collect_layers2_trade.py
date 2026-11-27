"""Collect the 2025 customs portal regional overview using its public search form."""

import argparse
import site
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

from bs4 import BeautifulSoup
from collect_layers2 import LayerArchive, PublicSession

HOME = "https://tradedata.go.kr/cts/index.do"
BASE = "https://tradedata.go.kr/cts/hmpg/"
OVERVIEW = "openETS0100026Q.do"
QUERY = "retrieveTradeRegionAll.do"
YEAR = "2025"
HS2_MENU = "openETS0100027Q.do"
HS2_QUERY = "retrieveTradeRegion.do"
HS2_DOWNLOAD = "downloadTradeRegionJson.do"


def filters(code):
    return dict(sidosggKind="sgg", priodKind="YEAR", priodFr=YEAR, priodTo=YEAR,
                statsBase="acptDd", sidoCd=code, sggCd="%", selectPaging="1",
                showPagingLine="100", sortColumn="", sortOrder="")


def menu(session, endpoint, menu_id):
    response = session.post(BASE + endpoint, data={"menuId": menu_id}, timeout=45)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


def collect_hs2(session, archive, provinces):
    page = menu(session, HS2_MENU, "ETS_MNK_10400000")
    if not page.select_one("#radioSgg"):
        raise ValueError("Customs portal regional detail did not open")
    for code, province in provinces.items():
        source = f"customs-trade-hs2-{YEAR}-{code}"
        if archive.has(source):
            continue
        params = dict(filters(code), tradeKind="ETS_MNK_1040000A", imexTpcd="EXP_TMPR_CD",
                      hsSgnGrpCol="HS2_SGN", hsSgnWhrCol="HS2_SGN", hsSgn="", subHsSgn="N")
        response = session.post(BASE + HS2_QUERY, data=params, timeout=55)
        response.raise_for_status()
        count = int(response.json()["count"])
        if not 1 < count <= 100000:
            raise ValueError(f"HS2 result unavailable for export: {province}, {count}")
        params.update(isAllExcel="YES", xlsxFileNm="품목별 수출입통계 현황", xlsxSellMerge="A1:I1",
                      xlsxUnit=" 건, 천 달러", xlsxUnitPosition="8",
                      xlsxSearch=f"지역명 : {province} 전체, 조회기간 : {YEAR}, 통계기준 : 수리일",
                      xlsxHeards="priodTitle:기간:6000,sggNm:시도명:6000,hsSgn:HS코드:6000,"
                      "korePrlstNm:HS코드명:8000,expCnt:수출건수:6000,expUsdAmt:수출금액:6000,"
                      "impCnt:수입건수:6000,impUsdAmt:수입금액:6000,cmtrBlncAmt:무역수지:6000")
        response = session.post(BASE + HS2_DOWNLOAD, data=params, timeout=75)
        response.raise_for_status()
        result = response.json()
        if len(result.get("items", [])) != count:
            raise ValueError(f"HS2 export is incomplete: {province}, {result.get('message', '')}")
        archive.save(source, f"01/trade-hs2-{YEAR}-{code}.json", response.content,
                     title=f"{YEAR}년 {province} 시군구별 HS 2단위 수출입 실적", publisher="관세청",
                     url=response.url, catalog_url=HOME, vintage=YEAR, license="미확인",
                     method="POST", query=params, province=province, unit="천 달러")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hs2", action="store_true", help="Also export HS 2-digit regional trade")
    args = parser.parse_args()
    archive = LayerArchive()
    prefixes = [f"customs-trade-sgg-{YEAR}-"]
    if args.hs2:
        prefixes.append(f"customs-trade-hs2-{YEAR}-")
    cached = [[source for source in archive.entries if source.startswith(prefix)] for prefix in prefixes]
    if all(len(group) == 17 and all(archive.has(source) for source in group) for group in cached):
        return
    with PublicSession() as session:
        session.get(HOME, timeout=30).raise_for_status()
        session.headers.update({"Referer": HOME, "X-Requested-With": "XMLHttpRequest"})
        page = menu(session, OVERVIEW, "ETS_MNK_10300000")
        if not page.select_one("#radioSgg") or not page.select_one('input[value="acptDd"]'):
            raise ValueError("Customs portal regional overview did not open")
        # 2025 predates the new combined province option.
        provinces = {option["value"]: option.get_text(strip=True)
                     for option in page.select("#ETS0100026Q_sidoCd option")
                     if option["value"] not in {"%", "12"}}
        if len(provinces) != 17:
            raise ValueError("Unexpected province selection list")
        for code, province in provinces.items():
            source = f"customs-trade-sgg-{YEAR}-{code}"
            if archive.has(source):
                continue
            params = filters(code)
            response = session.post(BASE + QUERY, data=params, timeout=45)
            response.raise_for_status()
            result = response.json()
            entries = result["items"]
            if len(entries) <= 1 or int(result["count"]) != len(entries):
                raise ValueError(f"Missing or paginated results for {province}: {result.get('count')}")
            archive.save(source, f"01/trade-sgg-{YEAR}-{code}.json", response.content,
                         title=f"{YEAR}년 {province} 시군구별 수출입 총괄", publisher="관세청",
                         url=response.url, catalog_url=HOME, vintage=YEAR, license="미확인",
                         method="POST", query=params, province=province, unit="천 달러")
        if args.hs2:
            collect_hs2(session, archive, provinces)


if __name__ == "__main__":
    main()

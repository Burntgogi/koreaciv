"""Export the monthly cattle stock table through the public Mtrace CSV workflow."""

import csv
import json
import site
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

from bs4 import BeautifulSoup
from collect_layers2 import LayerArchive, PublicSession

BASE = "https://www.mtrace.go.kr/statHtml/"
TABLE = "DT_323901_A100000004"
MONTH = "202610"
PAGE = BASE + f"statHtml.do?orgId=323&conn_path=I2&tblId={TABLE}"
SOURCE = "mtrace-hanwoo-202610"
PIG_TABLE = "DT_1EO311"
PIG_PERIOD = "202603"
PIG_PAGE = BASE + f"statHtml.do?orgId=323&conn_path=I2&tblId={PIG_TABLE}"
PIG_SOURCE = "mtrace-pig-sido-2026q3"


def form_for(session, page_url):
    response = session.get(page_url, timeout=30)
    response.raise_for_status()
    page = BeautifulSoup(response.content, "html.parser")
    form = {x["name"]: x.get("value", "") for x in page.select("#ParamInfo input[name]")}
    session.headers["Referer"] = page_url
    return page, form


def download(session, form, fields, row_axis, col_axis):
    form.update(fieldList=json.dumps([dict(targetId=key, targetValue=val, prdValue=period)
                                      for key, val, period in fields]),
                rowAxis=row_axis, colAxis=col_axis, dataOpt="cdko", view="csv",
                viewKind="2", viewSubKind="2_3", smblYn="N")
    ajax = {"X-Requested-With": "XMLHttpRequest"}
    response = session.post(BASE + "downGrid.do", data=form, headers=ajax, timeout=50)
    response.raise_for_status()
    form["file"] = response.json()["file"]
    response = session.post(BASE + "downNormal.do", data=form, timeout=50)
    response.raise_for_status()
    content = response.content
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeError:
        decoded = content.decode("cp949")
    return response, decoded


def hanwoo(session, archive):
    if archive.has(SOURCE):
        return
    page, form = form_for(session, PAGE)
    breed = page.select_one('input[name="classChkLi1_1"][title="한우"]')["value"].rstrip("=")
    sex = page.select_one('input[name="classChkLi2_1"][title="전체"]')["value"].rstrip("=")
    indicator = page.select_one('input[name="itemChkLi"][title="사육두수"]')["value"]
    ajax = {"X-Requested-With": "XMLHttpRequest"}
    geography = dict(lvl="2", objVarId="C", searchCondition="A", orgId=form["orgId"],
                     tblId=TABLE, dataOpt="ko", language="ko", pub="", dbUser=form["dbUser"], st="")
    response = session.post(BASE + "classDivSelect.do", data=geography, headers=ajax, timeout=40)
    response.raise_for_status()
    levels, = response.json()["result"]
    fields = [("PRD", "", f"M,{MONTH},@"), ("ITM_ID", indicator, ""),
              ("OV_L1_ID", breed, ""), ("OV_L2_ID", sex, "")]
    fields.extend(("OV_L3_ID", code, "") for code in levels["data"])
    response, decoded = download(session, form, fields, "C", "TIME,A,B")
    header = list(csv.reader(decoded.splitlines()[:4]))
    if len(header) != 4 or f"M{MONTH}" not in header[0][2] or not header[1][2].endswith(" 한우"):
        raise ValueError("Mtrace did not return the selected Hanwoo CSV")
    archive.save(SOURCE, "09/hanwoo-202610.csv", response.content, title=form["tblNm"],
                 publisher="축산물품질평가원", url=response.url, catalog_url=PAGE,
                 vintage=MONTH, license="미확인", method="POST",
                 query={"period": MONTH, "breed": "한우", "sex": "전체", "region_level": 2})


def pigs(session, archive):
    if archive.has(PIG_SOURCE):
        return
    page, form = form_for(session, PIG_PAGE)
    indicator = page.select_one('input[name="itemChkLi"][title="마리수"]')["value"]
    total = page.select_one('input[name="classChkLi2_1"][title="합계"]')["value"].rstrip("=")
    fields = [("PRD", "", f"Q,{PIG_PERIOD},@"), ("ITM_ID", indicator, ""), ("OV_L2_ID", total, "")]
    fields.extend(("OV_L1_ID", node["value"].rstrip("="), "")
                  for node in page.select('input[name="classChkLi1_1"]'))
    response, decoded = download(session, form, fields, "A,B", "TIME,ITEM")
    if f"Q{PIG_PERIOD}" not in decoded[:250] or "마리수" not in decoded[:350]:
        raise ValueError("Mtrace did not return the selected pig CSV")
    archive.save(PIG_SOURCE, "09/pig-sido-2026q3.csv", response.content, title=form["tblNm"],
                 publisher="국가데이터처 가축동향조사 (축산유통 통계누리)", url=response.url,
                 catalog_url=PIG_PAGE, vintage="2026-Q3", license="미확인", method="POST",
                 query={"period": PIG_PERIOD, "indicator": "마리수", "size": "합계", "region_level": 1})


def main():
    archive = LayerArchive()
    with PublicSession() as session:
        hanwoo(session, archive)
        pigs(session, archive)


if __name__ == "__main__":
    main()

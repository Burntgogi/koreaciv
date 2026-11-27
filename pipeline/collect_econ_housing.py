"""Download the public MOLIT apartment CSVs in nationwide calendar months."""
import argparse
import datetime as dt
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import RequestException

from collect_econ_web import Archive, PublicSession, SiteBlocked

PAGE = "https://rt.molit.go.kr/pt/xls/xls.do?mobileAt="
CHECK = "/pt/xls/ptXlsDownDataCheck.do"
DOWNLOAD = "/pt/xls/ptXlsCSVDown.do"


def download(start_month, end_month, force=False):
    archive = Archive()
    session = PublicSession()
    page = session.get(PAGE, timeout=45)
    page.raise_for_status()
    form = BeautifulSoup(page.content, "html.parser").select_one("#frm_xls")
    default = [(e["name"], e.get("value", "")) for e in form.select("input[name], select[name]")
               if not e.has_attr("disabled")]
    # The CSV form action can carry the public session ID from this page.
    action = re.search(r'(/pt/xls/ptXlsCSVDown\.do[^"\s]*)', page.text)[1]
    failures = []
    for deal, code in (("sale", "1"), ("lease", "2")):
        first = start_month
        while first <= end_month:
            next_month = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
            last = next_month - dt.timedelta(days=1)
            month = first.strftime("%Y-%m")
            source_id = f"molit-apartment-{deal}-{month}"
            if force or not archive.has(source_id):
                params = dict(srhFromDt=str(first), srhToDt=str(last), srhDelngSecd=code)
                fields = [(key, params.get(key, value)) for key, value in default]
                try:
                    check = session.post(urljoin(PAGE, CHECK), data=fields, timeout=60)
                    check.raise_for_status()
                    status = check.json()
                    if status.get("error") or not int(status.get("cnt", 0)):
                        raise ValueError(str(status))
                    labels = {"sidoNm": "전체", "sggNm": "전체", "emdNm": "전체",
                              "areaNm": "전체", "loadNm": "전체", "hsmpNm": "전체"}
                    result = session.post(urljoin(PAGE, action),
                                          data=[(key, labels.get(key, value)) for key, value in fields],
                                          timeout=120)
                    result.raise_for_status()
                    if "attachment" not in result.headers.get("Content-Disposition", "").lower():
                        raise ValueError(f"HTTP {result.status_code} without attachment")
                    archive.save(source_id, f"housing/{source_id}.csv", result.content,
                                 title=f"아파트 {'매매' if deal == 'sale' else '전월세'} 실거래가 {month}",
                                 publisher="국토교통부", url=urljoin(PAGE, DOWNLOAD),
                                 vintage=month, catalog_url=PAGE, deal=deal,
                                 license_note="조건별 자료제공 이용시 유의사항 참조")
                except (RequestException, ValueError) as error:
                    failures.append(source_id)
                    print(f"{source_id}: {error}", flush=True)
            first = next_month
    return int(bool(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first_month", help="YYYY-MM")
    parser.add_argument("last_month", help="YYYY-MM")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    try:
        raise SystemExit(download(dt.date.fromisoformat(args.first_month + "-01"),
                                  dt.date.fromisoformat(args.last_month + "-01"), args.force))
    except SiteBlocked as error:
        raise SystemExit(str(error))

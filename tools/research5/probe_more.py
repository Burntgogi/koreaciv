"""추가 공식·오픈 후보 출처 확인 및 다운로드 (표준데이터 15013205, OurAirports, 인천공항 누리집, 법령, 산림청/국토지리정보원/환경빅데이터, Zenodo CGLS-LC100 등).

실행: python -I tools/research5/probe_more.py
"""
import site
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

import json
import re
from urllib.parse import urlencode
from bs4 import BeautifulSoup
import probe_portal as PP

# 추가 허용 호스트 등록 (모두 HTTPS 검증 통과 대상)
PP.ALLOWED_HOSTS = PP.ALLOWED_HOSTS | {
    "ourairports.com",
    "www.bigdata-environment.kr",
    "bigdata-environment.kr",
    "developers.google.com",
    "www.eorc.jaxa.jp",
    "glad.umd.edu",
}


def main():
    sess = PP.Session()

    # 1. 전국도시철도역사정보표준데이터 (15013205) 전체 JSON 다운로드
    try:
        cols_meta = json.loads((PP.RAW5 / "portal/std-15013205-cols.json").read_text(encoding="utf-8"))
        cols = [c["columCode"] for c in cols_meta["columList"]]
        total_cnt = cols_meta["totalCount"]
        # portal-std-15013205.html 에서 svcTableNm 추출
        html_txt = (PP.RAW5 / "portal/portal-std-15013205.html").read_text(encoding="utf-8", errors="ignore")
        m_tbl = re.search(r"tn_pubr_[a-z0-9_]+", html_txt)
        tbl_nm = m_tbl[0] if m_tbl else "tn_pubr_public_urban_rail_statn_info_api"
        print(f"std-15013205 table={tbl_nm}, total={total_cnt}, cols={cols}", flush=True)
        q = [("publicDataPk", "15013205")] + [("colNmList", c) for c in cols] + [
            ("totalCount", str(total_cnt)), ("svcTableNm", tbl_nm), ("perPage", "10000"), ("page", "1")
        ]
        std_dl_url = "https://www.data.go.kr/download/standard.json?" + urlencode(q)
        _, std_data = sess.fetch("p1-std-15013205", "files/p1-std-15013205.json", std_dl_url,
                                 license_url="https://www.data.go.kr/data/15013205/standard.do")
        rows = json.loads(std_data.decode("utf-8"))
        print(f"std-15013205 downloaded {len(rows)} rows", flush=True)
        for r in rows:
            if "인천공항" in str(r) or "공항" in str(r.get("STATN_NM", "")):
                print("  MATCH std-15013205:", r, flush=True)
    except Exception as e:
        print(f"[err] std-15013205 download: {e}", flush=True)

    # 2. OurAirports airports.csv 및 라이선스 안내 페이지
    for key, rel, url, lurl in [
        ("ourairports-about", "files/ourairports-data.html", "https://ourairports.com/data/", "https://ourairports.com/data/"),
        ("ourairports-csv", "files/ourairports-airports.csv", "https://davidmegginson.github.io/ourairports-data/airports.csv", "https://ourairports.com/data/"),
    ]:
        try:
            _, data = sess.fetch(key, rel, url, license_url=lurl)
            if key == "ourairports-csv":
                for line in data.decode("utf-8", errors="ignore").splitlines():
                    if "RKSI" in line or "Incheon International" in line:
                        print("  MATCH OurAirports:", line[:220], flush=True)
            else:
                soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
                print("  OurAirports data page text:", " ".join(soup.get_text(" ", strip=True).split())[:600], flush=True)
        except Exception as e:
            print(f"[err] {key}: {e}", flush=True)

    # 3. 법제처 국가법령정보센터 인천국제공항공사법
    try:
        law_url = "https://www.law.go.kr/법령/인천국제공항공사법"
        _, page_b = sess.fetch("law-iiac-page", "portal/law-iiac-page.html", law_url, license_url="https://www.law.go.kr/법령/저작권법/제7조")
        soup = BeautifulSoup(page_b.decode("utf-8", errors="ignore"), "html.parser")
        seq = soup.select_one("#frm_lsiSeq")
        efyd = soup.select_one("#frm_efYd")
        if seq and efyd:
            payload = {"lsiSeq": seq["value"], "efYd": efyd["value"], "efYn": "Y", "chrClsCd": "010202", "nwJoYnInfo": "Y", "ancYnChk": "0", "netPrivateYn": "N"}
            _, body_b = sess.fetch("law-iiac-body", "portal/law-iiac-body.html", "https://www.law.go.kr/LSW/lsInfoR.do",
                                   license_url="https://www.law.go.kr/법령/저작권법/제7조", method="POST", data=payload, headers={"Referer": law_url})
            b_soup = BeautifulSoup(body_b.decode("utf-8", errors="ignore"), "html.parser")
            print("  인천국제공항공사법 본문 발췌:", " ".join(b_soup.get_text(" ", strip=True).split())[:500], flush=True)
    except Exception as e:
        print(f"[err] law-iiac: {e}", flush=True)

    # 4. 인천국제공항공사 공식 누리집 (airport.kr) 저작권정책 및 하단 주소 확인
    for key, url in [
        ("airport-kr-main", "https://www.airport.kr/ap_ko/index.do"),
        ("airport-kr-copyright", "https://www.airport.kr/ap_ko/6642/subview.do"),
    ]:
        try:
            _, b = sess.fetch(key, f"portal/{key}.html", url, license_url=url)
            soup = BeautifulSoup(b.decode("utf-8", errors="ignore"), "html.parser")
            txt = " ".join(soup.get_text(" ", strip=True).split())
            print(f"  {key}: {txt[:500]} ... {txt[-400:]}", flush=True)
        except Exception as e:
            print(f"[err] {key}: {e}", flush=True)

    # 5. 산림청 산림공간정보서비스(fgis.forest.go.kr / map.forest.go.kr), 국토지리정보원 국토정보플랫폼(map.ngii.go.kr), 환경 빅데이터 플랫폼, Zenodo CGLS-LC100
    other_checks = [
        ("fgis-forest", "https://map.forest.go.kr/forest/"),
        ("ngii-map", "https://map.ngii.go.kr/mn/mainPage.do"),
        ("env-bigdata", "https://www.bigdata-environment.kr/user/main.do"),
        ("zenodo-cgls-lc100", "https://zenodo.org/api/records/3939050"),
        ("dynamic-world-doc", "https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1"),
        ("jaxa-fnf-doc", "https://www.eorc.jaxa.jp/ALOS/en/dataset/fnf_e.htm"),
    ]
    for key, url in other_checks:
        try:
            ext = "json" if "api/records" in url else "html"
            _, b = sess.fetch(key, f"portal/{key}.{ext}", url, license_url=url)
            if ext == "json":
                j = json.loads(b.decode("utf-8"))
                print(f"=== {key}: title={j.get('metadata',{}).get('title')}, license={j.get('metadata',{}).get('license')} ===", flush=True)
                for f in j.get("files", []):
                    if "E120N40" in f.get("key", ""):
                        print(f"  file: {f['key']} ({f['size']:,} B) -> {f.get('links',{}).get('self')}", flush=True)
            else:
                soup = BeautifulSoup(b.decode("utf-8", errors="ignore"), "html.parser")
                txt = " ".join(soup.get_text(" ", strip=True).split())
                print(f"=== {key} ({len(b):,} B): {txt[:500]} ===", flush=True)
        except Exception as e:
            print(f"[err] {key}: {e}", flush=True)


if __name__ == "__main__":
    main()

"""후보 데이터셋 상세 페이지·메타데이터 조회 및 조건이 깨끗한 소형 파일 다운로드.

실행: python -I tools/research5/probe_details.py
"""
import site
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.extend([str(Path(__file__).resolve().parent), site.getusersitepackages()])

import json
import re
from bs4 import BeautifulSoup
from probe_portal import Session, parse_portal_detail


def download_portal_file(sess, pk, key_prefix, max_mb=60):
    """공공데이터포털 fileData.do 페이지에서 이용허락범위가 깨끗하면(제한 없음 또는 제1유형) 첨부 메타데이터를 확인하고 max_mb 이하일 때 내려받는다."""
    detail_url = f"https://www.data.go.kr/data/{pk}/fileData.do"
    _, html_bytes = sess.fetch(f"portal-{pk}", f"portal/portal-{pk}.html", detail_url, license_url=detail_url)
    text = html_bytes.decode("utf-8", errors="ignore")
    soup = BeautifulSoup(text, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else str(pk)
    label = soup.find(string=lambda x: x and x.strip() == "이용허락범위")
    lic = " ".join(label.parent.find_next_sibling().get_text(" ", strip=True).split()) if label and label.parent.find_next_sibling() else "미확인"

    btn = soup.select_one('button[onclick*="fn_fileDataDown("], a[onclick*="fn_fileDataDown("]')
    if not btn:
        # 링크 바로가기 여부 확인
        link_btn = soup.select_one('a[onclick*="fn_fileDataLink("], button[onclick*="fn_fileDataLink("]')
        print(f"[{pk}] {title} | 허락: {lic} | 직접 다운로드 버튼 없음 (링크버튼: {link_btn['onclick'] if link_btn else None})", flush=True)
        return
    args = re.findall(r"'([^']*)'", btn["onclick"])
    if len(args) < 5:
        print(f"[{pk}] {title} | 허락: {lic} | onclick 파싱 실패: {btn['onclick']}", flush=True)
        return
    data_pk, detail_pk, _, serial, history = args[:5]
    meta_url = (f"https://www.data.go.kr/tcs/dss/selectFileDataDownload.do?"
                f"publicDataPk={data_pk}&publicDataDetailPk={detail_pk}&fileDetailSn={serial}&publicDataHistSn={history}")
    _, meta_bytes = sess.fetch(f"meta-{pk}", f"portal/meta-{pk}.json", meta_url, license_url=detail_url)
    meta_text = meta_bytes.decode("utf-8", errors="ignore")
    atch = re.search(r'"atchFileId"\s*:\s*"([^"]+)"', meta_text)
    ext = re.search(r'"atchFileExtsn"\s*:\s*"([A-Za-z0-9]+)"', meta_text)
    fsize = re.search(r'"fileMg"\s*:\s*(\d+)', meta_text) or re.search(r'"atchFileMg"\s*:\s*(\d+)', meta_text)
    org_nm = re.search(r'"orignlFileNm"\s*:\s*"([^"]+)"', meta_text)
    size_b = int(fsize[1]) if fsize else None
    print(f"[{pk}] {title} | 허락: {lic} | 원본명: {org_nm[1] if org_nm else '?'} | 확장자: {ext[1] if ext else '?'} | 크기: {size_b:,} B" if size_b else f"[{pk}] {title} | 허락: {lic} | meta: {meta_text[:200]}", flush=True)

    clean_lic = ("제한 없음" in lic) or ("1유형" in lic) or ("제 1유형" in lic)
    if not clean_lic:
        print(f"  -> 이용허락 조건 때문에 다운로드 건너뜀 ({lic})", flush=True)
        return
    if not atch or not ext:
        print(f"  -> 첨부 ID 없음 (링크형 또는 비표준): {meta_text[:200]}", flush=True)
        return
    if size_b and size_b > max_mb * 1024 * 1024:
        print(f"  -> 파일 크기({size_b / 1e6:.1f} MB)가 상한({max_mb} MB)을 넘어 메타만 기록", flush=True)
        return
    dl_url = f"https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={atch[1]}&fileDetailSn={serial}"
    ext_s = ext[1].lower()
    sess.fetch(f"{key_prefix}-{pk}", f"files/{key_prefix}-{pk}.{ext_s}", dl_url, license_url=detail_url)


def main():
    sess = Session()

    # 1. 문제 1 (인천국제공항) 후보 포털 데이터셋
    p1_pks = [
        "3051587",   # 국토교통부_세계 공항_정보
        "15061950",  # 국토교통부_세계 공항_코드
        "15041331",  # 국가철도공단_공항철도_역위치
        "15041094",  # 국가철도공단_공항철도_주소데이터
        "15041332",  # 국가철도공단_공항철도자기부상_역위치
        "15060089",  # 우체국물류지원단_해외통관 우체국 공항 위치
        "15037262",  # 인천국제공항공사_제세동기위치정보
        "15088368",  # 인천국제공항공사_항공사 사무실 정보
        "15086557",  # 인천국제공항공사_코로나19 검사센터 현황
        "15002619",  # 한국공항공사_국제공항 여객실적
        "15002645",  # 한국공항공사_국제공항 화물실적
    ]
    print("=== 문제 1: 인천국제공항 포털 후보 조사 ===", flush=True)
    for pk in p1_pks:
        try:
            download_portal_file(sess, pk, "p1")
        except Exception as e:
            print(f"[err] p1 {pk}: {e}", flush=True)

    # 표준데이터: 전국도시철도역사정보표준데이터 (15013205)
    try:
        std_url = "https://www.data.go.kr/data/15013205/standard.do"
        _, std_html = sess.fetch("portal-std-15013205", "portal/portal-std-15013205.html", std_url, license_url=std_url)
        soup = BeautifulSoup(std_html.decode("utf-8", errors="ignore"), "html.parser")
        label = soup.find(string=lambda x: x and x.strip() == "이용허락범위")
        lic = " ".join(label.parent.find_next_sibling().get_text(" ", strip=True).split()) if label and label.parent.find_next_sibling() else "미확인"
        print(f"[std-15013205] 전국도시철도역사정보표준데이터 | 허락: {lic}", flush=True)
        _, col_bytes = sess.fetch("std-15013205-cols", "portal/std-15013205-cols.json",
                                  "https://www.data.go.kr/download/columList.json?pk=15013205&ext=JSON", license_url=std_url)
        col_info = json.loads(col_bytes.decode("utf-8"))
        print(f"  std-15013205 totalCount: {col_info.get('totalCount')}, table: {col_info.get('svcTableNm')}", flush=True)
    except Exception as e:
        print(f"[err] std-15013205: {e}", flush=True)

    # 2. 문제 1 (인천국제공항) 외부 공식·오픈 후보 (Natural Earth, OurAirports, Wikidata, GeoNames)
    ext_p1 = [
        ("ne-10m-airports", "files/ne_10m_airports.zip",
         "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_airports.zip",
         "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/README.md"),
        ("ourairports-readme", "files/ourairports-README.md",
         "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/README.md",
         "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/README.md"),
        ("wikidata-license", "files/wikidata-licensing.html",
         "https://www.wikidata.org/wiki/Wikidata:Licensing",
         "https://www.wikidata.org/wiki/Wikidata:Licensing"),
        ("wikidata-q20932", "files/wikidata-Q20932.json",
         "https://www.wikidata.org/wiki/Special:EntityData/Q20932.json",
         "https://www.wikidata.org/wiki/Wikidata:Licensing"),
        ("geonames-readme", "files/geonames-readme.txt",
         "https://download.geonames.org/export/dump/readme.txt",
         "https://download.geonames.org/export/dump/readme.txt"),
        ("geonames-kr", "files/geonames-KR.zip",
         "https://download.geonames.org/export/dump/KR.zip",
         "https://download.geonames.org/export/dump/readme.txt"),
    ]
    for key, rel, url, lurl in ext_p1:
        try:
            sess.fetch(key, rel, url, license_url=lurl)
        except Exception as e:
            print(f"[err] {key}: {e}", flush=True)

    # 3. 문제 2 (토지피복) 포털 후보 데이터셋
    p2_pks = [
        # 기후에너지환경부 토지피복 통계·현황 (제1유형 확인 및 파일 다운로드)
        "15124208",  # 지역별 중분류 토지피복 면적 현황
        "15166514",  # 중분류 토지피복지도 지역별 현행화 통계(토지피복지도 작성지침 개정)
        "15163128",  # 국가 토지피복 통계(토지피복지도 분류항목 통계)
        "15124209",  # 지역별 세분류 토지피복 면적 현황
        "15164500",  # 지역별 세분류 토지피복 면적 현황(토지피복지도 작성지침 개정)
        "15150695",  # 중분류 토지피복지도 도엽단위 현행화 통계
        "15150509",  # 세분류 토지피복지도 도엽단위 현행화 통계(토지피복지도 작성지침 개정)
        "15152095",  # 세분류 토지피복지도 도엽단위 현행화 통계
        "15124207",  # 년도별 대분류 토지 피복 통계 현황
        "15071109",  # 국립환경과학원_전국오염원조사 토지계통계
        # 팜맵 나머지 권역 상세·메타 확인 (15104481 서울·세종·6대광역시, 15104491 제주 등 소형은 다운로드)
        "15104481",  # 팜맵 서울_세종_6대광역시
        "15104483",  # 팜맵 경기도
        "15104484",  # 팜맵 충청북도
        "15104485",  # 팜맵 충청남도
        "15104486",  # 팜맵 전북 (메타 크기 확인)
        "15104487",  # 팜맵 전남 (메타 크기 확인)
        "15104488",  # 팜맵 경북 (메타 크기 확인)
        "15104489",  # 팜맵 경남 (메타 크기 확인)
        "15104490",  # 팜맵 강원특별자치도
        "15104491",  # 팜맵 제주특별자치도
        # 산림청 임상도, 국토지리정보원 토지이용현황도, 국토교통부 지적통계
        "15093362",  # 산림청_임상도 (산림공간정보)
        "3045619",   # 산림청_임상도 산림공간정보
        "15059724",  # 국토지리정보원_토지이용현황도
        "3049890",   # 국토교통부_토지이용현황도
        "15063997",  # 국토교통부_지적 기본 통계 집계
        "3078691",   # 경상남도_시군별 지목별 면적
    ]
    print("=== 문제 2: 토지피복 포털 후보 조사 ===", flush=True)
    for pk in p2_pks:
        try:
            # 이미 로컬에 받은 팜맵 3종(15104486, 87, 89)은 max_mb=0 으로 메타만 조회하고 나머지는 80MB 이하 다운로드
            limit_mb = 0 if pk in ("15104486", "15104487", "15104489") else 80
            download_portal_file(sess, pk, "p2", max_mb=limit_mb)
        except Exception as e:
            print(f"[err] p2 {pk}: {e}", flush=True)


if __name__ == "__main__":
    main()

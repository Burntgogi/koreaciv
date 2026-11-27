"""출처 목록 -> site/data/sources.json

data/raw/manifest.json(읽기만)과 data/raw/population/manifest.json 에서 이번 단계에 실제로 쓴 원자료만 고른다.
"""
import collections
import csv
import glob
import os
import sys

from lib import profile as PRF
from lib.common import BUILD, load_json, raw, save_json, site

USED = {
    "boundary_admdong": ("행정구역", "칸 소유 시도·시군구, 도시 영토, 읍면동 인구를 칸에 내리는 표본점 판정"),
    "terrain_srtm30plus": ("지형", "칸 표고·기복(평지/구릉/산/고봉), 먼바다/연안 구분"),
    "ne_ne_10m_admin_0_countries": ("지형", "외국 땅(북한·일본) 판정, 휴전선"),
    "jumin_age5_sgg": ("인구", "시군구 인구·성별·5세 계급 (기준 시점), 도시·시도 집계"),
    # 5a 지도 층
    "datagokr_15017313": ("지도 층", "불가사의: 국립공원 경계·덮는 칸 (넓이는 5d 부터 공식 지정면적)"),
    "datagokr_15107994": ("지도 층", "불가사의: 세계유산 등재 건 (5d 부터 구성 유산 정리표가 기준, 이 파일은 관람객 이름 대응에만)"),
    "datagokr_15087524": ("지도 층", "불가사의: 세계유산 관람객"),
    "heritage_11": ("지도 층", "국가유산 밀집지, 유산 렌즈, 세계유산 구성 유산 위치"),
    "heritage_13": ("지도 층", "국가유산 밀집지, 유산 렌즈, 세계유산 구성 유산 위치"),
    "heritage_15": ("지도 층", "유산 렌즈, 세계유산 구성 유산 위치"),
    "heritage_16": ("지도 층", "유산 렌즈, 세계유산 구성 유산 위치"),
    "datagokr_15046076": ("지도 층", "원전 본부별 가동 용량 — 5b 발전기 현황 원전 합계와 대조"),
    "datagokr_15049846": ("지도 층", "자원: 댐 총저수용량 (위치는 5d 의 WAMIS 댐 관측소 이름 대응)"),
    "datagokr_15085874": ("지도 층", "자원: 국가산업단지"),
    "datagokr_15085886": ("지도 층", "자원: 일반산업단지 시군구 합계"),
    "datagokr_15059868": ("지도 층", "자원: 국가어항"),
    "datagokr_3077829": ("지도 층", "자원: 시도별 금속 가행 광산"),
    "datagokr_15067760": ("지도 층", "자원: 시도별 비금속 가행 광산"),
    "datagokr_15067761": ("지도 층", "자원: 전국 광종별 가행 광산"),
    "datagokr_15067652": ("지도 층", "기반시설: 철도역"),
    "ne_ne_10m_railroads": ("지도 층", "철도 선 초안"),
}
POP_USE = {
    "jumin_age5_emd": ("인구", "읍면동 인구 -> 칸 인구밀도·연령 렌즈, 도시 인구 가중 중심"),
    "jumin_age5_nation": ("인구", "전국·시도 행: 합계 검증"),
    "jumin_age5_sgg_20": ("인구", "과거 12월 시군구 인구: 시계열·증감"),
}
# 5b: data/raw/layers/manifest.json (읽기만) 가운데 실제로 쓴 것. 셋째 값이 참이면 공식 자료가 아닌 '대체 자료'.
LAYERS_USED = {
    "worldcover-": ("지형", "칸 피복 보완: 세분류 토지피복지도 도엽 통계가 닿지 않는 육지 칸의 대표 피복과 대분류 비율 (250 m 최빈값으로 바꾼 격자, 수집 단계)", True),
    "wamis-rivlinen": ("지형", "강: 국가하천 유로선 (Natural Earth 강을 교체)", False),
    "wamis-rivlinel": ("지형", "강: 지방하천 유로선 (20 km 이상, 확대 시)", False),
    "osm-water": ("지형", "호수·저수지 수면 (호수 칸, 칸 위 수면 폴리곤, 이름표)", True),
    "tidal-flat-shp": ("지형", "갯벌 타일·갯벌 비율, 시도별 갯벌 칸 수·넓이 (2011년 제작)", False),
    "municipalities-2025": ("인구", "시도청·시군구청 소재지 (도청 소재지 표식, county 정밀도)", False),
    "special-city-act": ("인구", "전남광주통합특별시 청사 3곳 (제7조제3항)", False),
    "layers-kosis-": ("경제", "시군구 GRDP 과거 연도 (2020년 기준 개편표는 명목 증가율에 이어 붙임, 2015년 기준표는 이어 붙이지 않음)", False),
    "kosis-101-DT_1C91": ("경제", "전국·시도 공식 GRDP·산업별 부가가치·다섯 산출·명목 증가율", False),
    "kosis-101-DT_1DA7004S": ("경제", "전국·시도 공식 고용률·실업률 (경제활동인구조사, 최신 월)", False),
    "lofin-fiscal-2026": ("경제", "전국·시도 재정자립도 (시도 전체 평균, 본청)", False),
    # 5b 2부 — 층과 렌즈
    "data-15002851": ("지도 층", "공항 14곳 좌표 (point)", False),
    "airportal-2025": ("지도 층", "공항별 2025년 여객·화물", False),
    "data-15088273": ("지도 층", "무역항 31곳 위치 문자열 (county, 해안 칸)", False),
    "nlic-ports-2025": ("지도 층", "무역항 2025년 화물 처리량", False),
    "data-15147941": ("지도 층", "부산항 컨테이너(TEU) 원자료 합계", False),
    "mof-ports-2025": ("지도 층", "전국·인천항·광양항 컨테이너 (발표 반올림값)", False),
    "epsis-generators": ("지도 층", "발전소(원전·석탄·가스·수력·양수, 태양광·풍력 시군구 합계), 시군구 연료원별 설비용량", False),
    "its-nodelink-20261111": ("지도 층", "도로 선: 고속국도·일반국도 (Natural Earth 도로를 교체)", False),
    "knps-statistics": ("지도 층", "국립공원 23곳 2025년 탐방객", False),
    "mafra-farm-gi": ("지도 층", "특산: 농산물 지리적표시", False),
    "fish-gi": ("지도 층", "특산: 수산물 지리적표시", False),
    "fish-gi-2": ("지도 층", "특산: 수산물 지리적표시", False),
    "fish-gi-3": ("지도 층", "특산: 수산물 지리적표시", False),
    "forest-gi": ("지도 층", "특산: 임산물 지리적표시", False),
    "kosis-101-DT_1ET0034": ("지도 층", "쌀 아이콘·도시 패널 식량 (2026 논벼 생산량)", False),
    "data-15071107": ("지도 층", "5b 의 돼지·한우·육우 (2019). 한우는 5d 부터 축산유통 통계누리 2026-10, 돼지는 5e 부터 가축위생방역지원본부 2026 시군 값으로 바뀌어 지금 화면에는 쓰지 않음 (빌드 기록용)", False),
    "border-article": ("지도 층", "접경지역 17개 시·군 (시행령 제2조)", False),
    "border-law": ("지도 층", "접경지역 시행령 본문", False),
    "border-act": ("지도 층", "접경지역 지원 특별법 제2조", False),
    "data-15045195": ("지도 층", "연구기관 이름 25건 (지도에 놓지 않음, 연감 목록)", False),
    "kosis-110-TX_11025_A001_A": ("렌즈", "외국인 주민 비율 (2024)", False),
    "air-yearbook-2025": ("렌즈", "초미세먼지(PM2.5) 측정소 연평균 (2025)", False),
    "airkorea-stations": ("렌즈", "PM2.5 측정소 좌표 (정리 단계에서 연평균과 연결)", False),
    "kosis-177-DT_H_SM": ("렌즈", "현재 흡연율 (2025)", False),
    "kosis-177-DT_HEALTH_RECOG": ("렌즈", "주관적 건강 양호 인지율 (2025)", False),
    "kosis-177-DT_H_MENTAL_DEPRESS": ("렌즈", "우울감 경험률 (2025)", False),
    "kosis-177-DT_H_OBE_OBE": ("렌즈", "비만율(자가보고) (2025)", False),
    "disaster-2024": ("렌즈", "자연재난 1인당 피해액 (2024)", False),
    "kosis-101-DT_1YL21191": ("렌즈", "인구 천 명당 사설학원 (2025, 원값 학원 수를 직접 나눔)", False),
}
# layers5: data/raw/layers5/manifest.json (읽기만). 이용허락은 같이 저장한 공공데이터포털 자료 쪽(portal-<번호>.html)의 '이용허락범위' 표시에서 읽는다.
LAYERS5_USED = [
    ("p2-15150509", "data-15150509", "지형", "칸 토지피복 전부(두 판 공용): 대표 피복·대분류와 세부 비율(활엽·침엽·혼효림, 논·밭·과수원·시설재배지), 숲 종류, "
     "숲·농경지·시가지·논·밭·침엽수림 렌즈의 바탕 — 1:5,000 도엽별 세분류 41개 면적을 칸에 나눔 (도엽마다 기준년도가 가장 늦은 행)", "기후에너지환경부"),
    ("p2-15163128", "data-15163128", "지형", "도시·시도·전국 패널 '땅' 구역의 시군구별 중분류 면적(2024 기준, 세분류 41항목을 중분류로 합산), 그리고 칸 피복 비율 대조(화면의 치우침 문장의 숫자)", "기후에너지환경부"),
    ("p1-15041331", "data-15041331", "지도 층", "인천공항 위치: 인천공항1터미널역·인천공항2터미널역 좌표의 중점 (공항 기준점이 아님)", "국가철도공단"),
    ("p1-15041094", "data-15041094", "지도 층", "인천공항 소재 주소: 인천공항1터미널역 도로명주소", "국가철도공단"),
]
PORTAL_LICENSES = ("이용허락범위 제한 없음", "공공저작물 : 출처표시 (제 1유형)")


def portal_license(pk):
    """저장한 공공데이터포털 자료 쪽(신뢰할 수 없는 입력)에서 '이용허락범위' 표시와 제목만 읽는다. 알려진 값 하나가 아니면 빌드 오류."""
    import html as _html
    import re as _re
    path = raw("layers5", "portal", f"portal-{pk}.html")
    t = open(path, "rb").read().decode("utf-8", "replace")
    flat = _html.unescape(_re.sub(r"\s+", " ", _re.sub(r"<[^>]+>", " ", t)))
    # 쪽 안의 이용허락 표시(본문 칸과 메타데이터) 가운데 공공데이터포털 표기 꼴인 것을 모두 모은다 — 둘 이상이거나 알려진 값이 아니면 멈춘다
    vals = {" ".join(m.group(0).split()).replace("(제1유형)", "(제 1유형)")
            for m in _re.finditer(r"이용허락범위 제한 없음|공공저작물 ?: ?[^\(\)<>\"]{2,40}?\(제 ?\d ?유형\)", flat)}
    if len(vals) != 1 or next(iter(vals)) not in PORTAL_LICENSES:
        raise ValueError(f"portal-{pk}.html 의 이용허락범위 표시가 예상 밖: {vals}")
    tm = _re.search(r"<title>\s*([^<|]{1,160}?)\s*\|\s*공공데이터포털\s*</title>", t)
    return next(iter(vals)), (tm.group(1).strip() if tm else None), "layers5/portal/portal-" + pk + ".html"


def layers5_sources():
    path = raw("layers5", "manifest.json")
    if not os.path.exists(path):
        return []
    m = load_json(path)
    out = []
    for mk, key, grp, use, pub in LAYERS5_USED:
        e = m[mk]
        pk = key.split("-", 1)[1]
        lic, title, page = portal_license(pk)
        out.append({"key": key, "title": title, "publisher": pub, "vintage": (e.get("retrieved") or "")[:10] + " 받음", "url": f"https://www.data.go.kr/data/{pk}/fileData.do",
                    "file": "layers5/" + e["file"], "sha256": e["sha256"], "bytes": e["bytes"], "retrieved": e.get("retrieved"), "license": lic,
                    "license_page": page, "alternative": False, "group": grp, "used_in": use})
    return out


# 5d: data/raw/layers2/manifest.json (읽기만). 같은 접두의 파일(시도별 17개 등)은 한 줄로 묶고 파일별 sha256 은 원 매니페스트에 둔다.
LAYERS2_USED = [
    ("customs-trade-sgg-2025-", "경제", "수출입: 도시·시도·전국 교역 구역, 수출 거점, 1인당 수출 렌즈 (2025, 시군구 공표 단위)"),
    ("customs-trade-hs2-2025-", "경제", "수출입 품목: 시군구별 수출·수입 상위 5개 HS 2단위 (2025)"),
    ("nlic-road-od-2024", "지도 층", "교역로: 시도 간 도로 화물 O/D 17×17 (2024)"),
    ("kosis-101-DT_2KI2010_11", "지도 층", "주력 업종 아이콘: 2020 경제총조사 제조업 6개 중분류 종사자 (전국 시군구)"),
    ("kosis-203-DT_203N300003_2024_01", "지도 층", "주력 업종 최신 값: 대구 2024 (도시 패널 병기)"),
    ("kosis-217-DT_217004_2026D005", "지도 층", "주력 업종 최신 값: 경남 2024 (도시 패널 병기)"),
    ("seoul-business-census-2024", "지도 층", "주력 업종 최신 값: 서울 2024 (도시 패널 병기)"),
    ("gyeongbuk-business-2024", "지도 층", "주력 업종 최신 값: 경북 2024 (도시 패널 병기)"),
    ("chungnam-business-2024", "지도 층", "주력 업종 최신 값: 충남 2024 (도시 패널 병기)"),
    ("sejong-business-2024", "지도 층", "주력 업종 최신 값: 세종 2024 (도시 패널 병기)"),
    ("incheon-manufacturing-2022", "지도 층", "주력 업종 최신 값: 인천 2022 (도시 패널 병기)"),
    ("wamis-dam-observations", "지도 층", "댐 위치: 이름이 정확히 같은 댐 관측소 좌표 (point)"),
    ("komir-mine-grid-", "지도 층", "가행 광산 293곳 (광종·소재지 → 시군구, 광산 아이콘·패널 광종별 수)"),
    ("institution-", "지도 층", "지식 아이콘: 과학기술원·출연연·대학 주소 8곳 (county)"),
    ("academyinfo-research-funding-2026", "지도 층", "대학별 연구비 상위 20 (시도 패널·연감, 지도에 놓지 않음)"),
    ("knps-area-2025", "지도 층", "국립공원 23곳 공식 지정면적 (2025 기준)"),
    ("khs-", "지도 층", "세계유산 17건 구성 유산 97행 (이름·소재지)"),
    ("mtrace-hanwoo-202610", "지도 층", "한우 사육 상위 15 아이콘·도시 패널 (2026-10)"),
    ("mtrace-pig-sido-2026q3", "지도 층", "시도 패널 돼지 사육 마릿수 (2026년 3분기, 가축동향조사 — 5e 의 방역본부 시군 값 시도 합과 나란히 대조용)"),
]


LAYERS2_TITLE = {"customs-trade-sgg-2025-": "관세청 수출입무역통계 지역별 총괄 시군구 2025 (시도별 조회)",
                 "customs-trade-hs2-2025-": "관세청 수출입무역통계 지역별 품목별 HS 2단위 2025 (시도별 조회)",
                 "komir-mine-grid-": "한국광해광업공단 국내광산검색 공개 표 (가행)",
                 "institution-": "과학기술원·출연연·대학 누리집 (하단 연락처 주소)",
                 "khs-": "국가유산포털 세계유산 해설·궁능유적본부 왕릉 일람표 (구성 유산)"}


def layers2_sources():
    path = raw("layers2", "manifest.json")
    if not os.path.exists(path):
        return []
    m = load_json(path)
    out = []
    for prefix, grp, use in LAYERS2_USED:
        ks = sorted(k for k in m if k == prefix or (prefix.endswith("-") and k.startswith(prefix)))
        if not ks:
            continue
        e = m[ks[0]]
        lic = sorted({str(m[k].get("license") or "미확인") for k in ks})
        many = len(ks) > 1
        pubs = sorted({str(m[k].get("publisher")) for k in ks})
        out.append({"key": prefix.rstrip("-"), "title": (e.get("title") if not many else f"{LAYERS2_TITLE.get(prefix, e.get('title'))} (파일 {len(ks)}개)"),
                    "publisher": pubs[0] if len(pubs) == 1 else " · ".join(pubs[:3]) + (" 등" if len(pubs) > 3 else ""), "vintage": e.get("vintage") or (e.get("retrieved") or "")[:10],
                    "url": e.get("catalog_url") or e.get("url"), "file": "layers2/" + (str(e.get("file")) if not many else str(e.get("file")).rsplit("/", 1)[0] + "/"),
                    "sha256": e.get("sha256") if not many else None, "bytes": sum(m[k].get("bytes") or 0 for k in ks),
                    "retrieved": max(m[k].get("retrieved") or "" for k in ks), "license": ", ".join(lic), "alternative": False, "group": grp,
                    "used_in": use + (" · 파일별 sha256 은 이 기록의 files (data/raw/layers2/manifest.json)" if many else ""),
                    **({"files": [{"file": m[k].get("file"), "sha256": m[k].get("sha256"), "bytes": m[k].get("bytes")} for k in ks]} if many else {})})
    return out


# 5e: data/raw/layers3/{pig,veterans}/manifest.tsv (읽기만, 탭 5칸: 데이터 번호·제목·URL·sha256·바이트, 머리행 없음)
LAYERS3_USED = {
    "pig": ("지도 층", "돼지 아이콘(상위 15)·도시 패널·시도 합 (2026 시군별 일반돼지 전체두수)",
            "일반돼지만 포함(종돈·흑돼지 등은 별도 자료라 빠짐), 방역 시스템 등록 농가 기준. 광역시는 시 전체 한 행이라 자치구·군으로 나누지 않는다. "
            "가축동향조사(시도, 2026년 3분기)와 조사가 달라 값이 다르다."),
    "veterans": ("렌즈", "보훈대상자 렌즈(인구 천 명당)·도시·시도 패널 인원 (파일마다 최신 분기: 2026년 3분기, 전라남도 파일만 2026년 2분기 — 전남광주통합특별시 파일과 겹쳐 쓰지 않음)",
                 "시군구 인원 = 대상구분 41개 행 '합계'의 합. 원자료 설명대로 대상 사이에 중복이 있어 실제 인원보다 많을 수 있다. "
                 "시도 합계 행은 시군구 값에서 빼고 대조에만 썼다. 세종은 읍면동별."),
}


def layers3_sources():
    out = []
    for sub, (grp, use, note) in LAYERS3_USED.items():
        path = raw("layers3", sub, "manifest.tsv")
        if not os.path.exists(path):
            continue
        rows = []
        with open(path, encoding="utf-8") as f:
            for ln in f:
                p = ln.rstrip("\r\n").split("\t")
                if len(p) == 5 and p[0].strip().isdigit():
                    rows.append({"no": p[0].strip(), "title": p[1].strip(), "url": p[2].strip(), "sha256": p[3].strip(), "bytes": int(p[4])})
        if not rows:
            continue
        pub = sorted({r["title"].split("_", 1)[0] for r in rows})
        vint = sorted({r["title"].rsplit("_", 1)[-1] for r in rows})
        many = len(rows) > 1
        e = rows[0]
        title = e["title"].split("_", 1)[-1] if not many else "시도별 시군구별 보훈대상자 인원현황 (시도별 파일 " + str(len(rows)) + "개, 세종은 읍면동별)"
        out.append({"key": "layers3-" + sub, "title": title, "publisher": " · ".join(pub), "vintage": " · ".join(vint) + " (파일 이름의 기준일)",
                    "url": e["url"] if not many else "https://www.data.go.kr/", "file": "layers3/" + sub + "/", "sha256": None if many else e["sha256"],
                    "bytes": sum(r["bytes"] for r in rows), "retrieved": "", "license": "미확인", "alternative": False, "group": grp,
                    "files": [{"no": r["no"], "title": r["title"], "url": r["url"], "sha256": r["sha256"], "bytes": r["bytes"]} for r in rows],
                    "used_in": use + " · 주의: " + note + " · 공공데이터포털 로그인 없이 받은 파일, 이용허락 미확인 · 파일별 sha256 은 manifest.tsv 와 이 기록의 files",
                    "note": note})
    return out


# 수작업 표: 원자료 파일이 없으므로 표를 적은 코드 파일(file_root 'repo')과 그 빌드 시점 sha256, 작성 근거(basis)를 적는다 (감사 15)
MANUAL = [
    {"key": "manual_national_capital", "title": "수도 표시 (서울)", "publisher": "수작업",
     "vintage": "2026-11", "url": None, "file": "pipeline/build_regions.py", "group": "인구",
     "basis": "수도 표식은 서울 한 곳. 법령·공표 자료 파일을 받지 않았고 코드(build_regions.py)에 적었다",
     "used_in": "도시 깃발의 수도 표식. 도청 소재지는 5b 부터 행정안전부 청사 주소 표에서 읽는다"},
    {"key": "manual_special_cities", "title": "특례시 표", "publisher": "수작업 (지방자치법 제198조 지정 현황)",
     "vintage": "2026-11", "url": None, "file": "pipeline/build_regions.py", "group": "인구",
     "basis": "지방자치법 제198조(인구 100만 이상 대도시 특례) 지정 현황을 손으로 옮긴 표 SPECIAL_CITIES — 공표 자료 파일을 받지 못함",
     "used_in": "도시 종류 '특례시' (수원·고양·용인·화성·창원). 출처를 확인할 공표 자료를 받지 못해 수작업 표로 둔다"},
    {"key": "manual_address", "title": "시도 이름 별칭표 (주소 대응)", "publisher": "수작업 (pipeline/lib/address.py)",
     "vintage": "2026-11", "url": None, "file": "pipeline/lib/address.py", "group": "지도 층",
     "basis": "옛 시도 이름(강원도·전라북도·전라남도·광주광역시)과 짧은 이름을 현재 시도로 잇는 표. 행정구역 개편 법령 시행일 기준",
     "used_in": "주소·소재지 표기 -> 현재 시군구. 옛 시도 이름(강원도·전라북도·전라남도·광주광역시)과 짧은 이름. 좌표·숫자는 없음"},
    {"key": "manual_crosswalk", "title": "행정구역 코드 대응표", "publisher": "수작업 (pipeline/lib/crosswalk.py)",
     "vintage": "2026-10", "url": None, "file": "pipeline/lib/crosswalk.py", "group": "인구",
     "basis": "주민등록 인구 시군구 표(2020-12 ~ 2026-09)에 나온 옛 코드와 현재 코드를 이름·인구 합으로 맞춘 표. 나뉜 구는 비교 단위로 묶는다",
     "used_in": "과거 시군구 코드 -> 현재 코드 (강원·전북 특별자치도, 군위 편입, 광주·전남 통합, 부천·화성 일반구, 인천 개편)"},
]
for _m in MANUAL:
    _m.update({"manual": True, "file_root": "repo", "sha256": None, "bytes": None})


def manual_hashes(out):
    import hashlib
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for x in out:
        if x.get("file_root") == "repo":
            with open(os.path.join(root, x["file"]), "rb") as fh:
                b = fh.read()
            x["sha256"] = hashlib.sha256(b).hexdigest()
            x["bytes"] = len(b)


# 감사 04: 이용허락 유형이 제한적인 자료의 실제 사용 부분과 허용 범위 (확인하지 못한 것은 그렇게 적는다)
USE_SCOPE = {
    "mohw-welfare-2025": ("쓴 부분: 시군구별 일반수급자 수(2025, 229행)의 숫자를 읽어 같은 해 12월 주민등록 인구로 나눈 비율과 색 등급으로 보인다(기초생활 수급 렌즈). "
                          "원 통계를 바꾸지 않는다 — 원값을 그대로 모아(인구 대비 비율) 보이기만 하고, 출처(보건복지부)를 밝힌다."),
    "gyeongbuk-business-2024": ("쓴 부분: 경북 시군별 제조업 중분류 종사자 수(2024)를 도시 패널 주력 업종의 '최신 값'으로 원값 그대로 옮겨 적는다(표 전체를 재배포하지 않음). "
                                "원 통계를 바꾸지 않는다 — 값을 모아 보이기만 하고, 출처(경상북도)를 밝힌다."),
    "sejong-business-2024": ("쓴 부분: 세종 제조업 중분류 종사자 수(2024)를 도시 패널 주력 업종의 '최신 값'으로 원값 그대로 옮겨 적는다(표 전체를 재배포하지 않음). "
                             "원 통계를 바꾸지 않는다 — 값을 모아 보이기만 하고, 출처(세종특별자치시)를 밝힌다."),
}


def clean_used_in(out):
    """감사 04: used_in(쓴 곳)에 수집 때 적은 이용허락 문구가 남아 이용허락 열과 어긋나지 않게 뺀다. 이용허락은 license 열 하나로 본다."""
    import re
    for x in out:
        u = x.get("used_in") or ""
        u = re.sub(r",\s*이용허락 미확인", "", u)
        u = re.sub(r"\s*·\s*이용허락 [^·]*?(?=\s*·|$)", "", u)
        x["used_in"] = u.strip()
        if x["key"] in USE_SCOPE:
            x["use_scope"] = USE_SCOPE[x["key"]]


def LC_NOTE():
    w = load_json(site("world.json"))
    cm = w.get("cover_meta") or {}
    n = (cm.get("src") or {}).get("esa")
    return (f"토지피복 (두 판 공용): {cm.get('source')}를 칸에 나눴다. 방법: {cm.get('method')} 도엽 통계가 닿지 않는 {n}칸만 대체 자료 ESA WorldCover 2021 v200 (CC BY 4.0). "
            "기후에너지환경부 환경공간정보서비스 WMS 그림은 Open API 약관이 저장·전송을 막아 어느 판에서도 쓰지 않는다.")


def landcover_me_sources():
    """국가토지피복통계 정리표(패널 '땅' 구역). 기후에너지환경부 WMS 그림·범례 쪽은 어느 판에서도 쓰지 않아 싣지 않는다."""
    path = raw("landcover_me", "manifest.json")
    if not os.path.exists(path):
        return []
    m = load_json(path)
    out = []
    e = None  # 패널 '땅' 은 이제 data-15163128(공공누리 제1유형)에서 만든다 — build_landstats_open.py
    if e:
        out.append({"key": "landcover-me-stats-ntn-lcm-2025", "title": e.get("title"), "publisher": e.get("publisher"),
                    "vintage": "2024년 기준 (2025 작성)", "url": e.get("url"),
                    "file": "landcover_me/" + e["file"], "sha256": e.get("sha256"), "bytes": e.get("bytes"), "retrieved": e.get("retrieved"),
                    "license": e.get("license"), "alternative": False, "group": "지형",
                    "used_in": "국가토지피복통계 시군구별 중분류 면적: 도시·시도·전국 패널 '땅' 구역 · 이용허락 " + str(e.get("license"))})
    return out


# 감사 03: 지도에 그린 것의 출처 표시. 공유 그림(PNG)은 아래 key 의 sources.json 기록(기관·이용허락)으로 출처 줄을 만든다.
# 'used:문구' 는 used_in 에 그 문구가 든 출처 전부, 끝이 '*' 이면 그 접두어로 시작하는 key 전부.
BASE_ATTR = ["boundary_admdong", "osm-water", "data-15150509", "worldcover-*", "terrain_srtm30plus", "tidal-flat-shp",
             "wamis-rivlinen", "wamis-rivlinel", "ne_ne_10m_admin_0_countries"]
POP = ["jumin_age5_emd", "jumin_age5_sgg"]
POP_Y = ["jumin_age5_sgg_20*"]
GRDP = ["used:다섯 산출·1인당 GRDP"]
LANDCOVER = ["data-15150509"]
LENS_ATTR = {
    "density": POP, "over65": POP, "extinction": POP, "under15": POP, "age": POP, "sex_ratio": POP,
    "growth": ["jumin_age5_sgg"] + POP_Y, "fertility": ["used:합계출산율"], "foreign": ["kosis-110-TX_11025_A001_A"],
    "veterans": ["layers3-veterans"] + POP, "gdp_pc": GRDP + POP_Y, "wage": ["used:1인당 총급여"],
    "home": ["molit-apartment-sale-*"], "jeonse": ["molit-apartment-lease-*"], "employment": ["used:고용률·실업률"],
    "fiscal": ["used:재정자립도"], "assistance": ["used:기초생활 수급"] + POP_Y, "top_industry": GRDP, "manufacturing_share": GRDP,
    "farm_share": GRDP, "export_pc": ["customs-trade-sgg-2025"] + POP_Y, "single": ["used:1인 가구"], "owner": ["used:자가 점유"],
    "long_commute": ["used:긴 통근"], "doctors": ["used:의사 수"], "pm25": ["air-yearbook-2025", "airkorea-stations"],
    "health": ["kosis-177-*"], "smoking": ["kosis-177-DT_H_SM"], "obesity": ["kosis-177-DT_H_OBE_OBE"],
    "depression": ["kosis-177-DT_H_MENTAL_DEPRESS"], "health_good": ["kosis-177-DT_HEALTH_RECOG"],
    "degree": ["used:대졸 이상"], "academies": ["kosis-101-DT_1YL21191"] + POP_Y, "religion": ["used:종교 인구"],
    "religion_top": ["used:종교 인구"], "forest": LANDCOVER + ["worldcover-*"], "cropland": LANDCOVER + ["worldcover-*"],
    "built": LANDCOVER + ["worldcover-*"], "paddy_share": LANDCOVER, "field_share": LANDCOVER, "conifer": LANDCOVER,
    "heritage": ["heritage_*"], "disaster": ["disaster-2024"] + POP_Y, "migration": ["used:순이동률"] + POP_Y, "paddy": ["used:논 비율"],
}

# ---- 감사 04: SRTM30+ 제공자가 복제할 때 함께 싣게 한 저작권 고지와 문단 (보관한 제공자 쪽에서 그대로 옮긴다) ----
SRTM_PAGE = ("layers4", "terrain.html")


def srtm_notice():
    """data/raw/layers4/terrain.html (ERDDAP 자료 정보 쪽, 신뢰하지 않는 입력) 의 NC_GLOBAL license 값 -> 문단 목록.
    표의 '<td>license</td><td>String</td><td>값</td>' 한 칸만 읽고, <br> 로 나뉜 줄을 빈 줄 기준 문단으로 묶는다. 글은 바꾸지 않는다(HTML 개체만 푼다)."""
    import hashlib
    import html as _html
    import re as _re
    p = raw(*SRTM_PAGE)
    b = open(p, "rb").read()
    t = b.decode("utf-8")
    m = _re.search(r"<td>license</td>\s*<td>String</td>\s*<td>(.*?)</td>", t, _re.S)
    if not m or "<" in _re.sub(r"<br\s*/?>", "", m.group(1)):
        raise ValueError("terrain.html 에서 license 칸을 찾지 못했거나 칸 안에 다른 태그가 있음")
    lines = [_html.unescape(x) for x in _re.split(r"<br\s*/?>", m.group(1))]
    paras, cur = [], []
    for ln in lines:
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            paras.append("\n".join(cur))
            cur = []
    if cur:
        paras.append("\n".join(cur))
    need = ("The Regents of the University of California", "Permission to copy, modify and distribute", "IN NO EVENT SHALL", '"AS IS" BASIS')
    flat = " ".join(paras)
    if not all(n in flat for n in need) or len(paras) != 5:
        raise ValueError(f"SRTM30+ 고지 문단이 예상과 다름 ({len(paras)}문단)")
    return {"paragraphs": paras, "from": "/".join(("data", "raw") + SRTM_PAGE), "from_sha256": hashlib.sha256(b).hexdigest(),
            "from_url": "https://coastwatch.pfeg.noaa.gov/erddap/info/srtm30plus_LonPM180/index.html",
            "rule": ("제공자(Scripps·NOAA ERDDAP 자료 정보 쪽의 license 속성)가 교육·연구·비영리 목적의 복제·수정·배포에 붙인 조건: 저작권 고지(아래 첫 문단), 허락 문단(둘째)과 "
                     "뒤따르는 세 문단을 모든 사본에 싣는다. 원문을 고치지 않고 옮겼다 (줄바꿈은 원문의 <br> 그대로).")}


SRTM_COMMERCIAL = ("상업 이용 조건 (코드의 Apache 2.0 이용허락과 별개): SRTM30+ 에서 낸 표고·수심·기복·먼바다/연안 구분(world.json 의 elev·elev_sd·relief·water, "
                   "ridges.json 의 산줄기)은 교육·연구·비영리 목적으로만 복제·배포할 수 있다. 상업 제품에 넣거나 상업 목적으로 쓰려면 UC San Diego 기술이전실"
                   "(invent@ucsd.edu)과 먼저 협의해야 한다. 저장소 코드의 Apache 2.0 이용허락은 이 자료에 미치지 않는다.")
ODBL_STATEMENT = ("이 사이트의 호수·저수지 수면(world.json 의 lakes·lake_labels·lake_meta 와 water = 3 '호수' 칸)은 OpenStreetMap 자료에서 만든 파생 데이터베이스다. "
                  "© OpenStreetMap 기여자. Open Database License(ODbL) 1.0 으로 이용할 수 있다: https://opendatacommons.org/licenses/odbl/1-0/ · "
                  "https://www.openstreetmap.org/copyright. 파생 자료 전체는 이 저장소의 site/data/world.json 에 그대로 있고(위 필드), 만든 방법은 "
                  "pipeline/collect_layers_terrain.py(OSM 추출 -> lakes.geojson)와 pipeline/build_world.py(칸 판정·단순화)에 있다.")

# ---- 감사 05: 조건부·미확인 출처가 실린 자리 (사이트 JSON 의 필드) ----
# 경제 정리표(data/build/econ/<표>.csv) -> 그 값이 실리는 패널 필드. 렌즈는 출처 줄 규칙(attribution.lenses)에서 따로 찾는다.
ECON_FIELDS = {
    "grdp": [("cities.json", "[*].gdp_by_industry", "도시 GRDP·산업별 부가가치·다섯 산출"), ("states.json", "[*].gdp_by_industry", "시도 GRDP 시군구 합")],
    "income": [("cities.json", "[*].wage", "도시 1인당 총급여")],
    "housing": [("cities.json", "[*].housing", "도시 아파트 매매·전세")],
    "employment": [("cities.json", "[*].employment", "도시 고용률·실업률")],
    "finance": [("cities.json", "[*].fiscal_independence", "도시 재정자립도")],
    "education": [("cities.json", "[*].degree", "도시 대졸 이상 비율")],
    "land": [("cities.json", "[*].farm", "도시 논·밭 면적")],
    "agriculture": [("cities.json", "[*].farm", "도시 농가 가구·인구")],
    "business": [("cities.json", "[*].workers", "도시 종사자 합계·제조업"), ("cities.json", "[*].jobs", "도시 산업 대분류 종사자")],
    "official_totals": [("nation.json", "nation.official", "전국 공식값"), ("states.json", "[*].official", "시도 공식값")],
}
# 정리표·매니페스트로 찾지 못하는 자리 (key 무늬 -> 필드). 검증(S7)이 필드가 실제로 있는지 본다.
EXTRA_FIELDS = {
    "terrain_srtm30plus": [("world.json", "elev", "칸 표고"), ("world.json", "elev_sd", "칸 기복"), ("world.json", "relief", "평지·구릉·산·고봉"),
                           ("world.json", "water", "먼바다·연안 구분"), ("ridges.json", "lines", "산줄기 (신여지도)")],
    "osm-water": [("world.json", "lakes", "칸 위 수면 폴리곤"), ("world.json", "lake_labels", "호수 이름표"), ("world.json", "water", "호수 칸 (water = 3)")],
    "tidal-flat-shp": [("world.json", "tidal", "갯벌 칸·비율·시도별 넓이")],
    "wamis-rivlinen": [("world.json", "rivers", "국가하천 선·이름표"), ("ridges.json", "lines", "산줄기 계산의 물줄기")],
    "wamis-rivlinel": [("world.json", "rivers", "지방하천 선 (확대 시)")],
    "data-15150509": [("world.json", "cover_share", "칸 피복 비율"), ("world.json", "cover", "칸 대표 피복"), ("world.json", "forest_kind", "숲 종류"),
                      ("world.json", "crop_kind", "농경지 칸의 무늬")],
    "worldcover-*": [("world.json", "cover_share", "칸 피복 비율 (도엽 통계가 닿지 않는 칸)"), ("world.json", "cover", "칸 대표 피복 (도엽 통계가 닿지 않는 칸)")],
    "data-15163128": [("world.json", "cover_meta.compare", "칸 피복 비율 대조 (치우침 문장)"), ("cities.json", "[*].land_stats", "도시 패널 '땅' (국가 토지피복 통계)"),
                      ("states.json", "[*].land_stats", "시도 패널 '땅'"), ("nation.json", "nation.land_stats", "전국 패널 '땅'")],
    "data-15041331": [("infrastructure.json", "items", "인천공항 위치 (두 터미널 역의 중점)")],
    "municipalities-2025": [("cities.json", "[*].offices", "시군구청 소재지"), ("states.json", "[*].offices", "시도청 소재지")],
    "lofin-fiscal-2026": [("states.json", "[*].official", "시도 재정자립도 (공식값)")],
    "mohw-welfare-2025": [("lenses.json", "lenses[id=assistance]", "렌즈 '기초생활 수급'")],
    "gyeongbuk-business-2024": [("resources.json", "key_industries.by_city", "도시 패널 주력 업종 최신 값 (경북)")],
    "sejong-business-2024": [("resources.json", "key_industries.by_city", "도시 패널 주력 업종 최신 값 (세종)")],
    "chungnam-business-2024": [("resources.json", "key_industries.by_city", "도시 패널 주력 업종 최신 값 (충남)")],
    "knps-statistics": [("wonders.json", "parks", "국립공원 탐방객")],
    "knps-area-2025": [("wonders.json", "parks", "국립공원 공식 지정면적")],
    "khs": [("wonders.json", "world_heritage", "세계유산 구성 유산")],
    "mtrace-pig-sido-2026q3": [("resources.json", "farm.pigs_sido_2026", "시도 패널 돼지 (2026 3분기)")],
    "mof-ports-2025": [("infrastructure.json", "items", "무역항 컨테이너 발표값")],
    "nlic-ports-2025": [("infrastructure.json", "items", "무역항 화물")],
    "manual_national_capital": [("cities.json", "[*].capital", "수도 표식")],
    "manual_special_cities": [("cities.json", "[*].kind", "도시 종류 '특례시'")],
    "manual_address": [("resources.json", "items", "주소로 놓은 층 항목의 시군구")],
    "manual_crosswalk": [("cities.json", "[*].pop_series", "과거 인구 시계열"), ("cities.json", "[*].growth_5y", "5년 인구 증감")],
    "data-15107736-univ-address": [("wonders.json", "universities", "연구대학 주소 → 시군구")],
}


def shipped_fields(out, attr, lens_names, econ_tables):
    """조건이 있거나 이용허락을 확인하지 못한 출처·대체 자료마다 실린 자리(사이트 JSON 필드)를 적는다 (감사 05).
    ① 층 항목·종류의 source  ② 렌즈 출처 줄 규칙  ③ 지도 바탕 출처 줄  ④ 경제 정리표 -> 패널 필드  ⑤ EXTRA_FIELDS."""
    import fnmatch as _fn
    rev = collections.defaultdict(list)
    for lid, ks in attr["lenses"].items():
        for k in ks:
            rev[k].append(lid)
    layer_items = collections.defaultdict(collections.Counter)
    for fn in ("wonders.json", "resources.json", "infrastructure.json"):
        J = _site_json(fn)
        for it in J.get("items") or []:
            sk = it.get("source")
            if isinstance(sk, str):
                layer_items[sk][(fn, it.get("kind"))] += 1
        for kn, kd in (J.get("kinds") or {}).items():
            for sref in (kd or {}).get("source") or []:
                if isinstance(sref, dict) and sref.get("key"):
                    layer_items[sref["key"]][(fn, kn)] += 0
    for x in out:
        x.pop("shipped", None)
        conditional = bool(x.get("restriction_kinds")) or (x.get("license") or "미확인") == "미확인" or x.get("alternative") or x.get("manual")
        if not conditional:
            continue
        k = x["key"]
        rows = []
        li = collections.Counter()
        for sk, cnt in layer_items.items():
            if sk == k or sk.startswith(k + "-"):
                li.update(cnt)
        for (fn, kind), n in sorted(li.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
            if any(fn == f_ and f"kind={kind}" in p_ for f_, p_, _ in rows):
                continue
            rows.append((fn, f"items[kind={kind}]" if n else f"kinds.{kind}", f"층 '{kind}' {n}개" if n else f"층 '{kind}' 규칙·출처"))
        for lid in rev.get(k, []):
            rows.append(("lenses.json", f"lenses[id={lid}]" if any(l_["id"] == lid for l_ in _site_json("lenses.json")["lenses"]) else f"retired_values.items[id={lid}]",
                         f"렌즈 '{lens_names.get(lid, lid)}'"))
        if k in attr["base"]:
            rows.append(("world.json", "cover" if k.startswith(("worldcover", "data-15150509")) else "owner", "지도 바탕 (두 판에 늘 그림)"))
        for t in econ_tables.get(k, ()):
            rows += ECON_FIELDS.get(t, [])
        for pat, fl in EXTRA_FIELDS.items():
            if _fn.fnmatchcase(k, pat):
                rows += fl
        seen, uniq = set(), []
        for r in rows:
            if (r[0], r[1]) not in seen:
                seen.add((r[0], r[1]))
                uniq.append({"file": r[0], "path": r[1], "label": r[2]})
        x["shipped"] = uniq


def profile_block(out, dropped):
    """sources.json 의 profile: 판 이름, 뺀 것과 까닭, 변경금지 통계(원 통계를 바꾸지 않고 모아 보이기만 함) 목록, 판을 바꾸는 명령."""
    kept_nd = [x for x in out if "noderivs" in (x.get("restriction_kinds") or [])]
    consent = [x for x in out if "consent" in (x.get("restriction_kinds") or [])]
    ex = []
    for e in PRF.EXCLUDE:
        srcs = [d for d in dropped if d["excluded"] == e["id"]] if PRF.PUBLIC else [
            {"key": x["key"], "title": x["title"], "publisher": x.get("publisher")} for x in out if PRF.key_excluded(x["key"], "public") == e["id"]]
        ex.append({"id": e["id"], "what": e["what"], "why": e["why"], "instead": e["instead"],
                   "sources": [{"key": d["key"], "title": d["title"], "publisher": d.get("publisher")} for d in srcs]})
    same = " ".join(f"{x['what']}: {x['how']} {x['not_used']}" for x in PRF.SAME_IN_BOTH)
    if PRF.PUBLIC:
        st = ("이 사이트는 공개판(profile public)으로 빌드했다. 개인·비상업 목적의 공개를 위해 이용조건이 공개 배포를 막는 자료 "
              f"{len(ex)}묶음({sum(len(e['sources']) for e in ex)}건)을 뺐다. 뺀 것과 까닭은 아래에 있다. 판 차이가 아닌 것: " + same)
    else:
        st = ("이 사이트는 전체판(profile full)으로 빌드했다 — 내부 열람용이다. 공개판(profile public)이 빼는 자료 "
              f"{len(ex)}묶음({sum(len(e['sources']) for e in ex)}건)이 들어 있어 이 판은 공개 배포하지 않는다. 판 차이가 아닌 것: " + same)
    return {"profile": PRF.PROFILE, "name": PRF.NAME[PRF.PROFILE], "statement": st, "excluded": ex,
            "check_needed": [{"key": x["key"], "title": x["title"], "publisher": x.get("publisher"), "license_short": x.get("license_short"),
                              "kinds": x.get("restriction_kinds"), "use_scope": x.get("use_scope"),
                              "where": [f"{r['label']} ({r['file']} {r['path']})" for r in x.get("shipped") or []]} for x in kept_nd],
            "check_rule": ("변경금지(공공누리 제3·4유형) 조건이 붙은 통계: 원 통계를 바꾸지 않는다 — 원값을 모으고(합·비율) 그대로 보이기만 하며, 출처를 밝힌다."),
            "consent_kept": [{"key": x["key"], "title": x["title"], "why": PRF.KEEP_CONSENT.get(x["key"], "")} for x in consent if not PRF.key_excluded(x["key"], "public")],
            "rule": ("판은 둘이다. 공개판: python pipeline/build_all.py --profile public (GitHub Pages 에 올리는 판). 전체판: python pipeline/build_all.py --profile full "
                     "(내부 열람용, 기본값). 빼는 자료와 까닭은 pipeline/lib/profile.py 의 EXCLUDE 한 곳에 있다.")}


def short_license(lic):
    """이용허락 원문 -> 그림 출처 줄에 넣는 짧은 표기 (원문에서 유형만 골라낸다. 못 고르면 원문 앞부분)."""
    t = str(lic or "").strip()
    n = t.replace(" ", "")
    rules = [("OpenDatabaseLicense", "ODbL 1.0"), ("ODbL", "ODbL 1.0"), ("Attribution4.0", "CC BY 4.0"), ("CCBY4.0", "CC BY 4.0"),
             ("제1유형", "공공누리 제1유형"), ("1유형", "공공누리 제1유형"), ("제3유형", "공공누리 제3유형"), ("4유형", "공공누리 제4유형"),
             ("변경금지", "출처표시·상업적 이용금지·변경금지"), ("publicdomain", "퍼블릭 도메인"), ("KOSIS통계정보", "KOSIS 이용조건"),
             ("non-profit", "교육·연구·비영리 이용 조건"), ("신고일기준으로집계되는공식통계", "외부 공개 시 공식통계 이용 조건"),
             ("영리목적의이용을포함한자유로운활용", "영리 포함 자유 이용"), ("명시적승인없이상업적으로", "상업적 이용 승인 필요"),
             ("사전승낙없이복제", "영리 목적 복제·배포 사전승낙 필요"), ("priorpermission", "사전 허락 필요"), ("KOMIR와사전에", "사전 협의·허락 필요"), ("이용허락범위제한없음", "이용허락범위 제한 없음"), ("보호받지못하는저작물", "보호받지 못하는 저작물")]
    if not t or t == "미확인":
        return "이용허락 미확인"
    for k, v in rules:
        if k.lower() in n.lower():
            return v
    return t[:28] + ("…" if len(t) > 28 else "")


def resolve_keys(specs, out):
    keys = []
    for sp in specs:
        if sp.startswith("used:"):
            hit = [x["key"] for x in out if sp[5:] in (x.get("used_in") or "")]
        elif sp.endswith("*"):
            hit = [x["key"] for x in out if x["key"].startswith(sp[:-1])]
        else:
            hit = [x["key"] for x in out if x["key"] == sp]
        if not hit:
            raise ValueError(f"출처 표시 규칙 '{sp}' 에 맞는 출처가 없음")
        keys += [k for k in hit if k not in keys]
    return keys


def attribution(out, lens_ids=None):
    """lens_ids: lenses.json 에 실린 렌즈(막대 + 뺀 렌즈) id — 그 판에 없는 렌즈(공개판의 아파트·침엽수림)는 출처 줄 규칙에 넣지 않는다."""
    for x in out:
        x["license_short"] = short_license(x.get("license"))
        # ODbL 은 저작자 표시에 © 를 붙여 적는다 (OpenStreetMap 저작권 안내)
        if x["license_short"] == "ODbL 1.0":
            x["attribution_name"] = "© " + str(x.get("publisher"))
    return {"base": resolve_keys(BASE_ATTR, out), "lenses": {k: resolve_keys(v, out) for k, v in LENS_ATTR.items() if lens_ids is None or k in lens_ids},
            "full_list": "연감 › 출처 (data/sources.json)",
            "rule": ("공유 그림의 출처 줄은 그린 것에 맞춰 이 key 들의 기관·이용허락(sources.json)으로 만든다: 지도 바탕(행정경계·표고·토지피복·호수·갯벌·강·국경)은 늘, "
                     "렌즈를 켜면 그 렌즈의 원자료, 켜진 지도 층은 층 종류의 출처. 같은 이용허락끼리 기관을 묶어 적는다.")}


LICENSES_CSV = os.path.join(BUILD, "licenses.csv")
UNIV_CSV = os.path.join(BUILD, "layers", "universities.csv")


def university_sources():
    """6단계 A6: universities.csv 의 대학 주소 출처(address_source_url). 연구비 출처(funding_source_id)는 5d 출처에 이미 있다.
    원파일의 수집 기록은 data/raw/layers4/manifest.json 에서 읽기만 한다."""
    if not os.path.exists(UNIV_CSV):
        return []
    with open(UNIV_CSV, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    urls = sorted({(r.get("address_source_url") or "").strip() for r in rows} - {""})
    m4p = raw("layers4", "manifest.json")
    m4 = load_json(m4p) if os.path.exists(m4p) else {}
    out = []
    for u in urls:
        pk = u.rstrip("/").split("/")[-2] if "/data/" in u else u
        rk, rec = next(((k, v) for k, v in m4.items() if isinstance(v, dict) and k.startswith("university-addresses") and f"publicDataPk={pk}" in (v.get("url") or "")), (None, {}))
        # 감사 15: file 은 원자료(data/raw) 경로, 정리표는 derived_table 로 따로 적는다
        out.append({"key": f"data-{pk}-univ-address", "title": f"대학 주소 (공공데이터포털 표준데이터 {pk})", "publisher": "공공데이터포털",
                    "vintage": (rec.get("retrieved") or "")[:10], "url": u, "file": f"layers4/{rec.get('file') or rk}" if rk else None, "sha256": rec.get("sha256"),
                    "bytes": rec.get("bytes"), "retrieved": rec.get("retrieved"), "group": "층", "derived_table": "data/build/layers/universities.csv",
                    "used_in": "연구대학(지식 불가사의) 주소 → 시군구 — 정리표 data/build/layers/universities.csv (다른 작업자 정리표, 읽기만)"})
    return out


def apply_licenses(out):
    """6단계 A3: data/build/licenses.csv(key, license, license_url, basis, checked_at, note)를 출처마다 license·license_url 로 붙인다.
    표에 없는 출처는 수집 기록(매니페스트)에 이용허락이 적혀 있으면 그 값을, 없으면 '미확인'을 둔다. 손으로 유형을 적지 않는다."""
    rows = {}
    if os.path.exists(LICENSES_CSV):
        with open(LICENSES_CSV, encoding="utf-8-sig", newline="") as fh:
            rd = csv.DictReader(fh)
            need = {"key", "license", "license_url", "basis", "checked_at", "note"}
            if not need <= set(rd.fieldnames or []):
                raise ValueError(f"licenses.csv 열이 다름: 없는 열 {sorted(need - set(rd.fieldnames or []))}")
            for r in rd:
                k = (r["key"] or "").strip()
                if k:
                    rows[k] = r
    n_csv = n_man = n_unk = n_csv_unk = 0
    for s in out:
        r = rows.get(s.get("key"))
        old = s.get("license")
        old = str(old).strip() if old and str(old).strip() and str(old).strip() != "미확인" else None
        for k in ("license_basis", "license_checked", "license_note", "license_collected"):
            s.pop(k, None)
        if r is not None:
            # 표에 행이 있으면 표가 정한다. 표에서 확인하지 못한 것(license 빈 칸)은 '미확인' — 수집 기록의 값은 참고로만 남긴다
            lic = (r["license"] or "").strip()
            s["license"] = lic or "미확인"
            s["license_url"] = (r["license_url"] or "").strip() or None
            s["license_basis"] = (r["basis"] or "").strip() or None
            s["license_checked"] = (r["checked_at"] or "").strip() or None
            if (r["note"] or "").strip():
                s["license_note"] = r["note"].strip()
            if not lic and old:
                s["license_collected"] = old
            s["license_from"] = "licenses.csv"
            n_csv += 1
            n_csv_unk += 0 if lic else 1
        elif old:
            s["license"] = old
            s["license_url"] = None
            s["license_from"] = "수집 기록"
            n_man += 1
        else:
            s["license"] = "미확인"
            s["license_url"] = None
            s["license_from"] = None
            n_unk += 1
    # 공개판에서 뺀 출처(lib/profile.py EXCLUDE)는 '표에만 있는 key' 목록에 적지 않는다 — 무엇을 왜 뺐는지는 profile 기록에 있다
    dropped_n = sum(1 for k in rows if PRF.key_excluded(k))
    never_n = sum(1 for k in rows if PRF.never_used(k))
    unused = sorted(k for k in set(rows) - {s.get("key") for s in out} if not PRF.key_excluded(k) and not PRF.never_used(k))
    if os.path.exists(LICENSES_CSV):
        note = (f"이용허락: data/build/licenses.csv(다른 작업자가 출처 페이지에서 확인한 표, {len(rows)}개 key)를 출처 key 로 붙였다 — 표에 행이 있는 출처 {n_csv}건"
                f"(그 가운데 표에서도 확인하지 못해 '미확인' {n_csv_unk}건, 수집 기록에 다른 값이 있으면 참고로 함께 적음), 표에 없어 수집 기록(매니페스트)의 값 {n_man}건, "
                f"표에도 기록에도 없어 미확인 {n_unk}건." + (f" 출처 목록에 없는 표의 key {len(unused)}개: {', '.join(unused[:20])}{' …' if len(unused) > 20 else ''}." if unused else "")
                + (f" 공개판에서 뺀 출처 {dropped_n}건은 표에 있어도 이 목록에 싣지 않는다(profile 기록)." if dropped_n else "")
                + (f" 두 판 모두 쓰지 않게 된 출처 {never_n}건(토지피복 WMS 그림·그 범례 쪽, 항공정보간행물 좌표)도 싣지 않는다." if never_n else ""))
    else:
        note = (f"이용허락: 출처별 이용허락 표(data/build/licenses.csv)가 빌드 시점에 없었다. 수집 기록(매니페스트)에 적힌 값 {n_man}건만 보이고, "
                f"나머지 {n_unk}건은 '미확인'이다.")
    print(f"[sources] 이용허락 — licenses.csv {'있음 ' + str(len(rows)) + '개 key' if rows else '없음'}: 표 {n_csv} (표에서도 미확인 {n_csv_unk}), 수집 기록 {n_man}, 미확인 {n_unk}, 표에만 있는 key {len(unused)}")
    return note


import ast
import datetime

from lib import notice as NT

# ---- 출처 페이지 (site/sources/) 와 NOTICE.md 를 위한 기록 ----
# 계산한 층: (key, 제목, 규칙 문장이 든 자리 'site/data 파일:경로' 목록, 조각 목록 자리, 입력 출처 규칙(attribution 과 같은 꼴), 쓰는 곳)
# 규칙 문장은 그 자리에서 빌드 때 그대로 옮긴다 (validate.py 가 같은 자리에서 다시 읽어 대조한다).
DERIVED = [
    ("derived-ridges", "산줄기 (분수계, 계산한 선)", ["ridges.json:rule", "ridges.json:method"], "ridges.json:tiers",
     ["terrain_srtm30plus", "wamis-rivlinen", "wamis-rivlinel", "boundary_admdong"], "신여지도 먹판의 산줄기 선 (기존판은 그리지 않음)"),
    ("derived-relief", "칸 기복 (평지·구릉·산·고봉)", [], "world.json:tables.relief", ["terrain_srtm30plus"], "두 판의 지형 칸 (기복)"),
    ("derived-cell-population", "칸 인구 (읍면동 값을 칸에 내림)", ["lenses.json:lenses[id=density].description"], None,
     POP + ["boundary_admdong"], "인구밀도·고령 인구·소멸위험지수 등 칸 렌즈"),
    ("derived-extinction", "소멸위험지수", ["lenses.json:lenses[id=extinction].description"], None, POP, "렌즈 '소멸위험지수'·도시 패널·특성 표시"),
    ("derived-health-index", "건강 지수", ["lenses.json:lenses[id=health].description"], None, ["kosis-177-*"], "렌즈 '건강 지수'"),
    ("derived-pm25", "초미세먼지 칸 값 (측정소 거리 역가중)", ["lenses.json:lenses[id=pm25].description"], None, ["air-yearbook-2025", "airkorea-stations"], "렌즈 '초미세먼지'"),
    ("derived-landcover-share", "칸 토지피복 비율", ["world.json:cover_meta.method", "world.json:cover_meta.bias_note"], "world.json:tables.cover",
     LANDCOVER + ["worldcover-*", "data-15163128"], "지형 칸의 피복 빛깔, 숲·농경지·시가지·논·밭·침엽수림 렌즈 (두 판 공용)"),
    ("derived-yields", "다섯 산출 (식량·생산·금·과학·문화)", [], "nation.json:econ.yields", GRDP, "도시·시도·전국 패널의 다섯 산출, 순위 보고서"),
    ("derived-location-quotient", "입지계수 (LQ)", ["nation.json:nation.lq_rule"], None, GRDP + ["kosis-101-DT_1C91", "used:종사자"], "도시 패널의 업종 입지계수"),
    ("derived-city-tags", "도시 특성 표시", ["nation.json:nation.tag_rule"], None,
     GRDP + ["customs-trade-sgg-2025", "used:1인당 총급여"] + POP + POP_Y, "도시 머리의 특성 표시 (최대 2개)"),
    ("derived-peer-cities", "닮은 도시", ["nation.json:nation.peer_rule"], None,
     POP + GRDP + ["molit-apartment-sale-*", "used:1인당 총급여"], "도시 패널의 닮은 도시와 그 근거"),
    ("derived-benchmarks", "전국 기준 대비와 순위 막대", ["nation.json:nation.benchmarks.rule"], None,
     POP + GRDP + ["used:1인당 총급여", "molit-apartment-sale-*", "molit-apartment-lease-*", "used:대졸 이상", "used:고용률·실업률", "used:재정자립도"], "패널의 전국 비교 줄·순위 막대"),
    ("derived-presets", "추천 시점 여섯", ["nation.json:presets.rule"], None, [], "첫 화면의 추천 시점"),
]


if PRF.PUBLIC:
    # 공개판: 계산한 층의 입력에서 빼는 출처(lib/profile.py EXCLUDE)를 뺀다
    DERIVED = [tuple(list(_r[:4]) + [[k for k in _r[4] if not PRF.key_excluded(k.rstrip("*"))]] + list(_r[5:])) for _r in DERIVED]


def _site_json(fn, cache={}):
    if fn not in cache:
        cache[fn] = load_json(site(fn))
    return cache[fn]


def derived_records(out):
    res = []
    for key, title, specs, parts_spec, inputs, use in DERIVED:
        texts = [NT.resolve_rule(sp, _site_json)[0] for sp in specs]
        parts = NT.resolve_rule(parts_spec, _site_json)[1] if parts_spec else None
        files = sorted({sp.split(":", 1)[0] for sp in specs + ([parts_spec] if parts_spec else [])})
        r = {"key": key, "kind": "derived", "title": title, "file": " · ".join("site/data/" + f for f in files),
             "rule": " ".join(texts) if texts else NT.resolve_rule(parts_spec, _site_json)[0],
             "rule_from": specs, "used_in": use, "inputs": resolve_keys(inputs, out) if inputs else []}
        if parts_spec:
            r["parts_from"] = parts_spec
            r["parts"] = parts
        if not inputs:
            r["inputs_note"] = "site/data 의 계산 값 (원자료를 직접 읽지 않는다)"
        if key == "derived-ridges":
            ck = _site_json("ridges.json").get("checks") or {}
            r["checks"] = (f"물줄기 교차 {ck.get('river_crossings')}건 (물줄기 {ck.get('rivers_tested')}개), 호수 가로지름 {ck.get('lake_crossings')}건, "
                           f"선 {ck.get('lines')}개 · {ck.get('total_km')} km")
            r["version"] = _site_json("ridges.json").get("version")
        res.append(r)
    return res


# 글꼴 윤곽에서 뽑은 그림·기록용 서브셋이 어느 글꼴 기록에 딸렸는지 (site/yeojido/fonts/README.md 표: `title-hanja.svg` (+ `title-hanja.woff2`), `seal.svg`, `seal-mask.svg`)
FONT_EXTRA_FILES = {"title-hanja.woff2": "title-hanja.svg", "seal-mask.svg": "seal.svg"}
# 출처 페이지(site/sources/)도 쓰는 글꼴 (css/sources.css 의 @font-face)
SOURCES_PAGE_FONTS = {"Hahmlet-VF.subset.woff2": "출처 페이지 제목", "YeojidoSans-VF.subset.woff2": "출처 페이지 본문"}


def font_credits():
    fj = load_json(os.path.join(NT.FONT_DIR, "fonts.json"))
    res, mapped = [], set()
    for f in fj.get("fonts") or []:
        lf = os.path.join(NT.FONT_DIR, f["licence_file"])
        o = NT.parse_ofl(lf)
        if not o["license"]:
            raise ValueError(f"글꼴 이용허락 파일에서 OFL 1.1 문구를 찾지 못함: {lf}")
        files = [f["file"]] + sorted(k for k, v in FONT_EXTRA_FILES.items() if v == f["file"])
        recs = []
        for fn in files:
            h_, b_ = NT.sha256_file(os.path.join(NT.FONT_DIR, fn))
            recs.append({"file": "site/yeojido/fonts/" + fn, "sha256": h_, "bytes": b_})
            mapped.add("site/yeojido/fonts/" + fn)
        lh, _ = NT.sha256_file(lf)
        use = "신여지도 " + f["role"] + "".join(" · " + v for k, v in SOURCES_PAGE_FONTS.items() if k == f["file"])
        res.append({"key": "font-" + os.path.splitext(f["file"])[0].split(".")[0].lower(), "kind": "font", "title": f.get("family_shown"),
                    "publisher": f.get("author"), "role": f.get("role"), "url": f.get("source_url"), "source_ref": f.get("source_ref"),
                    "retrieved": f.get("fetched"), "license": o["license"], "license_short": "SIL OFL 1.1", "license_url": o["license_url"],
                    "license_file": "site/yeojido/fonts/" + f["licence_file"], "license_sha256": lh, "copyright": o["copyright"],
                    "reserved_font_name": o["reserved_font_name"], "files": recs, "used_in": use, "note": f.get("note"),
                    "license_from": "이용허락 파일"})
    left = [p for p in NT.shipped_font_files() if p not in mapped]
    if left:
        raise ValueError(f"이용허락 기록이 없는 글꼴 파일: {left}")
    return res


def third_party_modules():
    """pipeline/·tools/ 의 .py 가 import 하는 표준 라이브러리 밖 모듈 이름 (이 저장소 안 모듈은 뺀다)."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local, names = set(), set()
    for top in ("pipeline", "tools"):
        for dp, _, fs in os.walk(os.path.join(root, top)):
            for f in fs:
                if f.endswith(".py"):
                    local.add(f[:-3])
                    try:
                        tree = ast.parse(open(os.path.join(dp, f), encoding="utf-8").read())
                    except SyntaxError:
                        continue
                    for n in ast.walk(tree):
                        if isinstance(n, ast.Import):
                            names |= {a.name.split(".")[0] for a in n.names}
                        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                            names.add(n.module.split(".")[0])
            local |= {d for d in os.listdir(os.path.join(root, top)) if os.path.isdir(os.path.join(root, top, d))}
    return sorted((names - set(sys.stdlib_module_names) - local - {"lib"}), key=str.lower)


def other_credits():
    return [
        {"key": "project-own-work", "kind": "project", "title": "koreaciv · 신여지도 — 이 저장소가 만든 것 (코드, 화면 디자인, 문서, 수업안)", "publisher": "제작자",
         "url": None, "license": "Apache License 2.0", "license_short": "Apache-2.0",
         "license_note": "저장소의 LICENSE. 이 이용허락은 우리가 만든 것에만 적용된다. 위 자료와 글꼴에는 각자의 조건이 따로 있다.",
         "used_in": "저장소 전체의 코드·디자인·문서·수업안 (자료·글꼴 제외)", "basis": "LICENSE · README.md"},
        {"key": "inspiration-usaciv", "kind": "inspiration", "title": "usaciv — the United States as a strategy game", "publisher": "karpathy.ai",
         "url": "https://karpathy.ai/usaciv/", "license": "해당 없음", "license_short": "해당 없음 (착안)",
         "license_note": ("착안만 했다 (Andrej Karpathy). 자료 출처가 아니며, 원작의 코드·그림·자료를 가져오지 않았다. 원작에 관한 권리와 이용조건은 원작자의 것이며, "
                          "2026-11 현재 원작 사이트에서 공개된 이용허락 문서는 찾지 못했다 (README.md)."),
         "used_in": "착안: 실제 나라를 공공 통계로 턴제 전략 게임 지도처럼 그린다는 생각", "basis": "README.md · docs/DESIGN.md"},
        {"key": "build-tools-python", "kind": "tool", "title": "Python 라이브러리 (수집·빌드·검사·갈무리 도구)", "publisher": "각 라이브러리 프로젝트",
         "url": None, "names": third_party_modules(), "license": "미확인", "license_short": "이용허락 미확인",
         "license_note": "사이트에 실리지 않는 도구다. 저장소에 이용허락 파일이 없어 유형을 적지 않았다 — 각 패키지의 배포 정보를 본다.",
         "used_in": "pipeline/·tools/ 의 import (import 이름 그대로)"},
    ]


def affects(out, attr, lens_names):
    """제한 자료마다 사이트에서 영향 받는 곳: 지도 바탕 여부와 그 출처를 쓰는 렌즈 이름 (attribution 규칙에서)."""
    rev = collections.defaultdict(list)
    for lid, ks in attr["lenses"].items():
        for k in ks:
            rev[k].append(lens_names.get(lid, lid))
    for x in out:
        x.pop("restriction_kinds", None)
        x.pop("affects", None)
        ks = NT.restriction_kinds(x)
        if ks:
            x["restriction_kinds"] = ks
            x["affects"] = {"base": x["key"] in attr["base"], "lenses": rev.get(x["key"], [])}


def cite_block(out, summary):
    by = collections.defaultdict(list)
    for x in out:
        nm = x.get("attribution_name") or x.get("publisher")
        if nm not in by[x["license_short"]]:
            by[x["license_short"]].append(nm)
    order = [k for k, _ in NT.license_counts(out)]
    lines = [f"{k}: {' · '.join(by[k])}" for k in order]
    pubs = collections.Counter(x.get("publisher") for x in out)
    top = [p for p, _ in pubs.most_common(6)]
    must = [f"{x.get('attribution_name') or x.get('publisher')} — {x['title']} ({x['license_short']})" for x in out
            if x["license_short"] in ("ODbL 1.0", "CC BY 4.0", "교육·연구·비영리 이용 조건") and not x["key"].startswith("worldcover-")]
    wc = [x for x in out if x["key"].startswith("worldcover-")]
    if wc:
        must.append(f"{wc[0]['publisher']} — ESA WorldCover 타일 {len(wc)}장 ({wc[0]['license_short']})")
    text = "\n".join([
        "koreaciv · 신여지도 — 공공 통계로 그린 대한민국 지도 (개인·비상업 목적 공개, 정부·공공기관과 관계 없음)",
        f"자료: {', '.join(top)} 등 {len(pubs)}개 기관·출처의 공개 자료 {len(out)}건을 가공 (인구 기준 {summary['population_vintage']}, 빌드 {summary['built']})",
        *must,
        "출처별 이용허락과 조건: 사이트의 출처 페이지(sources/)와 저장소의 NOTICE.md"])
    return {"text": text, "lines": lines,
            "rule": "출처 표기 줄은 이용허락(짧은 표기)마다 기관을 모은 것이다. 위 글은 출처 표시를 꼭 요구하는 이용허락(ODbL·CC BY·SRTM30+ 고지)의 자료를 따로 적었다."}


def summary_block(out):
    nat = _site_json("nation.json")
    ret = sorted((x.get("retrieved") or "")[:10] for x in out if x.get("retrieved"))
    chk = sorted(x.get("license_checked") for x in out if x.get("license_checked"))
    pubs = len({x.get("publisher") for x in out})
    unk = sum(1 for x in out if x.get("license") == "미확인")
    rs = sum(1 for x in out if x.get("restriction_kinds"))
    sm = {"built": datetime.date.today().isoformat(), "population_vintage": nat.get("vintage"),
          "retrieved_from": ret[0] if ret else None, "retrieved_to": ret[-1] if ret else None, "license_checked": chk[-1] if chk else None,
          "counts": {"sources": len(out), "publishers": pubs, "unknown": unk, "restricted": rs}}
    sm["text"] = [
        f"이 사이트의 숫자와 위치는 정부·공공기관 등 {pubs}개 기관·출처가 공개한 자료 {len(out)}건(통계표·지도 파일·법령)에서 왔다. 숫자를 손으로 넣지 않았고, 손으로 옮긴 표 {sum(1 for x in out if x.get('manual'))}개(이름·코드 대응 등)는 '수작업'으로 표시했다.",
        "개인·비상업 목적으로 공개한다. 자료마다 이용조건이 달라, 상업적으로 쓰려면 출처별 조건을 직접 확인해야 한다.",
        "이 사이트는 정부·공공기관과 관계가 없다. 통계의 가공·표현에 대한 책임은 제작자에게 있다.",
        f"기준: 인구 {sm['population_vintage']} 주민등록, 자료 수집 {sm['retrieved_from'] if sm['retrieved_from'] == sm['retrieved_to'] else str(sm['retrieved_from']) + '–' + str(sm['retrieved_to'])}, 이용허락 확인 {sm['license_checked']}, 출처 목록 빌드 {sm['built']}.",
        f"이용조건에 제한이 있는 자료 {rs}건, 이용허락을 확인하지 못한 자료 {unk}건 — 아래에 따로 적었다.",
    ]
    return sm


def main():
    out = []
    m = load_json(raw("manifest.json"))
    for k, (grp, use) in USED.items():
        if k not in m:
            continue
        e = m[k]
        out.append({"key": k, "title": e.get("title"), "publisher": e.get("publisher"),
                    "vintage": e.get("vintage") or e.get("retrieved", "")[:10], "url": e.get("url"),
                    "file": e.get("file"), "sha256": e.get("sha256"), "bytes": e.get("bytes"),
                    "retrieved": e.get("retrieved"), "group": grp, "used_in": use})
    pm = load_json(raw("population", "manifest.json"))
    for k, e in sorted(pm.items()):
        use = next((v for p, v in POP_USE.items() if k.startswith(p)), None)
        if not use:
            continue
        out.append({"key": k, "title": e.get("title"), "publisher": e.get("publisher"), "vintage": e.get("vintage"),
                    "url": e.get("url"), "file": e.get("file"), "sha256": e.get("sha256"), "bytes": e.get("bytes"),
                    "retrieved": e.get("retrieved"), "group": use[0], "used_in": use[1]})
    # 경제 원자료: data/raw/econ/manifest.json (읽기만) 가운데 정리표 행의 source_id 로 실제 쓰인 것
    econ_use = {"grdp": "다섯 산출·1인당 GRDP·산업 비중·최대 산업", "income": "1인당 총급여",
                "housing": "아파트 매매·전세 (건별 원자료에서 12개월 전체 거래 중위값 직접 계산)",
                "employment": "고용률·실업률", "finance": "재정자립도", "assistance": "기초생활 수급", "fertility": "합계출산율",
                "migration": "순이동률", "households": "1인 가구", "tenure": "자가 점유", "commute": "긴 통근",
                "doctors": "의사 수", "education": "대졸 이상", "religion": "종교 인구·최대 종교", "land": "논 비율·경지",
                "agriculture": "농가 가구·인구", "business": "종사자 (합계·제조업)",
                "official_totals": "전국·시도 공식값 (5b: GRDP·종사자 대분류·고용·재정자립도·논밭 면적)"}
    em_path = raw("econ", "manifest.json")
    used = collections.defaultdict(set)
    if os.path.exists(em_path):
        em = load_json(em_path)
        for f in glob.glob(os.path.join(BUILD, "econ", "*.csv")):
            t = os.path.basename(f)[:-4]
            if t not in econ_use:
                continue
            with open(f, encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    used[r.get("source_id", "")].add(t)
        for k, e in sorted(em.items()):
            if k not in used:
                continue
            out.append({"key": k, "title": e.get("title"), "publisher": e.get("publisher"),
                        "vintage": e.get("vintage") if not isinstance(e.get("vintage"), list) else "–".join(map(str, e["vintage"])),
                        "url": e.get("catalog_url") or e.get("url"), "file": "econ/" + str(e.get("file")),
                        "sha256": e.get("sha256"), "bytes": e.get("bytes"), "retrieved": e.get("retrieved"),
                        "license": e.get("license") or e.get("license_note"), "group": "경제",
                        "used_in": " · ".join(econ_use[t] for t in sorted(used[k]))})
    lm_path = raw("layers", "manifest.json")
    if os.path.exists(lm_path):
        lm = load_json(lm_path)
        have = {x["key"] for x in out}
        for k, e in sorted(lm.items()):
            use = next((v for p, v in LAYERS_USED.items() if k == p or (p.endswith("-") and k.startswith(p))), None)
            if not use or k in have:
                continue
            grp, txt, alt = use
            if k.startswith("layers-kosis-"):
                txt = ("시군구 GRDP 2015년 기준표 — 기준년이 달라 이어 붙이지 않음 (읽어서 계열만 확인)" if "grdp_history_2015" in str(e.get("file"))
                       else "시군구 GRDP 2020년 기준 개편표 과거 연도 — 최신 표와 같은 표 번호라 명목 증가율에 이어 붙임")
            lic = e.get("license") or e.get("license_note")
            out.append({"key": k, "title": e.get("title"), "publisher": e.get("publisher"),
                        "vintage": e.get("vintage") or (e.get("retrieved") or "")[:10], "url": e.get("catalog_url") or e.get("url"),
                        "file": "layers/" + str(e.get("file")), "sha256": e.get("sha256"), "bytes": e.get("bytes"),
                        "retrieved": e.get("retrieved"), "license": lic, "alternative": alt, "group": grp,
                        "used_in": ("대체 자료 (공식 자료 아님) · " if alt else "") + txt
                                   + (" · 이용허락 " + lic if lic and lic != "미확인" else " · 이용허락 미확인")
                                   + (" · © OpenStreetMap 기여자" if k == "osm-water" else "")})
    # 5c: 기후에너지환경부 토지피복지도 (data/raw/landcover_me/manifest.json, 읽기만)
    out += landcover_me_sources()
    # 두 판 공용 토지피복(세분류 토지피복지도 도엽 통계)·대조 통계·인천공항 위치 (data/raw/layers5/manifest.json, 읽기만)
    out += layers5_sources()
    # 5d: 수출입·교역로·남은 위치 자료 (data/raw/layers2/manifest.json, 읽기만)
    out += layers2_sources()
    # 5e: 돼지 시군 값·보훈대상자 (data/raw/layers3/*/manifest.tsv, 읽기만)
    out += layers3_sources()
    out += MANUAL
    out += university_sources()
    # 공개판: 빼는 자료(lib/profile.py EXCLUDE)는 출처 목록에서도 뺀다 — 무엇을 왜 뺐는지는 profile 기록에 남는다
    dropped = []
    if PRF.PUBLIC:
        keep = []
        for x in out:
            eid = PRF.key_excluded(x["key"])
            if eid:
                dropped.append({"key": x["key"], "title": x["title"], "publisher": x.get("publisher"), "excluded": eid})
            else:
                keep.append(x)
        out = keep
        print(f"[sources] 공개판: 출처 {len(dropped)}건 뺌 — " + ", ".join(sorted({d['excluded'] for d in dropped})))
    never = sorted(x["key"] for x in out if PRF.never_used(x["key"]))
    if never:
        raise ValueError(f"어느 판에서도 쓰지 않는 출처가 목록에 들어옴: {never}")
    lic_note = apply_licenses(out)
    for x in out:
        if x.get("license_page"):
            # 이용허락: 같이 저장한 공공데이터포털 자료 쪽의 '이용허락범위' 표시 (build_sources.portal_license 가 읽음)
            x["license_from"] = "저장한 자료 쪽"
            x["license_basis"] = x.pop("license_page")
        if x["key"] == "terrain_srtm30plus":
            x["required_notice"] = srtm_notice()
            x["commercial_use"] = SRTM_COMMERCIAL
        if x["key"] == "osm-water":
            x["odbl"] = ODBL_STATEMENT
    clean_used_in(out)
    manual_hashes(out)
    L = _site_json("lenses.json")
    lens_names = {l_["id"]: l_["name"] for l_ in L["lenses"]}
    lens_names.update({it["id"]: it["name"] + " (렌즈 막대에서 뺀 지표)" for it in (L.get("retired_values") or {}).get("items", [])})
    attr = attribution(out, set(lens_names))
    affects(out, attr, lens_names)
    shipped_fields(out, attr, lens_names, {k: sorted(v) for k, v in used.items()})
    summary = summary_block(out)
    derived = derived_records(out)
    credits = font_credits() + other_credits()
    w_ = load_json(site("world.json"))
    lc_notes = [LC_NOTE(), "토지피복 칸 비율의 치우침: " + w_["cover_meta"]["bias_note"],
                "인천공항 위치 (두 판 공용): 국가철도공단 공항철도 역위치의 인천공항1터미널역·2터미널역 좌표의 중점 — 공항 기준점이 아님. 항공정보간행물(AIP) 좌표는 어느 판에서도 쓰지 않는다."]
    save_json(site("sources.json"), {"profile": profile_block(out, dropped), "sources": out, "license_rule": lic_note, "attribution": attr,
                                     "summary": summary, "cite": cite_block(out, summary), "restricted_rule": NT.restriction_rule(),
                                     "restriction_kinds": [{"code": c, "name": n, "text": d} for c, n, d, _ in NT.RESTRICTION_KINDS],
                                     "derived": derived, "credits": credits,
                                     "restrictions": [{"key": x["key"], "title": x["title"], "text": x["restriction"], "short": x.get("restriction_short")}
                                                      for x in out if x.get("restriction")],
                                     "notes": ["원자료 파일마다 수집 시각과 sha256 을 남겼다. 같은 파일로 다시 빌드하면 같은 결과가 나온다.",
                                               "경제 정리표(data/build/econ)는 다른 작업자가 만든 것을 읽기만 했다. 원자료 기록은 data/raw/econ/manifest.json.",
                                               *lc_notes,
                                               "대체 자료: 호수·저수지 수면은 OpenStreetMap (© OpenStreetMap 기여자, ODbL 1.0)이다. 공식 호소 수면은 로그인·신청·키가 필요해 받지 않았다.",
                                               "5b 지형·청사·공식값·층·렌즈 원자료 기록은 data/raw/layers/manifest.json.",
                                               "도로 선은 5b 부터 국가교통정보센터 전국표준노드링크다. 철도 선은 여전히 Natural Earth 1:10m 초안이다.",
                                               ("5d 수출입·교역로·세계유산 구성 유산 등 원자료 기록은" if PRF.PUBLIC else "5d 수출입·교역로·광산·세계유산 구성 유산 등 원자료 기록은") + " data/raw/layers2/manifest.json. 공개 페이지에서 이용허락 유형을 확인하지 못한 자료는 '미확인'으로 적었다.",
                                               "5e 돼지 시군 값(가축위생방역지원본부)과 보훈대상자(국가보훈부) 원자료 기록은 data/raw/layers3/{pig,veterans}/manifest.tsv. 보훈대상자 인원은 대상 사이 중복이 있어 실제 인원보다 많을 수 있다."]})
    print(f"[sources] {len(out)}건")


if __name__ == "__main__":
    sys.exit(main())

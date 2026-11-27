"""빌드 판(profile): full(전체판, 내부 열람용 — 지금까지의 빌드 그대로) / public(공개판, 공개 배포용).

build_all.py --profile public 이 환경 변수 KOREACIV_PROFILE 로 각 단계에 넘긴다. 단계를 따로 돌릴 때도 같은 변수를 쓴다.
공개판이 빼는 자료와 그 까닭은 아래 EXCLUDE 한 곳에만 적는다. build_sources.py 가 이것으로 sources.json 의 profile 기록을 만들고
(출처 쪽·두 판의 연감·NOTICE.md 가 그 기록을 보인다), validate.py 가 같은 표로 빠졌는지 다시 확인한다.
"""
import fnmatch
import os

PROFILES = ("full", "public")
ENV = "KOREACIV_PROFILE"


def active():
    p = (os.environ.get(ENV) or "full").strip()
    if p not in PROFILES:
        raise SystemExit(f"알 수 없는 빌드 판 {ENV}={p!r} — {' / '.join(PROFILES)} 가운데 하나")
    return p


PROFILE = active()
PUBLIC = PROFILE == "public"
NAME = {"full": "전체판", "public": "공개판"}

# 공개판이 빼는 것: (id, 무엇, 출처 key 무늬, 까닭, 대신 쓰는 것). key 무늬는 fnmatch(* 는 접두어 묶음).
# 감사 docs/SECURITY_AUDIT.md 02–03 과, sources.json 이 '사전 허락·협의'로 분류한 자료 가운데 비상업 웹 배포에도 허락이 필요한 것.
# 토지피복과 인천공항 위치는 더 이상 판 차이가 아니다: 두 판 모두 이용조건이 깨끗한 자료(기후에너지환경부 세분류 토지피복지도 도엽 통계 —
# 공공누리 제1유형, 국가철도공단 공항철도 역위치 — 이용허락범위 제한 없음)로 만들고, WMS 그림과 항공정보간행물(AIP) 좌표는 어느 판에서도 쓰지 않는다.
SAME_IN_BOTH = [
    {"id": "landcover", "what": "칸 토지피복 (대표 피복·비율·숲 종류·논밭)",
     "how": "기후에너지환경부 세분류 토지피복지도 도엽단위 현행화 통계(공공데이터포털 15150509, 공공누리 제1유형)를 칸에 나눈 값. 두 판이 같다.",
     "not_used": "기후에너지환경부 환경공간정보서비스 WMS 그림(Open API 약관이 저장·전송을 막음) — 어느 판에서도 읽지 않는다."},
    {"id": "incheon_airport", "what": "인천공항 위치",
     "how": "국가철도공단 공항철도 역위치(15041331, 이용허락범위 제한 없음)의 제1·2여객터미널 역 좌표 중점 — 공항 기준점이 아님. 두 판이 같다.",
     "not_used": "항공정보간행물(AIP) 공항 기준점 좌표(허락 없는 복제·배포 제한) — 어느 판에서도 쓰지 않는다."},
]
# 어느 판에서도 쓰지 않는 출처 key (validate.py X3 가 sources.json·사이트 JSON 에 없는지 본다)
NEVER_KEYS = ["landcover-me-wms-*", "landcover-me-intro-land-html", "incheon-aip"]
EXCLUDE = [
    {"id": "housing", "what": "아파트 매매·전세 실거래 중위값 (렌즈 2종, 도시·시도 패널 값, 순위·전국 기준, 닮은 도시의 매매가 차이)",
     "sources": ["molit-apartment-sale-*", "molit-apartment-lease-*"],
     "why": ("국토교통부 실거래가 공개시스템의 계약일 기준 내려받기 자료로 직접 계산한 값이다. 그 안내가 외부 공개 때는 신고일 기준 공식통계를 쓰라고 해 "
             "공개판에서는 뺀다 (감사 02). 다른 값으로 메우지 않는다."),
     "instead": None},
    {"id": "mines", "what": "가행 광산 293곳 (광산 아이콘, 도시·시도 패널의 광종별 수)",
     "sources": ["komir-mine-grid"],
     "why": "한국광해광업공단 국내광산검색의 이용 안내가 웹을 통한 제3자 제공에 사전 협의·허락을 요구한다 (감사 03).",
     "instead": None},
    {"id": "hanwoo", "what": "한우 사육 마릿수 (상위 15 아이콘, 도시·시도 패널 값)",
     "sources": ["mtrace-hanwoo-202610"],
     "why": "축산물이력제 저작권보호정책이 저작권자의 사전승낙 없이 제3자에게 제공하는 것을 막는다 (감사 03).",
     "instead": None},
]
# sources.json 이 '사전 허락·협의'로 분류했지만 공개판에 남기는 자료와 까닭 (허락이 상업 이용에만 걸린다)
KEEP_CONSENT = {
    "terrain_srtm30plus": "교육·연구·비영리 목적의 복제·배포는 지정한 고지와 문단을 함께 싣는 조건으로 허용되고, 상업 이용만 UC San Diego 와 협의한다. 고지 원문을 NOTICE.md 와 출처 쪽에 싣는다.",
    "gyeonggi-business-2019": "경기도 승인은 상업적 이용에만 필요하다 (서비스 이용약관 제12조).",
    "gyeonggi-business-2024": "경기도 승인은 상업적 이용에만 필요하다 (서비스 이용약관 제12조).",
}


def excluded_ids():
    return {e["id"] for e in EXCLUDE} if PUBLIC else set()


def is_off(eid):
    """공개판에서 이 묶음을 빼는가."""
    if eid not in {e["id"] for e in EXCLUDE}:
        raise KeyError(eid)
    return PUBLIC


def key_excluded(key, profile=None):
    """출처 key 가 (그 판에서) 빠지는 자료인가 -> 묶음 id 또는 None."""
    if (profile or PROFILE) != "public":
        return None
    for e in EXCLUDE:
        if any(fnmatch.fnmatchcase(key, p) for p in e["sources"]):
            return e["id"]
    return None


def banner():
    line = "=" * 64
    if PUBLIC:
        txt = f"빌드 판: public (공개판) — 공개 배포용. 빼는 자료 {len(EXCLUDE)}묶음: " + ", ".join(e["id"] for e in EXCLUDE)
    else:
        txt = "빌드 판: full (전체판) — 내부 열람용. 공개 배포하지 않는다 (공개판: --profile public)"
    return f"{line}\n{txt}\n{line}"


def never_used(key):
    """두 판 모두 쓰지 않는 출처 key 인가 (토지피복 WMS 그림, 항공정보간행물 좌표)."""
    return any(fnmatch.fnmatchcase(key, p) for p in NEVER_KEYS)

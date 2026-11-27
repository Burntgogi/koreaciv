"""공공데이터포털·KOSIS·공식 기관 후보 출처 조사 스크립트 (문제 1: 인천국제공항, 문제 2: 토지피복).

실행: python -I tools/research5/probe_portal.py
규칙:
- 모든 요청은 순차 실행, 요청 간격 1.0초(0.8~1.2초 범위) 유지.
- User-Agent에 개인정보(이름·이메일) 미포함.
- 모든 응답은 data/raw/layers5/ 아래에 저장하고 data/raw/layers5/manifest.json 에 기록.
"""
import site
import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.append(site.getusersitepackages())

import datetime as dt
import hashlib
import json
import re
import time
from urllib.parse import quote, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
RAW5 = ROOT / "data/raw/layers5"
RAW5.mkdir(parents=True, exist_ok=True)
MANIFEST = RAW5 / "manifest.json"

ALLOWED_SUFFIXES = (".go.kr", ".or.kr", ".re.kr", ".ac.kr", ".korea.kr")
ALLOWED_HOSTS = frozenset({
    "kosis.kr", "www.data.go.kr", "data.go.kr",
    "naciscdn.org", "www.naturalearthdata.com",
    "www.openstreetmap.org", "download.geofabrik.de",
    "esa-worldcover.org", "esa-worldcover.s3.eu-central-1.amazonaws.com",
    "raw.githubusercontent.com", "davidmegginson.github.io",
    "www.wikidata.org", "query.wikidata.org",
    "www.geonames.org", "download.geonames.org",
    "www.airport.kr", "zenodo.org",
})
MAX_BYTES = 100 * 1024 * 1024


def load_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}


def save_manifest(man):
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(MANIFEST)


def host_ok(url):
    u = urlsplit(url)
    if u.scheme != "https":
        return False
    h = (u.hostname or "").lower().rstrip(".")
    return bool(h) and (h in ALLOWED_HOSTS or any(h.endswith(s) or h == s[1:] for s in ALLOWED_SUFFIXES))


class Session:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "Mozilla/5.0"
        self.last = 0.0

    def fetch(self, key, rel_path, url, license_url=None, force=False, method="GET", **kwargs):
        man = load_manifest()
        out_path = (RAW5 / rel_path).resolve()
        if RAW5.resolve() not in out_path.parents:
            raise ValueError(f"RAW5 밖 경로: {rel_path}")
        if not force and key in man and out_path.exists():
            data = out_path.read_bytes()
            if len(data) == man[key]["bytes"] and hashlib.sha256(data).hexdigest() == man[key]["sha256"]:
                return out_path, data
        if not host_ok(url):
            raise ValueError(f"허용되지 않은 URL: {url}")
        wait = 1.0 - (time.monotonic() - self.last)
        if wait > 0:
            time.sleep(wait)
        try:
            resp = self.s.request(method, url, timeout=30, allow_redirects=True, **kwargs)
        finally:
            self.last = time.monotonic()
        if not host_ok(resp.url):
            raise ValueError(f"허용되지 않은 리디렉션 URL: {resp.url}")
        resp.raise_for_status()
        data = resp.content
        if len(data) > MAX_BYTES:
            raise ValueError(f"크기 초과: {len(data)}")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        man[key] = {
            "url": url,
            "final_url": resp.url,
            "file": rel_path,
            "retrieved": dt.datetime.now(dt.timezone.utc).isoformat(),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "license_url": license_url or url,
        }
        save_manifest(man)
        print(f"[saved] {key} -> {rel_path} ({len(data):,} B)", flush=True)
        return out_path, data


def parse_portal_search(html_bytes):
    soup = BeautifulSoup(html_bytes.decode("utf-8", errors="ignore"), "html.parser")
    items = []
    for li in soup.select("div.result-list ul li"):
        a = li.select_one("dl dt a")
        if not a:
            continue
        href = a.get("href", "").strip()
        title = " ".join(a.get_text(" ", strip=True).split())
        desc = li.select_one("dl dd")
        desc_txt = " ".join(desc.get_text(" ", strip=True).split()) if desc else ""
        info = " ".join(li.get_text(" ", strip=True).split())
        items.append((href, title, desc_txt[:160], info[:260]))
    return items


def parse_portal_detail(html_bytes):
    soup = BeautifulSoup(html_bytes.decode("utf-8", errors="ignore"), "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    info = {}
    for th in soup.select("th, dt, span.title"):
        k = " ".join(th.get_text(" ", strip=True).split())
        sib = th.find_next_sibling()
        if sib:
            info[k] = " ".join(sib.get_text(" ", strip=True).split())
    btn = soup.select_one('button[onclick*="fn_fileDataDown("], a[onclick*="fn_fileDataDown("]')
    onclick = btn["onclick"] if btn else None
    kogl = None
    for img in soup.select("img"):
        alt = img.get("alt", "")
        src = img.get("src", "")
        if "공공누리" in alt or "kogl" in src.lower() or "유형" in alt:
            kogl = f"{alt} ({src})"
    return {"title": title, "info": info, "download_onclick": onclick, "kogl": kogl}


def main():
    sess = Session()

    # 1. 공공데이터포털 검색: 문제 1 (인천국제공항) 및 문제 2 (토지피복·팜맵·임상도·지적통계)
    searches = [
        ("search-iiac-airport", "인천국제공항공사", "FILE"),
        ("search-airport-loc", "공항 위치정보", "FILE"),
        ("search-rail-station-std", "전국철도역사정보표준데이터", "STD"),
        ("search-farmmap", "농림수산식품교육문화정보원_팜맵공간정보", "FILE"),
        ("search-landcover-file", "토지피복", "FILE"),
        ("search-forest-map", "산림청 임상도", "FILE"),
        ("search-ngii-landuse", "국토지리정보원 토지이용현황도", "FILE"),
        ("search-cadastral-stat", "지적통계", "FILE"),
    ]
    for key, kw, dtype in searches:
        url = f"https://www.data.go.kr/tcs/dss/selectDataSetList.do?dType={dtype}&keyword={quote(kw)}&perPage=40"
        try:
            _, data = sess.fetch(key, f"portal/{key}.html", url, license_url=url)
            res = parse_portal_search(data)
            print(f"=== {key} ({kw}, {dtype}): {len(res)} results ===", flush=True)
            for href, title, desc, info in res[:15]:
                print(f"  {href} | {title} | {info[:140]}", flush=True)
        except Exception as e:
            print(f"[err] {key}: {e}", flush=True)

    # 2. 이미 알고 있는 환경부·팜맵 포털 상세 페이지 확인
    detail_pks = [
        "15124208",  # 기후에너지환경부_환경공간정보_지역별 중분류 토지피복 면적 현황
        "15166514",  # 기후에너지환경부_환경공간정보_ 중분류 토지피복지도 지역별 현행화 통계
        "15150078",  # 기후에너지환경부_환경공간정보_ 중분류 토지피복지도 구축 현황
        "15150695",  # 기후에너지환경부_환경공간정보_ 중분류 토지피복지도 도엽단위 현행화 통계
        "15104486",  # 팜맵 전북
        "15104487",  # 팜맵 전남
        "15104488",  # 팜맵 15104488 확인!
        "15104489",  # 팜맵 경남
    ]
    for pk in detail_pks:
        url = f"https://www.data.go.kr/data/{pk}/fileData.do"
        try:
            _, data = sess.fetch(f"portal-{pk}", f"portal/portal-{pk}.html", url, license_url=url)
            d = parse_portal_detail(data)
            print(f"=== portal-{pk}: {d['title']} ===", flush=True)
            for k in ("파일데이터명", "제공기관", "확장자", "이용허락범위", "주기성", "수정일", "등록일"):
                if k in d["info"]:
                    print(f"  {k}: {d['info'][k]}", flush=True)
            print(f"  onclick: {d['download_onclick']} | kogl: {d['kogl']}", flush=True)
        except Exception as e:
            print(f"[err] portal-{pk}: {e}", flush=True)


if __name__ == "__main__":
    main()

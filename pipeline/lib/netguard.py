"""수집기 공용 안전장치 (감사 08·09): 출처 key 문자 제한, 원자료 폴더 밖으로 쓰지 않기, 허용 호스트·HTTPS 만 요청·리디렉션, 응답 크기 상한.

출처 목록(site/data/sources.json)이나 매니페스트는 신뢰하지 않는 입력이다 — 거기서 온 key·주소·파일 이름은 이 모듈을 거쳐서만 쓴다.
네트워크에 닿지 않고 시험할 수 있게 판정 함수(check_*)와 요청 함수(fetch, GuardedSession)를 나눴다 (tools/test_netguard.py).
"""
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

# 허용 호스트: 정확한 이름 또는 '.접미사' (그 아래 모든 이름). 출처 목록이 아니라 이 코드가 정한다.
ALLOWED_SUFFIXES = (".go.kr", ".or.kr", ".re.kr", ".ac.kr", ".korea.kr")
ALLOWED_HOSTS = frozenset({
    "kosis.kr", "korea.kr", "www.korea.kr",
    "download.geofabrik.de", "naciscdn.org", "www.naturalearthdata.com", "www.openstreetmap.org",
    "esa-worldcover.org", "esa-worldcover.s3.eu-central-1.amazonaws.com",
    "raw.githubusercontent.com", "api.github.com", "github.com", "objects.githubusercontent.com",
    "coastwatch.pfeg.noaa.gov",
})
MAX_BYTES = 600 * 1024 * 1024          # 응답 하나의 상한 (가장 큰 원자료: OSM 추출 약 300 MB)
MAX_REDIRECTS = 6
KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")


class GuardError(ValueError):
    """안전장치가 막은 요청·경로."""


def check_key(key):
    """출처 key -> 파일 이름에 써도 되는 key. 영숫자로 시작, 영숫자·점·밑줄·붙임표만, '..' 없음."""
    k = str(key)
    if not KEY_RE.fullmatch(k) or ".." in k:
        raise GuardError(f"출처 key 에 허용하지 않는 문자: {k!r}")
    return k


def check_path(root, rel):
    """root 아래 상대 경로 -> 절대 경로. 절대 경로·드라이브·상위 폴더(..)로 root 밖을 가리키면 막는다 (링크도 풀어서 본다)."""
    root_p = Path(root).resolve()
    rel_s = str(rel)
    if not rel_s or os.path.isabs(rel_s) or re.match(r"^[A-Za-z]:", rel_s) or rel_s.startswith(("\\\\", "//")):
        raise GuardError(f"원자료 폴더 밖 경로: {rel_s!r}")
    p = (root_p / rel_s).resolve()
    if p != root_p and root_p not in p.parents:
        raise GuardError(f"원자료 폴더 밖 경로: {rel_s!r} -> {p}")
    return p


def host_allowed(host):
    h = (host or "").lower().rstrip(".")
    return bool(h) and (h in ALLOWED_HOSTS or any(h.endswith(s) or h == s[1:] for s in ALLOWED_SUFFIXES))


def check_url(url):
    """요청해도 되는 주소인가: https, 허용 호스트, 사용자 정보·이상한 포트 없음."""
    u = urlsplit(str(url))
    if u.scheme != "https":
        raise GuardError(f"HTTPS 가 아닌 주소: {url!r}")
    if u.username or u.password:
        raise GuardError(f"주소에 사용자 정보: {url!r}")
    if u.port not in (None, 443, 8443, 8444, 8445):
        raise GuardError(f"허용하지 않는 포트: {url!r}")
    if not host_allowed(u.hostname):
        raise GuardError(f"허용 목록에 없는 호스트: {u.hostname!r} ({url})")
    return url


def next_hop(current, location):
    """리디렉션 대상 -> 검사한 절대 주소 (평문 HTTP 로 내려가는 이동도 막는다)."""
    if not location:
        raise GuardError("Location 없는 리디렉션")
    return check_url(urljoin(current, location))


def read_capped(chunks, limit=MAX_BYTES, declared=None):
    """조각 반복자 -> bytes. 선언된 길이나 실제 받은 양이 상한을 넘으면 멈춘다."""
    if declared is not None and str(declared).isdigit() and int(declared) > limit:
        raise GuardError(f"응답 크기 {int(declared):,} B 가 상한 {limit:,} B 를 넘음")
    out, n = [], 0
    for c in chunks:
        n += len(c)
        if n > limit:
            raise GuardError(f"응답이 상한 {limit:,} B 를 넘음")
        out.append(c)
    return b"".join(out)


def fetch(session, method, url, limit=MAX_BYTES, max_redirects=MAX_REDIRECTS, **kw):
    """requests 세션으로 요청: 매 이동마다 주소를 검사하고(리디렉션은 직접 따라감) 본문을 상한까지만 읽는다. -> (응답, bytes)."""
    current = check_url(url)
    kw.pop("allow_redirects", None)
    kw.pop("stream", None)
    for _ in range(max_redirects + 1):
        resp = session.request_unguarded(method, current, allow_redirects=False, stream=True, **kw)
        if resp.is_redirect:
            nxt = next_hop(current, resp.headers.get("Location"))
            resp.close()
            if resp.status_code in (301, 302, 303) and method.upper() == "POST":
                method, kw = "GET", {k: v for k, v in kw.items() if k not in ("data", "json", "files")}
            current = nxt
            continue
        body = read_capped(resp.iter_content(1 << 16), limit, resp.headers.get("Content-Length"))
        resp._content = body
        resp._content_consumed = True
        return resp, body
    raise GuardError(f"리디렉션 {max_redirects}회 초과: {url}")


def guarded_session_class(base):
    """requests.Session (또는 그 하위 클래스) -> 모든 요청이 fetch 를 거치는 하위 클래스."""

    class Guarded(base):
        max_bytes = MAX_BYTES

        def request_unguarded(self, method, url, **kw):
            return base.request(self, method, url, **kw)

        def request(self, method, url, **kw):
            resp, _ = fetch(self, method, url, limit=self.max_bytes, **kw)
            return resp

    Guarded.__name__ = "Guarded" + base.__name__
    return Guarded


def urllib_open(req_or_url, timeout=60, limit=MAX_BYTES):
    """urllib 로 요청: 첫 주소와 모든 리디렉션을 검사하고 본문을 상한까지만 읽는다. -> (최종 주소, bytes)."""
    import urllib.request

    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            next_hop(req.full_url, newurl)
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    url = req_or_url.full_url if isinstance(req_or_url, urllib.request.Request) else req_or_url
    check_url(url)
    opener = urllib.request.build_opener(Redirect)
    with opener.open(req_or_url, timeout=timeout) as r:
        check_url(r.geturl())
        body = read_capped(iter(lambda: r.read(1 << 16), b""), limit, r.headers.get("Content-Length"))
        return r.geturl(), body

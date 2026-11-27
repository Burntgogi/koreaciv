"""수집기 안전장치 시험 (감사 08·09) — 네트워크에 닿지 않는다. 가짜 세션·가짜 응답·임시 폴더만 쓴다.

실행: python tools/test_netguard.py
"""
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
sys.stdout.reconfigure(encoding="utf-8")

import requests  # noqa: E402

from lib import netguard as NG  # noqa: E402

results = []


def case(name, fn, expect_block):
    try:
        fn()
        got = "통과시킴"
    except NG.GuardError as e:
        got = f"막음 ({e})"
    ok = got.startswith("막음") == expect_block
    results.append(ok)
    print(f"[{'맞음' if ok else '틀림'}] {name} — {got[:150]}")


# ---- 1. 출처 key 문자 ----
for k, bad in [("terrain_srtm30plus", False), ("kosis-101-DT_1EB002", False), ("../../etc/passwd", True), ("a/b", True), ("a\\b", True),
               ("..", True), ("", True), ("c:evil", True), (".hidden", True), ("x" * 200, True), ("가나", True), ("ok.name-1_2", False)]:
    case(f"key {k[:30]!r}", lambda k=k: NG.check_key(k), bad)

# ---- 2. RAW 밖 경로 ----
with tempfile.TemporaryDirectory() as td:
    raw = Path(td) / "raw"
    raw.mkdir()
    for rel, bad in [("layers4/terrain.html", False), ("a.html", False), ("../outside.html", True), ("layers4/../../x", True),
                     ("/etc/passwd", True), ("C:/Windows/x", True), ("C:x", True), ("\\\\server\\share\\x", True), ("", True)]:
        case(f"경로 {rel!r}", lambda rel=rel: NG.check_path(raw, rel), bad)

# ---- 3. 주소: HTTPS·허용 호스트 ----
for u, bad in [("https://www.data.go.kr/data/1/fileData.do", False), ("https://kosis.kr/x", False), ("https://coastwatch.pfeg.noaa.gov/erddap/", False),
               ("http://www.khs.go.kr/cha/SearchKindOpenapiList.do", True), ("https://evil.example.com/", True), ("https://go.kr.evil.com/", True),
               ("https://www.data.go.kr@evil.com/", True), ("https://user:pw@www.data.go.kr/", True), ("file:///etc/passwd", True),
               ("https://www.data.go.kr:2222/", True), ("ftp://kosis.kr/", True), ("https://map.wamis.go.kr:8444/geoserver", False)]:
    case(f"주소 {u}", lambda u=u: NG.check_url(u), bad)

# ---- 4. 리디렉션 대상 ----
for cur, loc, bad in [("https://www.data.go.kr/a", "/b", False), ("https://www.data.go.kr/a", "https://kosis.kr/c", False),
                      ("https://www.khs.go.kr/a", "http://www.khs.go.kr/a", True), ("https://www.data.go.kr/a", "https://evil.example.com/", True),
                      ("https://www.data.go.kr/a", "//evil.example.com/x", True), ("https://www.data.go.kr/a", None, True)]:
    case(f"이동 {cur} -> {loc}", lambda cur=cur, loc=loc: NG.next_hop(cur, loc), bad)

# ---- 5. 크기 상한 ----
case("선언된 길이가 상한 초과", lambda: NG.read_capped([b"x"], limit=10, declared="11"), True)
case("받은 양이 상한 초과", lambda: NG.read_capped([b"x" * 6, b"x" * 6], limit=10), True)
case("상한 안", lambda: NG.read_capped([b"x" * 5, b"x" * 5], limit=10), False)


# ---- 6. 가짜 세션으로 요청·리디렉션 따라가기 ----
class FakeResp:
    def __init__(self, status, headers=None, body=b""):
        self.status_code, self.headers, self._body = status, headers or {}, body
        self.url = None

    @property
    def is_redirect(self):
        return self.status_code in (301, 302, 303, 307, 308) and "Location" in self.headers

    def iter_content(self, n):
        for i in range(0, len(self._body), n):
            yield self._body[i:i + n]

    @property
    def content(self):
        return self._content

    def close(self):
        pass

    def raise_for_status(self):
        pass


class FakeBase(requests.Session):
    script = {}
    seen = []

    def request(self, method, url, **kw):
        FakeBase.seen.append(url)
        if url not in self.script:
            raise AssertionError(f"막혔어야 할 주소에 요청함: {url}")
        r = self.script[url]
        r.url = url
        return r


Guarded = NG.guarded_session_class(FakeBase)
s = Guarded()
FakeBase.script = {"https://www.data.go.kr/start": FakeResp(302, {"Location": "https://kosis.kr/next"}),
                   "https://kosis.kr/next": FakeResp(200, {"Content-Length": "5"}, b"hello")}
case("허용 호스트로만 이동하면 받음", lambda: s.get("https://www.data.go.kr/start"), False)
r = s.get("https://www.data.go.kr/start")
results.append(r.content == b"hello")
print(f"[{'맞음' if r.content == b'hello' else '틀림'}] 받은 본문 = {r.content!r}")
FakeBase.script = {"https://www.data.go.kr/start": FakeResp(302, {"Location": "https://evil.example.com/steal"})}
FakeBase.seen = []
case("허용 밖 호스트로 리디렉션 → 막고 그 주소에는 요청하지 않음", lambda: s.get("https://www.data.go.kr/start"), True)
results.append(FakeBase.seen == ["https://www.data.go.kr/start"])
print(f"[{'맞음' if FakeBase.seen == ['https://www.data.go.kr/start'] else '틀림'}] 요청한 주소 {FakeBase.seen}")
FakeBase.script = {"https://www.khs.go.kr/a": FakeResp(301, {"Location": "http://www.khs.go.kr/a"})}
case("HTTPS → 평문 HTTP 이동 막음", lambda: s.get("https://www.khs.go.kr/a"), True)
loop = {f"https://kosis.kr/{i}": FakeResp(302, {"Location": f"https://kosis.kr/{i + 1}"}) for i in range(10)}
FakeBase.script = loop
case("리디렉션 6회 초과 막음", lambda: s.get("https://kosis.kr/0"), True)
FakeBase.script = {"https://kosis.kr/big": FakeResp(200, {}, b"x" * 2000)}
s.max_bytes = 1000
case("본문이 세션 상한을 넘으면 막음", lambda: s.get("https://kosis.kr/big"), True)
case("처음 주소가 허용 밖이면 요청 전에 막음", lambda: s.get("https://evil.example.com/"), True)

# ---- 7. collect_layers4: 변조된 sources.json 의 key·주소 (임시 폴더에서, 네트워크 없음) ----
import collect_layers4 as C4  # noqa: E402

with tempfile.TemporaryDirectory() as td:
    C4.RAW = Path(td)
    C4.MANIFEST = C4.RAW / "manifest.json"
    C4.SOURCES = [{"key": "../../pwned", "url": "https://www.korea.kr/x"},
                  {"key": "good-key", "url": "https://evil.example.com/x"},
                  {"key": "good-key2", "url": "http://plain.go.kr/x"},
                  {"key": "fine_key", "url": "https://www.korea.kr/ok"}]
    names = [n for n, _ in C4.primary()]
    ok = all("/" not in n and "\\" not in n and ".." not in n for n in names) and "fine_key.html" in names and not any("pwned" in n for n in names)
    results.append(ok)
    print(f"[{'맞음' if ok else '틀림'}] collect_layers4.primary(): 변조된 key·주소는 건너뛰고 남은 이름 {[n for n in names if 'key' in n]}")
    calls = []
    C4.NG.fetch = lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(AssertionError("네트워크에 닿으면 안 됨"))
    C4.collect([("../escape.html", "https://www.korea.kr/x"), ("ok.html", "https://evil.example.com/x"), ("ok2.html", "http://www.korea.kr/x")])
    fails = json.loads((C4.RAW / "failures.json").read_text("utf8"))
    outside = list(Path(td).parent.glob("escape.html"))
    ok = not calls and set(fails) == {"../escape.html", "ok.html", "ok2.html"} and all("안전장치" in v["reason"] for v in fails.values()) and not outside
    results.append(ok)
    print(f"[{'맞음' if ok else '틀림'}] collect_layers4.collect(): 세 항목 모두 요청 전에 막고 실패 기록 {sorted(fails)}, RAW 밖 파일 {len(outside)}, 요청 {len(calls)}")

# ---- 8. 국가유산 수집기 주소 (감사 09) ----
src = (ROOT / "pipeline" / "collect_keyless.py").read_text("utf8")
ok = "http://www.khs.go.kr" not in src and "https://www.khs.go.kr/cha/SearchKindOpenapiList.do" in src and "NG.urllib_open" in src
results.append(ok)
print(f"[{'맞음' if ok else '틀림'}] collect_keyless.py: 국가유산 주소가 HTTPS, 요청은 NG.urllib_open (평문 이동 거부)")

n_ok = sum(results)
print(f"\n안전장치 시험 {len(results)}개 중 맞음 {n_ok}개, 틀림 {len(results) - n_ok}개 (네트워크 요청 0)")
sys.exit(0 if n_ok == len(results) else 1)

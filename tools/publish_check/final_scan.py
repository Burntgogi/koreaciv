"""공개 직전 점검: .gitignore 를 적용했을 때 올라갈 파일 전부에서 비밀·개인정보·큰 파일·원자료 형식을 찾는다."""
import os, re, subprocess, sys, tempfile, collections, math
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
g = tempfile.mkdtemp()
subprocess.run(["git", "--git-dir", g, "init", "-q"], check=True)
files = subprocess.run(["git", "--git-dir", g, "--work-tree", ROOT, "ls-files", "--others", "--exclude-standard", "-z"],
                       capture_output=True, check=True).stdout.decode("utf-8").split("\0")
files = [f for f in files if f]
PAT = {
    "email": re.compile(rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "win-user-path": re.compile(rb"(?i)[A-Z]:[\/]+Users[\/]+[^\/\s\"']+"),
    "secret-key": re.compile(rb"(AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|gho_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY)"),
    "jwt": re.compile(rb"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "query-secret": re.compile(rb"(?i)(serviceKey|api[_-]?key|crtfc_key|access[_-]?token|auth[_-]?token|password|passwd|secret)\s*[=:]\s*['\"]?[A-Za-z0-9%+/=_-]{8,}"),
    "session": re.compile(rb"(?i)(JSESSIONID|PHPSESSID|ASP\.NET_SessionId)=[A-Za-z0-9._-]{8,}"),
    "phone-kr": re.compile(rb"01[016789]-?\d{3,4}-?\d{4}"),
    "rrn": re.compile(rb"\b\d{6}-[1-4]\d{6}\b"),
}
# 찾을 개인 이름·계정은 저장소에 넣지 않는다: 같은 폴더의 private_terms.txt(.gitignore) 한 줄에 하나.
_terms_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "private_terms.txt")
if os.path.exists(_terms_path):
    _terms = [t.strip() for t in open(_terms_path, encoding="utf-8") if t.strip()]
    if _terms:
        PAT["names"] = re.compile("|".join(re.escape(t) for t in _terms).encode())
ALLOW_EMAIL = re.compile(rb"(noreply|users\.noreply\.github\.com|invent@ucsd\.edu|@ucsd\.edu|@example\.|@googlegroups|@openstreetmap|@noto|@google\.com|@adobe|license|copyright|@sil\.org|fonts?@|@apache\.org)")
hits = collections.defaultdict(list); big = []; types = collections.Counter()
for f in files:
    p = os.path.join(ROOT, f); n = os.path.getsize(p); types[os.path.splitext(f)[1].lower()] += 1
    if n > 1_000_000: big.append((f, n))
    b = open(p, "rb").read()
    for k, rx in PAT.items():
        for m in rx.finditer(b):
            s = m.group(0)
            if k == "email" and (ALLOW_EMAIL.search(s) or s.endswith(b".png") or s.endswith(b".svg")):
                continue
            line = b.count(b"\n", 0, m.start()) + 1
            hits[k].append((f, line, s[:4].decode("utf-8", "replace") + "…"))
print(f"올라갈 파일 {len(files)}개, {sum(os.path.getsize(os.path.join(ROOT, f)) for f in files)/1e6:.2f} MB")
print("확장자:", dict(types.most_common()))
print("1 MB 넘는 파일:", big or "없음")
for k in PAT:
    v = hits.get(k, [])
    print(f"[{k}] {len(v)}건", v[:8])
bad_ext = [f for f in files if os.path.splitext(f)[1].lower() in {".xlsx", ".xls", ".zip", ".tif", ".tiff", ".shp", ".dbf", ".pbf", ".hwp", ".pdf", ".env", ".pem", ".key", ".npz", ".pkl"}]
print("원자료·비밀 형식 파일:", bad_ext or "없음")

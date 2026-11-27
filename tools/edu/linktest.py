"""교육 쪽의 '지도에서 열기' 링크 점검: python tools/edu/linktest.py [content.json 경로] [--shots DIR] [--only id,id]
site/ 를 임시 서버로 띄워 링크마다 두 판(기존판·신여지도)을 머리 없는 브라우저로 열고, 열린 상태(렌즈·선택·층·카메라)를
해시가 뜻한 상태와 견준다. 결과는 표준 출력과 tools/edu/linktest_result.json 에 적는다. 자료를 고치지 않는다.
"""
import functools, http.server, json, os, socketserver, sys, threading
from urllib.parse import parse_qs
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SITE = os.path.join(ROOT, "site")


class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def serve():
    s = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(Q, directory=SITE))
    s.daemon_threads = True
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, s.server_address[1]


def collect(content):
    """content.json 에서 (id, 판별 해시)를 모두 모은다. 해시는 두 판에 같은 것을 넘긴다 (수업안이 editions 로 판을 좁히면 그 판만).
    옛 초안 꼴(links: {classic, yeojido})도 읽는다."""
    out = []
    def add(i, h, eds=None):
        if isinstance(h, dict):
            out.append((i, h))
        elif h:
            out.append((i, {e: h for e in (eds or ("classic", "yeojido"))}))
    for j, x in enumerate(content.get("start", {}).get("steps", []) if isinstance(content.get("start"), dict) else []):
        add(f"start{j + 1}", x.get("hash"))
    for l in content.get("lessons", []):
        eds = l.get("editions")
        add(l["id"], (l.get("open") or {}).get("hash") or l.get("links"), eds)
        for j, st in enumerate(l.get("steps", [])):
            if isinstance(st, dict):
                add(f"{l['id']}.s{j + 1}", st.get("hash"), eds)
        add(f"{l['id']}.harder", l.get("harder_hash"), eds)
    for k in ("quick", "projects"):
        for q in content.get(k, []):
            add(q["id"], q.get("hash") or q.get("links"))
    return out


STATE_JS = {
    "classic": """() => { const a = window.app; if (!a) return null; return {
        lens: a.lens ? a.lens.id : null, city: a.selCity ?? null, state: a.selState || null,
        item: a.selItem ? a.selItem.id : null, route: a.selRoute ? a.selRoute.id : null,
        mode: a.panel && a.panel.mode || null, tab: a.panelTab || null,
        ly: Object.keys(a.layerOn).filter(k => a.layerOn[k]).sort(), hide: [...a.subOff].sort(),
        cam: [Math.round(a.cam.x), Math.round(a.cam.y), +a.cam.scale.toFixed(3)], layers: !!a.layers, intro: false, report: null }; }""",
    "yeojido": """() => { const a = window.app; if (!a) return null; const s = a.sel || {}; return {
        lens: a.lens ? a.lens.id : null, city: s.type === 'city' ? s.id : null, state: s.type === 'state' ? s.id : null,
        item: s.type === 'item' ? s.id : null, route: s.type === 'route' ? s.id : null,
        mode: s.type || null, tab: null,
        ly: Object.keys(a.layerOn).filter(k => a.layerOn[k]).sort(), hide: [...a.subOff].sort(),
        cam: [Math.round(a.cam.x), Math.round(a.cam.y), +a.cam.scale.toFixed(3)], layers: !!a.layerMap, intro: !!a.introOn,
        report: a.masthead && a.masthead.reportId ? a.masthead.reportId() : null }; }""",
}
DEFAULT_LY = ["infra", "resources", "wonders"]
PATH = {"classic": "/", "yeojido": "/yeojido/"}


def expect(h, lens_ids):
    p = {k: v[0] for k, v in parse_qs(h.lstrip("#"), keep_blank_values=True).items()}
    e = {"lens": p.get("lens") or None}
    if e["lens"] and e["lens"] not in lens_ids:
        e["lens"] = None  # 이 판(profile)에 없는 렌즈
        e["lens_absent"] = p.get("lens")
    for k in ("item", "route", "city", "state"):
        if p.get(k):
            e["target"] = (k, int(p[k]) if k == "city" else p[k])
            break
    e["ly"] = sorted(x for x in p["ly"].split(",") if x) if "ly" in p else DEFAULT_LY
    e["hide"] = sorted(x for x in (p.get("hide") or "").split(",") if x)
    e["report"] = p.get("report")
    e["v"] = [float(x) for x in p["v"].split(",")] if p.get("v") else None
    return e


def check(ed, e, st):
    bad = []
    if st is None:
        return ["app 없음"]
    if st["lens"] != e["lens"]:
        bad.append(f"렌즈 {st['lens']} ≠ {e['lens']}")
    if "target" in e:
        k, v = e["target"]
        if st.get(k) != v:
            bad.append(f"선택 {k}={st.get(k)} ≠ {v}")
    elif e.get("report") and e["report"] != "0":
        if ed == "yeojido":
            want = "nation" if e["report"] == "1" else e["report"]
            got = st["mode"] if e["report"] == "1" else st["report"]
            if got != want:
                bad.append(f"보고서 {got} ≠ {want}")
        elif e["report"] == "1" and st["mode"] != "nation":
            bad.append(f"보고서 mode={st['mode']}")
    elif any(st.get(k) is not None for k in ("city", "state", "item", "route")):
        bad.append("뜻하지 않은 선택")
    if st["ly"] != e["ly"]:
        bad.append(f"층 {st['ly']} ≠ {e['ly']}")
    if sorted(set(st["hide"])) != sorted(set(e["hide"])):
        bad.append(f"끈 세부 {st['hide']} ≠ {e['hide']}")
    if st["intro"]:
        bad.append("표지가 지도를 가림")
    if e["v"] and (abs(st["cam"][2] - e["v"][2]) > 0.002):
        bad.append(f"축척 {st['cam'][2]} ≠ {e['v'][2]}")
    return bad


def main():
    args = sys.argv[1:]
    shots = None; only = None; path = os.path.join(SITE, "edu", "content.json")
    i = 0
    while i < len(args):
        if args[i] == "--shots": shots = args[i + 1]; i += 2
        elif args[i] == "--only": only = set(args[i + 1].split(",")); i += 2
        else: path = args[i]; i += 1
    content = json.load(open(path, encoding="utf-8"))
    links = collect(content)
    if only:
        links = [x for x in links if x[0] in only]
    lens_ids = {l["id"] for l in json.load(open(os.path.join(SITE, "data", "lenses.json"), encoding="utf-8"))["lenses"]}
    world = json.load(open(os.path.join(SITE, "data", "world.json"), encoding="utf-8"))
    profile = world.get("build_profile", "full")
    s, port = serve()
    base = f"http://127.0.0.1:{port}"
    res = {"profile": profile, "tested": 0, "failed": [], "errors": {}, "rows": []}
    if shots:
        os.makedirs(shots, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for ed in ("classic", "yeojido"):
            ctx = b.new_context(viewport={"width": 1280, "height": 800})
            for lid, lk in links:
                h = lk.get(ed)
                if not h:
                    continue
                pg = ctx.new_page(); errs = []
                pg.on("console", lambda m, errs=errs: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
                pg.on("pageerror", lambda e, errs=errs: errs.append("PAGEERROR " + str(e)))
                pg.goto(base + PATH[ed] + h)
                try:
                    pg.wait_for_function("window.app && (window.app.layers || window.app.layerMap)", timeout=30000)
                except Exception:
                    errs.append("층 자료를 30초 안에 못 받음")
                pg.wait_for_timeout(700)
                st = pg.evaluate(STATE_JS[ed])
                e = expect(h, lens_ids)
                bad = check(ed, e, st)
                res["tested"] += 1
                row = {"id": lid, "edition": ed, "hash": h, "ok": not bad, "bad": bad, "state": st, "console": errs}
                if e.get("lens_absent"):
                    row["lens_absent"] = e["lens_absent"]
                res["rows"].append(row)
                if bad or errs:
                    res["failed"].append(f"{lid}/{ed}")
                    print("✗", lid, ed, h, bad, errs[:2])
                if shots:
                    pg.screenshot(path=os.path.join(shots, f"{lid}_{ed}.png"))
                pg.close()
            ctx.close()
        b.close()
    s.shutdown()
    json.dump(res, open(os.path.join(ROOT, "tools", "edu", "linktest_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"자료 판(profile): {profile} · 링크 {res['tested']}건 점검 · 실패 {len(res['failed'])}건")
    return 1 if res["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())

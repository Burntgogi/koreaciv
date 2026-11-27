"""자료 글이 HTML 로 풀리지 않는지 (감사 07): site/ 사본의 data/*.json 의 글(이름·설명·규칙·출처 …)에 마크업을 넣고, 임시 폴더에서 띄워
두 판과 출처 쪽의 화면을 두루 연 뒤 ① 넣은 스크립트가 하나도 돌지 않았고 ② 넣은 요소(<b class=xss-mark>, <img src=x>)가 DOM 에 하나도 생기지 않았고
③ 넣은 글이 글자로는 보이는지 본다. 원래 site/ 는 건드리지 않는다.

실행: python tools/qa_xss.py   (Playwright + 설치된 Chrome)
"""
import functools
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
MARK = "<b class=xss-mark>X</b><img src=x onerror=__xss(1)><svg onload=__xss(2)>"
# 찾기 열쇠·코드·색·형식처럼 화면 글이 아니라 자료를 잇는 값은 그대로 둔다 (바꾸면 화면이 아니라 자료 연결이 깨진다)
KEEP = {"id", "code", "key", "kind", "sido", "sgg", "group", "lens", "near", "t", "k", "scale", "format", "higher_is", "ramp", "color", "colors",
        "layer", "sub", "precision", "place_from", "source_id", "cells", "keys", "kinds", "cover_keys", "srcs", "mode", "ref", "fmt", "dir",
        "profile", "phase", "version", "level", "grade", "file", "path", "url", "license_url", "href", "categories", "components", "basis_key",
        "same", "diff", "ind", "counties", "codes", "sgg_codes", "member_of", "unit_label", "share_keys", "names", "excluded", "first", "second",
        "tier", "inst_kind", "fuel", "fuel_raw", "status", "item", "route", "a", "b", "cover_src", "crop_kind", "forest_kind", "retired", "removed",
        "unit", "label_key", "source", "attribution", "spans", "members", "successors", "full_list", "sha256", "emoji_key", "industry_keys", "ksic", "draw_priority", "jobs_map"}
results = []


COUNT = [0]


def taint(o, key=None):
    n = COUNT
    if key in KEEP:
        return o
    if isinstance(o, dict):
        return {k: taint(v, k) for k, v in o.items()}
    if isinstance(o, list):
        return [taint(v, key) for v in o]
    if isinstance(o, str) and o and not o.startswith("#") and len(o) < 4000:
        n[0] += 1
        return o + MARK
    return o


def rec(name, ok, note=""):
    results.append(ok)
    print(f"[{'통과' if ok else '실패'}] {name}" + (f" — {note}" if note else ""), flush=True)


def serve(root):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


INIT = """
window.__xssHits = [];
window.__xss = (k) => { window.__xssHits.push(k); };
new MutationObserver((ms) => { for (const m of ms) for (const nd of m.addedNodes) {
  if (nd.nodeType !== 1) continue;
  const bad = (nd.matches && nd.matches('b.xss-mark, img[src="x"], svg[onload]')) ? [nd] : [...(nd.querySelectorAll ? nd.querySelectorAll('b.xss-mark, img[src="x"], svg[onload]') : [])];
  for (const b of bad) { const c = b.parentElement && b.parentElement.closest('[id]'); const q = b.parentElement ? b.parentElement.tagName + '.' + String(b.parentElement.className || '').slice(0, 20) : '?'; window.__xssHits.push('element:' + b.tagName + ' in #' + (c ? c.id : '?') + ' ' + q); }
} }).observe(document, { childList: true, subtree: true });
"""
CHECK = "() => { const h = window.__xssHits.splice(0); const u = [...new Set(h)]; return { hits: u.slice(0, 14), n: h.length, dom: document.querySelectorAll('b.xss-mark, img[src=\"x\"], svg[onload]').length, text: document.body.innerText.includes('<b class=xss-mark>') }; }"


def original(pg, base, errs):
    pg.goto(base + "index.html")
    pg.wait_for_function("window.app && window.app.layerR && window.app.layers", timeout=40000)
    pg.wait_for_timeout(600)
    steps = {
        "보고서 메뉴·보고서 전부": "() => { const t = app.topbar; t.openMenu(document.querySelector('[data-reports-menu]')); t.closeMenu(); for (const r of app.nation.reports.items) { app.report.open(r.id); app.report.mode = 1; app.report.render(); } app.report.close(); }",
        "렌즈 전부·범례": "() => { for (const l of app.lenses.lenses) app.setLens(l.id); app.setLens(null); app.lensbar.openGroup = 'land'; app.lensbar.render(); }",
        "칸 툴팁 (육지·바다·외국, 렌즈 켬)": "() => { const W = app.world; app.setLens('health'); for (let i = 0; i < W.owner.length; i += 97) app.tooltip.showCell(i, 50, 50); app.setLens(null); for (let i = 0; i < W.owner.length; i += 131) app.tooltip.showCell(i, 50, 50); }",
        "도시·층 항목·교역로 툴팁": "() => { for (const c of app.cities.slice(0, 30)) app.tooltip.showCity(c, 50, 50); for (const s of app.states) app.tooltip.showState(s, 50, 50); for (const it of [...app.layerR.byId.values()].slice(0, 400)) app.tooltip.showItem(it, [it], 50, 50, true); for (const r of [...app.layerR.routeById.values()].slice(0, 10)) app.tooltip.showRoute(r, 50, 50); }",
        "도시 패널 (탭 전부)": "() => { for (const c of app.cities.filter((_, i) => i % 9 === 0)) { app.selectCity(c.id); for (const tb of document.querySelectorAll('#panel [data-tab]')) tb.click(); } }",
        "시도·전국 패널": "() => { for (const s of app.states) app.selectState(s.code); app.showNation(); }",
        "층 항목 패널·교역로 패널": "() => { for (const it of [...app.layerR.byId.values()].filter((_, i) => i % 23 === 0)) app.selectItem(it); for (const r of [...app.layerR.routeById.values()].slice(0, 4)) app.selectRoute(r); app.clearSelection(); }",
        "연감 갈피 전부": "() => { app.almanac.open('terrain'); for (const b of document.querySelectorAll('#almanac [data-tab]')) { app.almanac.tab(b.dataset.tab); } app.almanac.close(); }",
        "찾기·층 조작·공유·도움말": "() => { app.search.open(); app.search.input.value = '수'; app.search.update(); app.search.close && app.search.close(); app.layerctl.open = true; app.layerctl.render(); app.share.toggle(document.getElementById('share-btn')); app.share.close(); app.help.toggle(); app.help.close(); }",
    }
    for name, js in steps.items():
        try:
            pg.evaluate(js)
            pg.wait_for_timeout(250)
        except Exception as e:  # noqa: BLE001
            errs.append(f"{name}: {str(e)[:160]}")
        st = pg.evaluate(CHECK)
        rec(f"기존판 · {name}", st["n"] == 0 and st["dom"] == 0, f"실행 {st['n']} · 요소 {st['dom']}" + (f" {st['hits']}" if st["n"] else ""))
    pg.evaluate("() => { app.almanac.open('sources'); }")
    pg.wait_for_timeout(800)
    st = pg.evaluate(CHECK)
    rec("기존판 · 넣은 글이 글자로 보임 (연감 › 출처)", st["text"], "본문에 '<b class=xss-mark>' 글자가 있음" if st["text"] else "글자로도 안 보임")


def yeojido(pg, base, errs):
    pg.goto(base + "yeojido/index.html#intro=0")
    pg.wait_for_function("window.app && window.app.layerMap", timeout=40000)
    pg.wait_for_timeout(600)
    steps = {
        "고을·도·전국 장": "() => { for (const c of app.D.cities.filter((_, i) => i % 11 === 0)) app.selectCity(c.id); for (const s of app.D.states) app.selectState(s.code); app.showNation(); }",
        "렌즈 전부": "() => { for (const l of app.D.lenses.list) app.setLens(l.id); app.setLens(null); }",
        "툴팁": "() => { const W = app.D.world; for (let i = 0; i < W.owner.length; i += 113) app.tooltip.showCell(i, 60, 60); }",
        "연감 갈피 전부": "async () => { for (const t of ['terrain', 'lenses', 'layers', 'yields', 'sources', 'notes']) { try { app.almanac.open(t); await new Promise((r) => setTimeout(r, 300)); } catch (e) {} } app.almanac.close(); }",
    }
    for name, js in steps.items():
        try:
            pg.evaluate(js)
            pg.wait_for_timeout(400)
        except Exception as e:  # noqa: BLE001
            errs.append(f"{name}: {str(e)[:160]}")
        st = pg.evaluate(CHECK)
        rec(f"신여지도 · {name}", st["n"] == 0 and st["dom"] == 0, f"실행 {st['n']} · 요소 {st['dom']}" + (f" {st['hits']}" if st["n"] else ""))


def sources_page(pg, base, errs):
    pg.goto(base + "sources/index.html")
    pg.wait_for_selector("body.is-ready", timeout=20000)
    for d in pg.query_selector_all("details"):
        d.evaluate("(e) => e.open = true")
    pg.wait_for_timeout(300)
    st = pg.evaluate(CHECK)
    rec("출처 쪽 · 모든 칸·접힌 칸", st["n"] == 0 and st["dom"] == 0 and st["text"], f"실행 {st['n']} · 요소 {st['dom']} · 글자로 보임 {st['text']}")


def main():
    tmp = tempfile.mkdtemp(prefix="koreaciv-xss-")
    try:
        dst = os.path.join(tmp, "site")
        shutil.copytree(SITE, dst, ignore=shutil.ignore_patterns("edu"))
        n0 = 0
        for fn in os.listdir(os.path.join(dst, "data")):
            if fn.endswith(".json"):
                p = os.path.join(dst, "data", fn)
                J = json.load(open(p, encoding="utf-8"))
                T = taint(J, None)
                json.dump(T, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        n0 = COUNT[0]
        prof = (json.load(open(os.path.join(SITE, "data", "sources.json"), encoding="utf-8")).get("profile") or {}).get("profile", "full")
        print(f"사본 {dst} · 마크업을 넣은 글 {n0:,}개 · 판 {prof}", flush=True)
        srv, base = serve(dst)
        errs, pageerrs, miss = [], [], []
        with sync_playwright() as p:
            br = p.chromium.launch(channel="chrome")
            for fn in (original, yeojido, sources_page):
                ctx = br.new_context(viewport={"width": 1440, "height": 900}, service_workers="block")
                ctx.add_init_script(INIT)
                pg = ctx.new_page()
                pg.on("pageerror", lambda e, f=fn.__name__: pageerrs.append(f"{f}: {str(e)[:200]}"))
                pg.on("console", lambda m, f=fn.__name__: pageerrs.append(f"{f} console.{m.type}: {m.text[:200]}") if m.type == "error" and "Failed to load resource" not in m.text else None)
                pg.on("response", lambda r, f=fn.__name__: (miss.append(f"{f}: {r.status} {r.url}") if r.status >= 400 else None))
                try:
                    fn(pg, base, errs)
                except Exception as e:  # noqa: BLE001
                    errs.append(f"{fn.__name__}: 열지 못함 {str(e)[:120]}")
                    rec(f"{fn.__name__} 쪽을 열고 조작함", False, "; ".join(pageerrs[-4:]))
                ctx.close()
            br.close()
        srv.shutdown()
        rec("페이지 예외·조작 오류 없음 (마크업을 넣은 자료로)", not errs and not pageerrs, "; ".join((errs + pageerrs)[:6]))
        injected = [m for m in miss if m.rstrip("/").endswith("/x")]
        rec("넣은 <img src=x> 가 요청되지 않음 (요소가 만들어지지 않았음)", not injected, f"4xx 응답 {len(miss)}건" + (f": {sorted(set(miss))[:4]}" if miss else ""))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = sum(results)
    print(f"\n주입 시험 {len(results)}개 중 통과 {ok}개, 실패 {len(results) - ok}개 (판 {prof})")
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())

"""토지피복(도엽 통계)·인천공항 갈무리 → docs/screenshots/12_*.png  (site/data 그대로, 보통 공개판)

두 프런트엔드(기존판 k, 신여지도 y)에서 전국·호남 평야·제주·휴전선 접경·서울·숲 렌즈·숲 종류 확대·인천공항 패널, 출처 쪽.
콘솔 오류를 센다. 실행: python tools/screens_12.py
"""
import functools
import http.server
import json
import os
import sys
import threading

from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
SHOT = os.path.join(ROOT, "docs", "screenshots")


def serve(root):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    class Srv(http.server.ThreadingHTTPServer):
        request_queue_size = 128   # 기본 5 로는 지도가 자료 파일을 한꺼번에 받을 때 연결이 거절될 때가 있다
    srv = Srv(("127.0.0.1", 0), functools.partial(Quiet, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def k_open(pg, base, hsh, wait=2200):
    pg.goto("about:blank")   # 해시만 바뀌면 같은 문서로 남으므로 새로 연다
    pg.mouse.move(5, 895)
    pg.goto(base + "index.html" + hsh)
    pg.wait_for_function("window.app && window.app.layerR && window.app.layers", timeout=40000)
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(wait)


def y_open(pg, base, hsh, wait=2600):
    pg.goto("about:blank")
    pg.mouse.move(5, 895)
    pg.goto(base + "yeojido/index.html" + hsh)
    pg.wait_for_function('document.body.classList.contains("is-ready")', timeout=40000)
    pg.wait_for_timeout(wait)


def main():
    os.makedirs(SHOT, exist_ok=True)
    W = json.load(open(os.path.join(SITE, "data", "world.json"), encoding="utf-8"))
    C = json.load(open(os.path.join(SITE, "data", "cities.json"), encoding="utf-8"))
    INF = json.load(open(os.path.join(SITE, "data", "infrastructure.json"), encoding="utf-8"))
    xy = {c["name"]: (c["x"], c["y"]) for c in C}
    icn = next(i for i in INF["items"] if i["name"] == "인천공항")
    # 확대할 곳: (이름, 도시 이름 또는 좌표, 기존판 배율 배수, 신여지도 배율)
    spots = [("honam", xy["김제시"], 5, 0.85), ("jeju", ((xy["제주시"][0] + xy["서귀포시"][0]) / 2, (xy["제주시"][1] + xy["서귀포시"][1]) / 2), 4, 0.6),
             ("dmz", xy["철원군"], 4.5, 0.7), ("seoul", xy["서울"], 5, 0.85), ("forest_types_inje", xy["인제군"], 6, 1.0)]
    log = {"profile": W.get("build_profile"), "errors": {}}
    srv, base = serve(SITE)
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chrome")
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append("PAGEERROR " + str(e)[:160]))
        pg.on("console", lambda m: errs.append(m.text[:160]) if m.type == "error" else None)
        pg.on("response", lambda r: errs.append(f"HTTP {r.status} {r.url}") if r.status >= 400 else None)
        pg.on("requestfailed", lambda r: errs.append(f"요청 실패 {r.url} {r.failure}"))
        # ---------- 기존판 ----------
        k_open(pg, base, "")
        pg.screenshot(path=os.path.join(SHOT, "12_k_national.png"))
        mins = pg.evaluate("() => app.cam.minScale")
        for nm, (x, y), kz, _ in spots:
            k_open(pg, base, f"#v={x:.1f},{y:.1f},{mins * kz:.4f}", 2800)
            if nm in ("forest_types_inje", "jeju", "dmz"):
                pg.mouse.move(720, 450)
                pg.wait_for_timeout(700)
            pg.screenshot(path=os.path.join(SHOT, f"12_k_{nm}.png"))
        k_open(pg, base, "#lens=forest")
        pg.screenshot(path=os.path.join(SHOT, "12_k_lens_forest.png"))
        k_open(pg, base, "", 1500)
        pg.evaluate(f"() => app.selectItem(app.layerR.byId.get('{icn['id']}'), true)")
        pg.wait_for_timeout(2600)
        pg.screenshot(path=os.path.join(SHOT, "12_k_incheon_airport.png"))
        k_open(pg, base, "", 1200)
        pg.evaluate("() => app.almanac.open('terrain')")
        pg.wait_for_timeout(900)
        pg.evaluate("() => { const h = [...document.querySelectorAll('#almanac h3')].find((x) => /피복/.test(x.textContent)); if (h) h.scrollIntoView(); }")
        pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(SHOT, "12_k_almanac_cover.png"))
        log["errors"]["k"] = list(errs)
        errs.clear()
        # ---------- 신여지도 ----------
        y_open(pg, base, "#intro=0")
        pg.screenshot(path=os.path.join(SHOT, "12_y_national.png"))
        for nm, (x, y), _, yz in spots:
            y_open(pg, base, f"#v={x:.0f},{y:.0f},{yz}&intro=0", 3200)
            if nm in ("forest_types_inje", "jeju", "dmz"):
                pg.mouse.move(720, 450)
                pg.wait_for_timeout(700)
            pg.screenshot(path=os.path.join(SHOT, f"12_y_{nm}.png"))
        y_open(pg, base, "#lens=forest&intro=0")
        pg.screenshot(path=os.path.join(SHOT, "12_y_lens_forest.png"))
        y_open(pg, base, "#intro=0", 1500)
        pg.evaluate("() => app.selectItem(app.layerMap.items.find((i) => i.name === '인천공항'), {fly: true})")
        pg.wait_for_timeout(2500)
        pg.screenshot(path=os.path.join(SHOT, "12_y_incheon_airport.png"))
        y_open(pg, base, "#intro=0", 1500)
        pg.evaluate("() => app.almanac.open('terrain')")
        pg.wait_for_timeout(1200)
        pg.evaluate("() => { const h = [...document.querySelectorAll('h3, h4')].find((x) => /토지피복/.test(x.textContent)); if (h) h.scrollIntoView(); }")
        pg.wait_for_timeout(400)
        pg.screenshot(path=os.path.join(SHOT, "12_y_almanac_cover.png"))
        log["errors"]["y"] = list(errs)
        errs.clear()
        # ---------- 출처 쪽 ----------
        for sec in ("profile", "credits"):
            pg.goto(base + "sources/index.html#" + sec)
            pg.wait_for_selector("body.is-ready", timeout=20000)
            pg.wait_for_timeout(700)
            pg.evaluate(f"() => document.getElementById('{sec}').scrollIntoView()")
            pg.wait_for_timeout(300)
            pg.screenshot(path=os.path.join(SHOT, f"12_sources_{sec}.png"))
        pg.evaluate("() => { const h = [...document.querySelectorAll('h3')].find((x) => x.textContent.trim() === '그 밖의 표기'); if (h) h.scrollIntoView(); }")
        pg.wait_for_timeout(300)
        pg.screenshot(path=os.path.join(SHOT, "12_sources_other_credits.png"))
        pg.goto(base + "sources/index.html#list")
        pg.wait_for_selector("body.is-ready", timeout=20000)
        pg.wait_for_timeout(500)
        pg.evaluate("""() => { const i = document.querySelector('#list input[type=search], input[type=search]'); if (i) { i.value = '15150509'; i.dispatchEvent(new Event('input', {bubbles: true})); }
          const el = [...document.querySelectorAll('article, tr, li')].find((x) => /15150509/.test(x.textContent)); if (el) el.scrollIntoView({block: 'center'}); }""")
        pg.wait_for_timeout(600)
        pg.screenshot(path=os.path.join(SHOT, "12_sources_landcover_entry.png"))
        log["errors"]["sources"] = list(errs)
        ctx.close()
        br.close()
    srv.shutdown()
    print(json.dumps(log, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
